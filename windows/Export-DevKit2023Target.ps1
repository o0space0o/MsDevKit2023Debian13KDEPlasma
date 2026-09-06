[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$OutputDirectory,
    [Parameter(Mandatory)][switch]$TargetThisDevice
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'DevKit.Common.ps1')
if (-not $TargetThisDevice) { throw 'Explicitly select this Windows Dev Kit as the target.' }
$computer = Get-CimInstance Win32_ComputerSystem
if ($computer.Model -ne 'Windows Dev Kit 2023' -or $computer.SystemType -notmatch 'ARM64') {
    throw 'Target export must run on the intended Windows Dev Kit 2023.'
}
$sourceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$output = [IO.Path]::GetFullPath($OutputDirectory)
if ($output -eq $sourceRoot -or $output.StartsWith($sourceRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Private target material must be outside public source.'
}
if (Test-Path -LiteralPath $output) { throw 'Use a new private output directory.' }
$ancestor = Split-Path -Parent $output
while ($ancestor) {
    if ((Test-Path -LiteralPath $ancestor) -and ((Get-Item -LiteralPath $ancestor).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Reparse-point output paths are not accepted.'
    }
    $ancestor = Split-Path -Parent $ancestor
}
$uuidText = ([string](Get-CimInstance Win32_ComputerSystemProduct).UUID).Trim().ToLowerInvariant()
$uuid = [Guid]::Empty
if (-not [Guid]::TryParse($uuidText, [ref]$uuid) -or $uuid -eq [Guid]::Empty -or $uuid.ToString('N') -eq ('f' * 32)) {
    throw 'This target has no usable SMBIOS UUID. No identity fallback will be used.'
}
$sha = [Security.Cryptography.SHA256]::Create()
try {
    $bindingInput = "DevKit2023CustomLinux target v1`nsmbios-uuid`n$($uuid.ToString('D').ToLowerInvariant())`n"
    $binding = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($bindingInput)))).Replace('-','').ToLowerInvariant()
} finally { $sha.Dispose() }

# Query only the built-in Qualcomm UART instances. Never copy a registry hive
# or Windows pairing-key storage. Ambiguity is an error, not first-match wins.
$radioBase = 'Registry::HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Enum\QCA_SHB\UART_H4'
if (-not (Test-Path -LiteralPath $radioBase)) { throw 'Built-in Qualcomm Bluetooth controller not found in Windows.' }
$addresses = @()
foreach ($instance in Get-ChildItem -LiteralPath $radioBase) {
    $parameters = Join-Path $instance.PSPath 'Device Parameters'
    $properties = Get-ItemProperty -LiteralPath $parameters -ErrorAction Stop
    if ($properties.PSObject.Properties.Name -notcontains 'DeviceAddressCache') { continue }
    $raw = $properties.DeviceAddressCache
    if ($raw -isnot [string]) { throw 'Unexpected Bluetooth address encoding; refusing to guess.' }
    $compact = $raw.Trim().Replace(':','').Replace('-','').ToUpperInvariant()
    if ($compact -notmatch '^[0-9A-F]{12}$' -or $compact -eq ('0' * 12) -or $compact -eq ('F' * 12) -or ([Convert]::ToInt32($compact.Substring(0,2),16) -band 3)) {
        throw 'Windows Bluetooth public address is invalid.'
    }
    $addresses += ((0..5 | ForEach-Object { $compact.Substring($_ * 2,2) }) -join ':')
}
$addresses = @($addresses | Select-Object -Unique)
if ($addresses.Count -ne 1) { throw 'A single unambiguous target Bluetooth address is required.' }

$driverStore = Join-Path $env:SystemRoot 'System32\DriverStore\FileRepository'
$rules = @(
    @{ Prefix='surfacepro_ext_adsp8280'; Firmware='qcadsp8280.mbn' },
    @{ Prefix='surfacepro_ext_cdsp8280'; Firmware='qccdsp8280.mbn' },
    @{ Prefix='qcdx8280'; Firmware='qcdxkmsuc8280.mbn' }
)
$selected = @()
foreach ($rule in $rules) {
    $pattern = '^' + [Regex]::Escape($rule.Prefix) + '\.inf_arm64_[0-9a-f]{16}$'
    $packages = @(Get-ChildItem -LiteralPath $driverStore -Directory | Where-Object { $_.Name -match $pattern })
    if ($packages.Count -lt 1 -or $packages.Count -gt 8) { throw "Missing or excessive candidate packages for $($rule.Firmware)." }
    foreach ($package in $packages) {
        if ($package.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse driver package refused.' }
        foreach ($name in @($rule.Firmware, ($rule.Prefix + '.inf'), ($rule.Prefix + '.cat'))) {
            $file = Get-Item -LiteralPath (Join-Path $package.FullName $name) -ErrorAction Stop
            if ($file.PSIsContainer -or ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $file.Length -gt 33554432) {
                throw 'Unexpected driver package file.'
            }
            $selected += @{ Source=$file.FullName; Relative=('packages/' + $package.Name.ToLowerInvariant() + '/' + $name) }
        }
    }
}

# The output is intentionally private and never a public artifact input. Only
# this user, administrators and SYSTEM receive access, without inherited ACLs.
New-Item -ItemType Directory -Path $output | Out-Null
$acl = [Security.AccessControl.DirectorySecurity]::new()
$acl.SetAccessRuleProtection($true,$false)
$currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
foreach ($sid in @($currentSid, [Security.Principal.SecurityIdentifier]::new('S-1-5-18'), [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))) {
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
}
Set-Acl -LiteralPath $output -AclObject $acl
$hashes = [ordered]@{}
foreach ($entry in $selected) {
    $destination = Join-Path $output $entry.Relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath $entry.Source -Destination $destination -ErrorAction Stop
    $hashes[$entry.Relative] = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
}
$manifest = [ordered]@{
    format=1; model='Windows Dev Kit 2023'
    binding=@{kind='smbios-uuid-sha256-v1'; value=$binding}
    bluetooth=@{source='windows-device-address-cache'; address=$addresses[0]}
    files=$hashes
}
$json = $manifest | ConvertTo-Json -Depth 6
[IO.File]::WriteAllText((Join-Path $output 'manifest.json'), $json + "`n", [Text.UTF8Encoding]::new($false))
Write-Host 'Private target export complete. Catalog authentication is performed by ISO preparation next.'
Write-Host 'No raw UUID, registry hive, pairing keys or account data were exported.'
