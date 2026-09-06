[CmdletBinding()]
param([string]$Distribution='Debian', [switch]$CheckOnly)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'DevKit.Common.ps1')

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    ([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

try {
    $state = Get-DevKitBuilderState -Distribution $Distribution
    if ($CheckOnly) {
        Write-Host ("Builder state: " + $state)
        if ($state -eq 'Ready') { exit 0 }
        exit 1
    }
    if ((Get-CimInstance Win32_ComputerSystem).SystemType -notmatch 'ARM64') {
        throw 'The guided builder requires Windows ARM64.'
    }
    if ($state -eq 'Ready') {
        Write-Host 'Debian 13 ARM64 WSL 2 is ready. Continuing automatically.'
        exit 0
    }
    if ($state -in @('WrongArchitecture','WrongDistribution')) {
        throw "The existing $Distribution distribution is not Debian 13 ARM64. It has been left untouched. See SETUP.md; do not delete a distribution containing your work."
    }
    if (-not (Test-IsAdministrator)) {
        Write-Host 'Approve Windows administrator access for WSL setup. No automatic reboot is performed.'
        $hostExecutable = (Get-Process -Id $PID).Path
        $arguments = @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"{0}"' -f $PSCommandPath),
                       '-Distribution',('"{0}"' -f $Distribution))
        $process = Start-Process -FilePath $hostExecutable -Verb RunAs -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
        exit $process.ExitCode
    }
    $result = 0
    $restartNeeded = $false
    foreach ($name in @('VirtualMachinePlatform','Microsoft-Windows-Subsystem-Linux')) {
        $feature = Get-WindowsOptionalFeature -Online -FeatureName $name
        if ($feature.State -eq 'EnablePending') { $restartNeeded = $true; continue }
        if ($feature.State -ne 'Enabled') {
            $change = Enable-WindowsOptionalFeature -Online -FeatureName $name -All -NoRestart
            if ($change.RestartNeeded) { $restartNeeded = $true }
        }
    }
    if ($restartNeeded) {
        Write-Host 'Restart Windows, then open Start-DevKit2023CustomLinux.cmd again. Setup will continue.'
        $result = 3010
    } else {
        $wsl = Join-Path $env:SystemRoot 'System32\wsl.exe'
        if (-not (Test-Path -LiteralPath $wsl)) { throw 'WSL is unavailable. Apply normal Windows updates and try this launcher again.' }
        $installed = Invoke-DevKitWslRead -Arguments @('--list','--quiet')
        if ($installed.ExitCode -ne 0) {
            # The inbox wsl.exe may only be an installer stub at this point.
            # Do not run distribution settings before installing the runtime.
            & $wsl --install --no-distribution --web-download | Out-Host
            if ($LASTEXITCODE -eq 3010) {
                Write-Host 'WSL installation needs a restart. Reopen the same launcher afterwards.'
                $result = 3010
            } elseif ($LASTEXITCODE -ne 0) { throw 'WSL runtime installation failed. Read the setup error above.' }
        }
        if ($result -ne 3010) {
            $installed = Invoke-DevKitWslRead -Arguments @('--list','--quiet')
            # Some WSL versions return nonzero for an empty distro list.
            # The runtime install succeeded above; let install report any
            # remaining platform error instead of rejecting an empty host.
            if ($installed.ExitCode -ne 0 -or @($installed.Output -split "\r?\n" | ForEach-Object { $_.Trim() }) -notcontains $Distribution) {
                # Current WSL registers Debian's modern .wsl image without a
                # separate Store-app first launch. Keep the existing distro default.
                & $wsl --update --web-download | Out-Host
                if ($LASTEXITCODE -ne 0) { throw 'WSL update failed. Current WSL is required for automatic Debian registration.' }
                & $wsl --install --distribution $Distribution --no-launch --web-download --version 2 | Out-Host
                if ($LASTEXITCODE -eq 3010) { $result = 3010 }
                elseif ($LASTEXITCODE -ne 0) { throw 'Debian installation failed. Review the setup error; no distribution was deleted.' }
            } elseif ($state -eq 'Wsl2Required') {
                Add-Type -AssemblyName System.Windows.Forms
                $confirm = [Windows.Forms.MessageBox]::Show(
                    'The existing Debian uses WSL 1. Back up any important Debian files before converting it to WSL 2. Conversion can fail and take time. Continue with conversion now?',
                    'Confirm Debian WSL 2 conversion', 'YesNo', 'Warning', 'Button2')
                if ($confirm -ne 'Yes') { throw 'WSL conversion cancelled. Existing Debian was left unchanged.' }
                & $wsl --set-version $Distribution 2 | Out-Host
                if ($LASTEXITCODE -ne 0) { throw 'WSL 2 conversion failed. Review the setup error and your Debian backup before trying again.' }
            }
            if ($result -ne 3010) {
                $after = Get-DevKitBuilderState -Distribution $Distribution
                if ($after -eq 'Ready') {
                    Write-Host 'Setup complete. Continuing to the Linux build automatically.'
                } elseif ($after -eq 'SetupRequired') {
                    throw 'Debian did not register after installation. Review the setup error and Windows updates; do not delete other distributions or repeatedly reboot without diagnosis.'
                } elseif ($after -in @('WrongArchitecture','WrongDistribution','Wsl2Required')) {
                    throw "Builder state after setup: $after. No existing distribution was deleted."
                } else {
                    Write-Host 'A Windows restart or WSL repair is still required. Reopen the same launcher afterwards.'
                    $result = 3010
                }
            }
        }
    }
    exit $result
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    if (-not $CheckOnly) {
        Add-Type -AssemblyName System.Windows.Forms
        [void][Windows.Forms.MessageBox]::Show($_.Exception.Message,'DevKit2023CustomLinux - WSL setup stopped','OK','Error')
    }
    exit 1
}
