[CmdletBinding(DefaultParameterSetName='ThisTarget')]
param(
    [string]$Distribution='Debian',
    [Parameter(Mandatory,ParameterSetName='ThisTarget')][switch]$TargetThisDevice,
    [Parameter(Mandatory,ParameterSetName='ExportedTarget')][string]$TargetBundle,
    [switch]$ReplaceExisting,
    [switch]$PassThru
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'DevKit.Common.ps1')
$paths = Get-DevKitPaths
$wsl = Join-Path $env:SystemRoot 'System32\wsl.exe'
if ((Get-CimInstance Win32_ComputerSystem).SystemType -notmatch 'ARM64') {
    throw 'Building requires Windows ARM64 with native Debian 13 ARM64 WSL 2.'
}
if ($PSCmdlet.ParameterSetName -eq 'ThisTarget' -and -not $TargetThisDevice) {
    throw 'Explicit target selection is required.'
}
Ensure-DevKitBuilder -Distribution $Distribution
Initialize-DevKitPrivateDirectory $paths.Iso
$version = (Get-Content -LiteralPath (Join-Path $paths.Source 'VERSION') -Raw).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid product version.' }
$destination = Join-Path $paths.Iso "DevKit2023CustomLinux-$version-arm64.iso"
Assert-DevKitPlainPath $destination
if ((Test-Path -LiteralPath $destination) -and -not $ReplaceExisting) {
    throw 'The current ISO is preserved. Use the launcher to explicitly confirm replacing it.'
}
$originalHash = if (Test-Path -LiteralPath $destination) { (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash } else { $null }
$scratch = Join-Path ([IO.Path]::GetTempPath()) ('DevKit2023CustomLinux-build-' + [Guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $scratch) { throw 'Temporary-directory collision.' }
$nativeRun = $null
$partial = $null
$owner = @{
    Product='DevKit2023CustomLinux'; Source=$paths.Source
    User=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    Process=$PID; Started=(Get-Process -Id $PID).StartTime.ToUniversalTime().Ticks
    Native=$null; Partial=$null; Distribution=$Distribution
}
function Save-BuildOwner {
    $owner.Native = $nativeRun
    $owner.Partial = $partial
    [IO.File]::WriteAllText((Join-Path $scratch 'build-owner.json'),($owner | ConvertTo-Json))
}
function Convert-ToWslPath([string]$Path) {
    $result = (& $wsl --distribution $Distribution --user root --exec wslpath -a -u $Path | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $result) { throw 'Windows-to-Linux path conversion failed.' }
    $result
}
try {
    Initialize-DevKitPrivateDirectory $scratch
    Save-BuildOwner
    if ($PSCmdlet.ParameterSetName -eq 'ThisTarget') {
        $TargetBundle = Join-Path $scratch 'target-bundle'
        & (Join-Path $PSScriptRoot 'Export-DevKit2023Target.ps1') -TargetThisDevice -OutputDirectory $TargetBundle | Out-Host
    } else {
        $TargetBundle = (Resolve-Path -LiteralPath $TargetBundle).Path
        Assert-DevKitPlainPath $TargetBundle
    }
    $nativeRun = (& $wsl --distribution $Distribution --user root --exec mktemp -d /var/tmp/DevKit2023CustomLinux-build.XXXXXXXXXX | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $nativeRun -notmatch '^/var/tmp/DevKit2023CustomLinux-build\.[A-Za-z0-9]{10}$') {
        throw 'Could not allocate an isolated native Linux build directory.'
    }
    Save-BuildOwner
    $bootstrap = Convert-ToWslPath (Join-Path $paths.Source 'scripts\wsl-build-bootstrap.sh')
    $source = Convert-ToWslPath $paths.Source
    $bundle = Convert-ToWslPath $TargetBundle
    $resultDirectory = Join-Path $scratch 'result'
    $output = Convert-ToWslPath $resultDirectory
    Write-Host '[2/4] Building a fresh base, then authenticating the selected target. Allow several hours.'
    # Chroot mounts stay in a private namespace, not the normal WSL session.
    & $wsl --distribution $Distribution --user root --exec unshare --mount --propagation private bash $bootstrap $source $nativeRun $bundle $output | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'Build/preparation stopped. Read the error above; the previous ISO has not been replaced.' }
    $stagedIso = Get-DevKitPreparedIso -IsoPath (Join-Path $resultDirectory "DevKit2023CustomLinux-$version-arm64.iso")
    $expectedHash = (Get-FileHash -LiteralPath $stagedIso -Algorithm SHA256).Hash
    # Preserve the current ISO until the replacement and copied bytes are verified.
    $partial = Join-Path $paths.Iso ('.building-' + [Guid]::NewGuid().ToString('N') + '.partial')
    Save-BuildOwner
    Copy-Item -LiteralPath $stagedIso -Destination $partial
    if ((Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash -ne $expectedHash) { throw 'Final ISO copy verification failed.' }
    Assert-DevKitPlainPath $destination
    if ($originalHash) {
        if (-not (Test-Path -LiteralPath $destination) -or
            (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ne $originalHash) {
            throw 'The destination changed during building. Refusing to overwrite it.'
        }
        [IO.File]::Replace($partial,$destination,$null)
    } else { [IO.File]::Move($partial,$destination) }
    $partial = $null
    Write-Host "Ready: $destination"
    Write-Host ("SHA-256: " + $expectedHash.ToLowerInvariant())
    Write-Host 'This private ISO belongs only to the selected Dev Kit. Removing temporary build data.'
} finally {
    # Attempt Windows cleanup even if Linux is unavailable after interruption.
    try {
        if ($partial -and (Test-Path -LiteralPath $partial)) {
            Assert-DevKitPlainPath $partial
            Remove-Item -LiteralPath $partial -Force
        }
        if ($nativeRun -match '^/var/tmp/DevKit2023CustomLinux-build\.[A-Za-z0-9]{10}$') {
            $cleanup = Convert-ToWslPath (Join-Path $paths.Source 'scripts\clean-workspace.sh')
            & $wsl --distribution $Distribution --user root --exec bash $cleanup $nativeRun | Out-Host
            if ($LASTEXITCODE -ne 0) { throw "Linux cleanup could not finish: $nativeRun. See SETUP.md." }
        }
    } finally {
        if ($nativeRun -and (Test-Path -LiteralPath $scratch)) {
            # Keep the private run and its ownership record if cleanup is interrupted.
            $nativeExists = Invoke-DevKitWslRead -Arguments @('--distribution',$Distribution,'--user','root','--exec','test','-e',$nativeRun)
            if ($nativeExists.ExitCode -eq 1 -and -not $nativeExists.Output) { Remove-DevKitTemporaryDirectory $scratch }
            else { Write-Warning "Cleanup needs attention. Reopen the launcher and choose Remove interrupted build files. Private temporary data remains at $scratch." }
        } else { Remove-DevKitTemporaryDirectory $scratch }
    }
}
if ($PassThru) { [pscustomobject]@{ IsoPath=$destination } }
