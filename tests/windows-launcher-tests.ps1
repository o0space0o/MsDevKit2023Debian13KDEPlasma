# Synthetic, non-elevated tests. Never installs WSL, reads target data or writes a disk.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $root 'windows\DevKit.Common.ps1')
$script:passed = 0

function Assert-Equal($Actual,$Expected,[string]$Name) {
    if ($Actual -ne $Expected) { throw "$Name expected '$Expected', got '$Actual'." }
    $script:passed++
}
function Assert-Rejected([scriptblock]$Action,[string]$Name) {
    $rejected = $false
    try { & $Action | Out-Null } catch { $rejected = $true }
    if (-not $rejected) { throw "$Name should have been rejected." }
    $script:passed++
}

# Replace the only native probe with a strict deterministic mock.
function Invoke-DevKitWslRead {
    param([string[]]$Arguments)
    $key = $Arguments -join '|'
    if (-not $script:responses.ContainsKey($key)) { throw "Unexpected native probe: $key" }
    $script:responses[$key]
}
function Reset-Responses {
    $script:responses = @{
        '--list|--quiet' = @{ExitCode=0;Output='Debian'}
        '--distribution|Debian|--user|root|--exec|uname|-m' = @{ExitCode=0;Output='aarch64'}
        '--distribution|Debian|--user|root|--exec|cat|/etc/os-release' = @{ExitCode=0;Output="ID=debian`nVERSION_ID=`"13`""}
        '--distribution|Debian|--user|root|--exec|uname|-r' = @{ExitCode=0;Output='6.6.0-microsoft-standard-WSL2'}
    }
}
$cases = @(
    @('--list|--quiet',1,'','SetupRequired'),
    @('--list|--quiet',0,'Ubuntu','SetupRequired'),
    @('--distribution|Debian|--user|root|--exec|uname|-m',1,'','RestartOrRepair'),
    @('--distribution|Debian|--user|root|--exec|uname|-m',0,'x86_64','WrongArchitecture'),
    @('--distribution|Debian|--user|root|--exec|cat|/etc/os-release',1,'','RestartOrRepair'),
    @('--distribution|Debian|--user|root|--exec|cat|/etc/os-release',0,"ID=ubuntu`nVERSION_ID=13",'WrongDistribution'),
    @('--distribution|Debian|--user|root|--exec|cat|/etc/os-release',0,"ID=debian`nVERSION_ID=12",'WrongDistribution'),
    @('--distribution|Debian|--user|root|--exec|uname|-r',1,'','RestartOrRepair'),
    @('--distribution|Debian|--user|root|--exec|uname|-r',0,'4.4.0-Microsoft','Wsl2Required')
)
foreach ($case in $cases) {
    Reset-Responses
    $script:responses[$case[0]] = @{ExitCode=$case[1];Output=$case[2]}
    Assert-Equal (Get-DevKitBuilderState) $case[3] $case[0]
}
Reset-Responses
Assert-Equal (Get-DevKitBuilderState) 'Ready' 'Ready ARM64 builder'
$script:responses['--list|--quiet'].Output = "Ubuntu`r`n Debian `r`n"
Assert-Equal (Get-DevKitBuilderState) 'Ready' 'Multiple distributions and CRLF'
Assert-Rejected { Get-DevKitBuilderState -Distribution '--unregister' } 'Invalid distro name'
Assert-Rejected { Get-DevKitBuilderState -Distribution 'Bad Name' } 'Spaced distro name'

$paths = Get-DevKitPaths -SourceRoot 'C:\Work\Linux'
Assert-Equal $paths.Iso 'C:\Work\Linux\ISO' 'Single ISO output folder'
Assert-Equal $paths.Pdf 'C:\Work\Linux\docs\DevKit2023CustomLinux-Guide.pdf' 'Public guide PDF'
Assert-Equal $paths.Guide 'C:\Work\Linux\SETUP.md' 'Single guide'
Assert-Equal (Get-DevKitPaths).Source $root 'Default source location follows the checkout'
Assert-Rejected { Remove-DevKitTemporaryDirectory 'C:\Work\Linux' } 'Broad cleanup refused'

# Only generated text fixtures are written, under one validated temporary child.
$tempParent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$fixture = Join-Path $tempParent ('devkit-launcher-test-' + [Guid]::NewGuid().ToString('N'))
if ((Split-Path -Parent $fixture) -ne $tempParent -or (Test-Path -LiteralPath $fixture)) { throw 'Unsafe test directory.' }
Assert-DevKitPlainPath $fixture
New-Item -ItemType Directory -Path $fixture | Out-Null
try {
    # Hidden ancestors such as AppData must work on Windows PowerShell 5.1 too.
    # Set attributes only on this synthetic child, never on the real user profile.
    $hiddenParent = Join-Path $fixture 'hidden-parent'
    New-Item -ItemType Directory -Path $hiddenParent | Out-Null
    $hiddenItem = Get-Item -LiteralPath $hiddenParent -Force
    $hiddenItem.Attributes = $hiddenItem.Attributes -bor [IO.FileAttributes]::Hidden
    Assert-Equal ([bool]((Get-Item -LiteralPath $hiddenParent -Force).Attributes -band [IO.FileAttributes]::Hidden)) $true 'Hidden fixture attribute'
    Assert-Equal (Assert-DevKitPlainPath $hiddenParent) $null 'Existing hidden folder'
    Assert-Equal (Assert-DevKitPlainPath (Join-Path $hiddenParent 'not-created-yet')) $null 'Missing child under hidden ancestor'
    $visibleChild = Join-Path $hiddenParent 'visible-child'
    New-Item -ItemType Directory -Path $visibleChild | Out-Null
    Assert-Equal (Assert-DevKitPlainPath $visibleChild) $null 'Existing child under hidden ancestor'
    & {
        # Simulate a hidden reparse point without creating links or requiring admin.
        function Get-Item {
            param([string]$LiteralPath,[switch]$Force)
            if ($LiteralPath -eq $hiddenParent) {
                return [pscustomobject]@{Attributes=([IO.FileAttributes]::Directory -bor [IO.FileAttributes]::Hidden -bor [IO.FileAttributes]::ReparsePoint)}
            }
            Microsoft.PowerShell.Management\Get-Item @PSBoundParameters
        }
        Assert-Rejected { Assert-DevKitPlainPath $visibleChild } 'Hidden reparse ancestor remains refused'
    }
    $iso = Join-Path $fixture 'synthetic.iso'
    $manifestPath = Join-Path $fixture 'build-manifest.json'
    [IO.File]::WriteAllText($iso,'Synthetic fixture; not an actual ISO or device record.')
    $hash = (Get-FileHash -LiteralPath $iso -Algorithm SHA256).Hash.ToLowerInvariant()
    function Write-FixtureManifest($Change=@{}) {
        $data = @{
            distribution='DevKit2023CustomLinux';releaseProfile='private-prepared'
            staticVerification='passed';containsDeviceIdentity=$true
            installationEnabled=$false;sha256=$hash
        }
        foreach ($key in $Change.Keys) { $data[$key]=$Change[$key] }
        [IO.File]::WriteAllText($manifestPath,($data | ConvertTo-Json))
    }
    Assert-Rejected { Get-DevKitPreparedIso $iso } 'Missing manifest'
    Write-FixtureManifest
    Assert-Equal (Get-DevKitPreparedIso $iso) $iso 'Completed image handoff'
    Write-FixtureManifest @{installationEnabled=$true;installerPolicy='windows-free-space-v1'}
    Assert-Equal (Get-DevKitPreparedIso $iso) $iso 'Completed installation candidate handoff'
    foreach ($change in @(
        @{distribution='OtherLinux'}, @{releaseProfile='public-base'},
        @{staticVerification='pending'}, @{containsDeviceIdentity=$false},
        @{installationEnabled=$true}, @{installationEnabled='false'},
        @{installationEnabled=$true;installerPolicy='unsafe'}, @{sha256=('0'*64)}, @{sha256='partial'}
    )) {
        Write-FixtureManifest $change
        Assert-Rejected { Get-DevKitPreparedIso $iso } ('Invalid manifest: '+($change.Keys -join ','))
    }
    Write-FixtureManifest
    [IO.File]::AppendAllText($iso,'Changed after manifest publication')
    Assert-Rejected { Get-DevKitPreparedIso $iso } 'Modified image'
    Assert-Rejected { Get-DevKitPreparedIso $manifestPath } 'Non-ISO selection'
} finally {
    $resolved = (Resolve-Path -LiteralPath $fixture).Path
    if ($resolved -ne $fixture -or (Split-Path -Parent $resolved) -ne $tempParent -or
        (Split-Path -Leaf $resolved) -notmatch '^devkit-launcher-test-[a-f0-9]{32}$') {
        throw 'Refusing unexpected test cleanup path.'
    }
    Assert-DevKitPlainPath $resolved
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
Write-Host "$script:passed synthetic Windows launcher checks passed. No WSL setup, target collection or drive writes were performed."
