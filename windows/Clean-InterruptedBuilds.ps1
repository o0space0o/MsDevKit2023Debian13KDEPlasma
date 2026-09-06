[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'DevKit.Common.ps1')
$paths = Get-DevKitPaths
$userSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$wsl = Join-Path $env:SystemRoot 'System32\wsl.exe'
$cleaned = 0
# No recursive discovery: only direct temporary children with a valid ownership record.
foreach ($directory in Get-ChildItem -LiteralPath ([IO.Path]::GetTempPath()) -Directory) {
    if ($directory.Name -notmatch '^DevKit2023CustomLinux-build-[a-f0-9]{32}$') { continue }
    Assert-DevKitPlainPath $directory.FullName
    $marker = Join-Path $directory.FullName 'build-owner.json'
    if (-not (Test-Path -LiteralPath $marker)) { continue }
    Assert-DevKitPlainPath $marker
    $record = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
    if ($record.Product -ne 'DevKit2023CustomLinux' -or $record.Source -ne $paths.Source -or $record.User -ne $userSid) { continue }
    $running = Get-Process -Id $record.Process -ErrorAction SilentlyContinue
    if ($running -and $running.StartTime.ToUniversalTime().Ticks -eq $record.Started) {
        Write-Warning 'A build from this project is still running; its files were left intact.'
        continue
    }
    if ($record.Native) {
        if ($record.Native -notmatch '^/var/tmp/DevKit2023CustomLinux-build\.[A-Za-z0-9]{10}$' -or
            $record.Distribution -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$') { throw 'Invalid interrupted-build ownership record.' }
        $cleanup = (& $wsl --distribution $record.Distribution --user root --exec wslpath -a -u (Join-Path $paths.Source 'scripts\clean-workspace.sh') | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $cleanup) { throw 'WSL is unavailable. Temporary files are preserved until cleanup can complete.' }
        & $wsl --distribution $record.Distribution --user root --exec bash $cleanup $record.Native | Out-Host
        if ($LASTEXITCODE -ne 0) { throw 'Linux build is busy or cleanup was refused. No broad paths were removed.' }
    }
    if ($record.Partial) {
        $partial = [IO.Path]::GetFullPath($record.Partial)
        if ((Split-Path -Parent $partial) -ne $paths.Iso -or
            (Split-Path -Leaf $partial) -notmatch '^\.building-[a-f0-9]{32}\.partial$') { throw 'Unexpected partial ISO path.' }
        Assert-DevKitPlainPath $partial
        if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
    }
    Remove-DevKitTemporaryDirectory $directory.FullName
    $cleaned++
}
Write-Host "Cleaned $cleaned interrupted build(s). Current ISOs, external bundles and WSL itself were preserved."
