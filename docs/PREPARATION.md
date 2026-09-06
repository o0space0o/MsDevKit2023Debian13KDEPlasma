# Windows preparation contract

Status: definitive 1.0.0 owner-accepted baseline. KDE, audible audio, Wi-Fi and
a Bluetooth speaker connection were observed. The free-space-only installer is
enabled. See VALIDATION.md for evidence limits; no further tests are requested
for this handoff.

## Internal stages and final image

| Product | Contents | Sharing rule |
| --- | --- | --- |
| Public source / temporary base | Code, Linux drivers, generic packaged firmware; no target identity or Windows firmware | Publish source; base is an internal stage |
| Temporary target bundle | Selected firmware, INF/CAT evidence, hashed binding and Bluetooth address | Removed after normal build; explicit transfer exports remain user-owned |
| Final prepared ISO | Validated target material and early-boot firmware | Only normal build output, in ISO; private and target-specific |

The base may be built elsewhere. Collection runs on the intended Dev Kit.
Preparation elsewhere requires its explicitly selected bundle. There is no
default-to-builder, cached-other-kit or generated-address fallback.

## Collection allowlist and evidence

Only three payloads and their corresponding INF/CAT evidence are collected:
`qcadsp8280.mbn`, `qccdsp8280.mbn`, `qcdxkmsuc8280.mbn`. Linux uses its own
drivers, not copied Windows `.sys` drivers. CDSP inclusion does not claim NPU or
compute support. The export contains no full DriverStore tree, registry hive,
account data, Wi-Fi credentials, pairing database or recovery keys.

The exporter hashes the allowlisted files. The Linux preparer separately verifies
Microsoft catalog signatures and exact unambiguous SHA-256 INF/MBN membership.
Digestless catalog entries are not hash evidence. The highest authenticated
DriverVer wins; conflicting firmware at the same version is rejected. Only the
selected three packages (nine files) are embedded and reverified.

The target binding is SHA-256 over this UTF-8 text, including its final newline:

```text
DevKit2023CustomLinux target v1
smbios-uuid
<canonical-lowercase-hyphenated-SMBIOS-UUID>
```

The bundle stores the hash, not the raw UUID. Windows reads
Win32_ComputerSystemProduct.UUID; Linux reads the DMI product UUID. There is no
switch to a disk, MAC or other identifier when DMI is missing. Missing/zero/all-F
UUIDs are rejected. Windows/Linux matching worked on the reference kit; another
kit still needs its own test. A hash is a stable identifier, not anonymous information or a
hardware attestation/anti-tamper mechanism.

Bluetooth comes only from the built-in Qualcomm UART controller's Windows
DeviceAddressCache. Multiple different addresses, unsupported encodings or an
invalid public address fail. No pairing secrets are read. Windows must have
initialized that controller; this is not a guarantee for an unconfigured
factory-fresh Windows image.

## Prepared boot

Preparation embeds authenticated firmware in both the root filesystem and its
initramfs, checks the finished ISO by extracting it, and publishes a manifest only
after verification. Completion metadata is checked internally before only the
final ISO is published. The temporary base and evidence files are then removed.
Blackrock's public AudioReach topology is also copied into the early boot image
at the exact kernel-requested path and included in its integrity record.

Before live storage discovery, the early hook checks Blackrock compatibility,
DMI binding and firmware hashes, then explicitly loads the required modules.
Mismatch stops that boot stage without returning to continue initialization.
At system startup the prepared service rechecks catalog evidence and target
binding before display/audio/Bluetooth services. The Bluetooth helper operates
only on the built-in controller and refuses to replace a different configured
public address. This is address provisioning, not proof of pairing success.

The codebase has no Linux-time Windows import, USB cache/reboot or offline registry
reader. The public base uses the same prepared runtime but contains no target
records, so it deliberately stops with preparation instructions. Only a matching
current-source base can be prepared; old base formats are rejected.

## Limits

The narrow Windows-preserving disk plan only creates a new Linux root in
unallocated space. Target, mount, GPT
and EFI checks remain mandatory. See [the installer reference](INSTALLATION.md).
Do not bypass checks to install an unsupported layout. Installed hardware boot
and Windows reboot are not established by the disk-image and synthetic tests.

The unsigned ISO is not a secure-boot trust chain. Local manifest hashes do not
authenticate an untrusted base, prove device ownership, or grant redistribution
rights over proprietary firmware. Keep target bundles and prepared ISOs private.
A second kit must be separately exported and prepared. BitLocker/EFI
recovery safety is independent of firmware acquisition.

Upstream context:
[Windows-side Blackrock firmware collection](https://github.com/jglathe/wdk2023_fw_fetch),
[Microsoft SMBIOS UUID documentation](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-computersystemproduct).
