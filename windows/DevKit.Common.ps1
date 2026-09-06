# Shared Windows paths and readiness checks. Dot-sourcing performs no setup/export.
Set-StrictMode -Version Latest

function Get-DevKitPaths {
    param([string]$SourceRoot = (Split-Path -Parent $PSScriptRoot))
    $source = [IO.Path]::GetFullPath($SourceRoot).TrimEnd('\')
    [pscustomobject]@{
        Source = $source
        Iso = Join-Path $source 'ISO'
        Guide = Join-Path $source 'SETUP.md'
        Pdf = Join-Path $source 'docs\DevKit2023CustomLinux-Guide.pdf'
    }
}

function Assert-DevKitPlainPath {
    param([Parameter(Mandatory)][string]$Path)
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        # AppData and other hidden ancestors still need the reparse-point check.
        if ((Test-Path -LiteralPath $cursor) -and
            ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Linked/reparse-point output paths are not accepted.'
        }
        $cursor = Split-Path -Parent $cursor
    }
}

function Initialize-DevKitPrivateDirectory {
    param([Parameter(Mandatory)][string]$Path)
    Assert-DevKitPlainPath $Path
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
    $acl = [Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    foreach ($sid in @([Security.Principal.WindowsIdentity]::GetCurrent().User,
                      [Security.Principal.SecurityIdentifier]::new('S-1-5-18'),
                      [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            $sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Remove-DevKitTemporaryDirectory {
    param([Parameter(Mandatory)][string]$Path)
    $parent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
    $resolved = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    if ((Split-Path -Parent $resolved) -ne $parent -or
        (Split-Path -Leaf $resolved) -notmatch '^DevKit2023CustomLinux-build-[a-f0-9]{32}$') {
        throw 'Refusing cleanup outside an explicitly created build temporary directory.'
    }
    Assert-DevKitPlainPath $resolved
    if (Test-Path -LiteralPath $resolved) {
        $links = @(Get-ChildItem -LiteralPath $resolved -Recurse -Force |
            Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint })
        if ($links.Count) { throw 'Temporary cleanup refused: linked content found.' }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}

function Invoke-DevKitWslRead {
    param([string[]]$Arguments)
    $wsl = Join-Path $env:SystemRoot 'System32\wsl.exe'
    if (-not (Test-Path -LiteralPath $wsl)) { return @{ ExitCode=1; Output='WSL executable is unavailable.' } }
    $ErrorActionPreference = 'Continue'
    $output = (& $wsl @Arguments 2>&1 | Out-String) -replace "`0",''
    @{ ExitCode=$LASTEXITCODE; Output=$output.Trim() }
}

function Get-DevKitBuilderState {
    param([string]$Distribution='Debian')
    if ($Distribution -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$') { throw 'Invalid WSL distribution name.' }
    $list = Invoke-DevKitWslRead -Arguments @('--list','--quiet')
    if ($list.ExitCode -ne 0) { return 'SetupRequired' }
    $names = @($list.Output -split "`r?`n" | ForEach-Object { $_.Trim() })
    if ($names -notcontains $Distribution) { return 'SetupRequired' }
    $arch = Invoke-DevKitWslRead -Arguments @('--distribution',$Distribution,'--user','root','--exec','uname','-m')
    if ($arch.ExitCode -ne 0) { return 'RestartOrRepair' }
    if ($arch.Output -notin @('aarch64','arm64')) { return 'WrongArchitecture' }
    $release = Invoke-DevKitWslRead -Arguments @('--distribution',$Distribution,'--user','root','--exec','cat','/etc/os-release')
    if ($release.ExitCode -ne 0) { return 'RestartOrRepair' }
    if ($release.Output -notmatch '(?m)^ID="?debian"?\s*$' -or
        $release.Output -notmatch '(?m)^VERSION_ID="?13"?\s*$') { return 'WrongDistribution' }
    $kernel = Invoke-DevKitWslRead -Arguments @('--distribution',$Distribution,'--user','root','--exec','uname','-r')
    if ($kernel.ExitCode -ne 0) { return 'RestartOrRepair' }
    if ($kernel.Output -notmatch '(?i)microsoft.*WSL2') { return 'Wsl2Required' }
    'Ready'
}

function Ensure-DevKitBuilder {
    param([string]$Distribution='Debian')
    Write-Host '[1/4] Checking Windows / Debian ARM64 WSL 2. Setup runs automatically if needed.'
    $hostExecutable = (Get-Process -Id $PID).Path
    & $hostExecutable -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'Setup-WSL.ps1') -Distribution $Distribution | Out-Host
    $code = $LASTEXITCODE
    if ($code -eq 3010) {
        throw 'Windows setup needs a restart. Restart when convenient, then double-click Start-DevKit2023CustomLinux.cmd again. Use the same guided option; no separate commands are needed.'
    }
    if ($code -ne 0) { throw 'WSL setup/readiness failed. See the message above and the troubleshooting section in SETUP.md. Do not reinstall or delete an existing WSL distribution.' }
}

function Get-DevKitPreparedIso {
    param([Parameter(Mandatory)][string]$IsoPath)
    $iso = (Resolve-Path -LiteralPath $IsoPath).Path
    if ([IO.Path]::GetExtension($iso) -ne '.iso') { throw 'Select the prepared .iso file.' }
    $manifestPath = Join-Path (Split-Path -Parent $iso) 'build-manifest.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.distribution -ne 'DevKit2023CustomLinux' -or
        $manifest.releaseProfile -ne 'private-prepared' -or
        $manifest.staticVerification -ne 'passed' -or
        $manifest.installationEnabled -isnot [bool] -or
        ($manifest.installationEnabled -and $manifest.installerPolicy -ne 'windows-free-space-v1') -or
        $manifest.containsDeviceIdentity -ne $true -or
        $manifest.sha256 -notmatch '^[a-f0-9]{64}$') {
        throw 'Select a completed private prepared ISO with its original manifest, not the public base.'
    }
    if ((Get-FileHash -LiteralPath $iso -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.sha256) {
        throw 'Prepared ISO checksum does not match its manifest.'
    }
    $iso
}
