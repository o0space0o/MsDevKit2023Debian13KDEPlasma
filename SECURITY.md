# Security and privacy

This is a community 1.0.0 source release, not a vendor-certified distribution. No security
update SLA or guarantee of safe installation is offered. Do not bypass the
installation safety checks. Keep Windows backups and recovery media.

Report suspected bugs without attaching a private prepared ISO, DriverStore
bundle, registry hive, machine identifier, Bluetooth address or pairing keys.
Review even redacted diagnostic reports before sharing. For a sensitive report,
use GitHub private vulnerability reporting if the eventual repository enables
it; do not place sensitive details in a public issue. No reporting account or
repository URL is invented in this source package.

Prepared firmware is authenticated against pinned Microsoft public trust roots;
catalog member hashes and target binding are checked. This is not Secure Boot:
the custom EFI loader/kernel are unsigned. Chrome is optional and downloaded
from Google's signed ARM64 repository only after user confirmation.
