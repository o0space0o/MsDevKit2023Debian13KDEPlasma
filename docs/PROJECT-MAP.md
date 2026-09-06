# Project map

There is one preparation workflow. Source and the reusable base are public;
target exports and prepared images are private.

```mermaid
flowchart TD
  S[Public source and pinned patches] --> B[Windows launcher / native ARM64 builder]
  B --> R[Automatic WSL readiness / setup]
  R --> A[Temporary target-free base ISO]
  W[Intended Dev Kit running Windows] --> E[Explicit firmware and identity export]
  E --> V[Catalog signatures, member hashes and target validation]
  A --> P[Private ISO preparation]
  V --> P
  P --> U[ISO folder: one private finished image]
  U --> X[Remove owned build intermediates]
  U --> I[Authenticated early firmware and target-bound boot]
  I --> D[KDE desktop / audio / Wi-Fi / Bluetooth]
  D --> C[Optional Chrome installer and Diagnostics]
  D --> F[Read-only target check and free-space plan]
  F --> Q[User confirms installation]
  Q --> L[New Linux root / preserved Windows EFI and partitions]
  L --> T[Linux and preserved Windows boot choices]
```

The public base intentionally stops before hardware startup if it has not been
prepared. No Windows volume scan or firmware-cache reboot is part of Linux boot.

The root is the only public source tree. The one end-user guide is
[SETUP.md](../SETUP.md). The only normal build output is the finished private
image in the ignored `ISO/` folder. Source mirrors, generic bases, target exports
and manifests are temporary build data, removed by the managed run. There is no
separate Data folder or old-build history. Explicit transfer exports remain
user-owned; they are never discovered as implicit inputs.

| Component | Main source |
| --- | --- |
| Windows launcher, WSL, target export | `Start-DevKit2023CustomLinux.cmd`, `windows/` |
| Pinned kernel and patch hashes | `scripts/lib/common.sh`, `scripts/build-kernel.sh`, `config/kernel/`, `patches/` |
| Debian/KDE base and ARM64 ISO | `scripts/build-rootfs.sh`, `scripts/build-iso.sh` |
| Shared desktop, drivers and branding | `overlay/` |
| Target-bound runtime and early loading | `profiles/prepared/overlay/` |
| Authenticated private preparation | `scripts/prepare-iso.py`, shared catalog validator |
| Source/base/prepared verification | `scripts/check-source.py`, `scripts/verify-base.py`, `scripts/verify-prepared-iso.py`, `tests/` |
| Free-space installation and target handoff | `overlay/etc/calamares/`, `install_policy.py`, `devkit2023customlinux-install-storage`, prepared install-preflight |
| User support | [Diagnostics](TESTER.md), [upstream evidence](UPSTREAM.md) |
| Technical reference | [Implemented software, patches and safeguards](IMPLEMENTATION.md) |

The [file index](FILE-INDEX.md) names every file using
[config/project-map.json](../config/project-map.json). Unregistered files,
private payloads and stale local links fail the source checker.

For no signal, follow boot parameters → early firmware result → display readiness.
For Bluetooth, distinguish address provisioning, discovery, pairing and actual
connection. For installation, inspect the final disk plan rather than inferring
safety from a working live desktop.
