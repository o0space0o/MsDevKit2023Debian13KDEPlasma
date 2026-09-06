[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'DevKit.Common.ps1')
Add-Type -AssemblyName System.Windows.Forms
[Windows.Forms.Application]::EnableVisualStyles()

function Show-SetupGuide {
    $pdf = (Get-DevKitPaths).Pdf
    if (Test-Path -LiteralPath $pdf) { Start-Process -FilePath $pdf | Out-Null; return }
    $guide = New-Object Windows.Forms.Form
    $guide.Text = 'DevKit2023CustomLinux - setup guide'
    $guide.ClientSize = New-Object Drawing.Size(820,600)
    $guide.StartPosition = 'CenterScreen'
    $text = New-Object Windows.Forms.TextBox
    $text.Multiline = $true
    $text.ReadOnly = $true
    $text.ScrollBars = 'Vertical'
    $text.Dock = 'Fill'
    $text.Font = New-Object Drawing.Font('Consolas',11)
    $text.Text = Get-Content -LiteralPath (Get-DevKitPaths).Guide -Raw -Encoding UTF8
    $guide.Controls.Add($text)
    [void]$guide.ShowDialog()
    $guide.Dispose()
}
function Confirm-ThisTarget {
    [Windows.Forms.MessageBox]::Show(
        'Prepare an ISO for THIS Dev Kit? Its three required firmware files, signed INF/CAT evidence, hashed target binding and Bluetooth address will be included privately. No passwords, pairing keys, recovery keys or full registry hives are collected. The finished ISO is only for this target.',
        'Confirm intended Dev Kit', 'OKCancel', 'Information') -eq 'OK'
}
function Show-UsbHandoff {
    param([Parameter(Mandatory)][string]$IsoPath)
    Write-Host "[4/4] Completed ISO: $IsoPath"
    $answer = [Windows.Forms.MessageBox]::Show(
        'The completed ISO has passed the build verification and copy checksum checks. Open its folder and the official Rufus download page? Choose Windows ARM64. Select the correct USB in Rufus and confirm its erase warning. This launcher never selects or writes a disk. Read the guide before installation.',
        'DevKit2023CustomLinux - ready for USB', 'YesNo', 'Information')
    if ($answer -eq 'Yes') {
        Start-Process -FilePath explorer.exe -ArgumentList ('"{0}"' -f (Split-Path -Parent $IsoPath)) | Out-Null
        Start-Process 'https://rufus.ie/en/' | Out-Null
    }
}
try {
    $form = New-Object Windows.Forms.Form
    $form.Text = 'DevKit2023CustomLinux 1.0.0'
    $form.ClientSize = New-Object Drawing.Size(680,414)
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedDialog'
    $form.MaximizeBox = $false
    $label = New-Object Windows.Forms.Label
    $label.SetBounds(22,18,636,55)
    $label.Text = 'One guided build: WSL setup, fresh source build, target preparation, ISO. Only the finished ISO is kept. Each Dev Kit needs its own prepared image.'
    $form.Controls.Add($label)
    $choices = @(
        @('this', 'Build an ISO for THIS Dev Kit (recommended)'),
        @('bundle', 'Build for another Dev Kit from its exported bundle'),
        @('export', 'Export THIS Dev Kit for a different ARM64 builder')
    )
    $offset = 78
    foreach ($choice in $choices) {
        $button = New-Object Windows.Forms.Button
        $button.SetBounds(22,$offset,636,48)
        $button.Text = $choice[1]
        $button.Tag = $choice[0]
        $button.Add_Click({ $this.FindForm().Tag = $this.Tag; $this.FindForm().Close() })
        $form.Controls.Add($button)
        $offset += 58
    }
    $guideButton = New-Object Windows.Forms.Button
    $guideButton.SetBounds(22,268,310,44)
    $guideButton.Text = 'Read the complete PDF guide'
    $guideButton.Add_Click({ Show-SetupGuide })
    $form.Controls.Add($guideButton)
    $isoButton = New-Object Windows.Forms.Button
    $isoButton.SetBounds(348,268,310,44)
    $isoButton.Text = 'Open ISO folder'
    $isoButton.Add_Click({
        try {
            Initialize-DevKitPrivateDirectory (Get-DevKitPaths).Iso
            Start-Process -FilePath explorer.exe -ArgumentList ('"{0}"' -f (Get-DevKitPaths).Iso) | Out-Null
        } catch { [void][Windows.Forms.MessageBox]::Show($_.Exception.Message,'ISO folder','OK','Error') }
    })
    $form.Controls.Add($isoButton)
    $cleanupButton = New-Object Windows.Forms.Button
    $cleanupButton.SetBounds(22,326,636,44)
    $cleanupButton.Text = 'Remove interrupted build files'
    $cleanupButton.Add_Click({ $this.FindForm().Tag = 'cleanup'; $this.FindForm().Close() })
    $form.Controls.Add($cleanupButton)
    [void]$form.ShowDialog()
    $mode = $form.Tag
    $form.Dispose()
    if (-not $mode) { exit 0 }
    if ($mode -eq 'cleanup') {
        & (Join-Path $PSScriptRoot 'Clean-InterruptedBuilds.ps1')
    } elseif ($mode -eq 'export') {
        if (-not (Confirm-ThisTarget)) { exit 0 }
        $folder = New-Object Windows.Forms.FolderBrowserDialog
        $folder.Description = 'Choose a PRIVATE parent folder. A new target-bundle subfolder will be created; transfer it privately to the ARM64 builder.'
        if ($folder.ShowDialog() -ne 'OK') { exit 0 }
        $destination = Join-Path $folder.SelectedPath 'target-bundle'
        & (Join-Path $PSScriptRoot 'Export-DevKit2023Target.ps1') -TargetThisDevice -OutputDirectory $destination
        Write-Host "Export complete: $destination"
        Write-Host 'This explicitly requested transfer bundle stays where you selected it. Remove it after transferring/building.'
    } else {
        $parameters = @{ PassThru=$true }
        if ($mode -eq 'bundle') {
            $folder = New-Object Windows.Forms.FolderBrowserDialog
            $folder.Description = 'Select the intended target-bundle folder containing manifest.json and packages.'
            if ($folder.ShowDialog() -ne 'OK') { exit 0 }
            $parameters.TargetBundle = $folder.SelectedPath
        } else {
            if (-not (Confirm-ThisTarget)) { exit 0 }
            $parameters.TargetThisDevice = $true
        }
        if (Test-Path -LiteralPath (Get-DevKitPaths).Iso) {
            $existing = @(Get-ChildItem -LiteralPath (Get-DevKitPaths).Iso -Filter '*.iso' -File)
            if ($existing.Count) {
                $choice = [Windows.Forms.MessageBox]::Show(
                    'Replace the current version ISO after the new build succeeds? The existing image stays intact until verification finishes. No backup or older build is kept. Cancel if you want to preserve it.',
                    'Replace current ISO?', 'OKCancel', 'Warning', 'Button2')
                if ($choice -ne 'OK') { exit 0 }
                $parameters.ReplaceExisting = $true
            }
        }
        $result = & (Join-Path $PSScriptRoot 'Build-DevKit2023CustomLinuxISO.ps1') @parameters
        if (-not $result -or -not $result.IsoPath) { throw 'No completed ISO was returned.' }
        Show-UsbHandoff $result.IsoPath
    }
    [void](Read-Host 'Finished. Press Enter to close')
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    [void][Windows.Forms.MessageBox]::Show($_.Exception.Message,'DevKit2023CustomLinux - not completed','OK','Error')
    exit 1
}
