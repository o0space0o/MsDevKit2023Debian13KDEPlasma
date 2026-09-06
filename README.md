# DevKit2023CustomLinux

Version 1.0.0 - minimal KDE Plasma for Microsoft Windows Dev Kit 2023
(Blackrock / Qualcomm SC8280XP).

A Debian 13 ARM64 derivative with a source-built, pinned and patched kernel.
This is a complete build project, **not Linux From Scratch userspace** and not
just an ISO repacker.

## Start here

Double-click [Start-DevKit2023CustomLinux.cmd](Start-DevKit2023CustomLinux.cmd).
Choose **Build an ISO for THIS Dev Kit (recommended)**.
The launcher handles WSL setup, a fresh base build, explicit target preparation
and cleanup. If Windows needs a restart, restart and open the same launcher.

Read [SETUP.md](SETUP.md) for the step-by-step tutorial, also available as the
[complete PDF guide](docs/DevKit2023CustomLinux-Guide.pdf).

The only normal build output is:

```text
ISO/DevKit2023CustomLinux-1.0.0-arm64.iso
```

There is no separate Data directory, retained base image, source archive, build
history or reusable build cache. Intermediate files are temporary. WSL and its
installed build tools remain available for the next build.

## The edition

The current working image is retained unchanged following the owner's acceptance.
KDE, mini-DisplayPort, Wi-Fi, audible audio and a Bluetooth speaker connection
have been observed on the reference kit. The desktop includes:

- **Install DevKit2023CustomLinux**: guided installation into existing free space.
- **Install Google Chrome**: optional download from Google's signed ARM64 repository.
- **Diagnostics**: optional user-initiated report, with Konsole and essential KDE tools.

The installer preserves Windows partitions and reuses the EFI partition without
formatting it. It does not shrink Windows, erase a disk or replace an existing
Linux installation. Backups and recovery access are still necessary.

This is the project's definitive 1.0.0 baseline, not a certification of every
port, accessory or other kit. [Release scope](docs/VALIDATION.md) and
[current evidence](BUILD-STATUS.md) state the limits. There is no additional
hardware/QEMU testing requirement imposed by this handoff.

## Public project, private ISO

**Publish the source, not the contents of ISO.** Git excludes the entire ISO
folder. A prepared image contains the selected kit's proprietary firmware,
Bluetooth address and hashed target binding. It must not be uploaded to GitHub
or used on a different kit. The public source contains none of these records.

Another Windows Dev Kit 2023 uses the same source and launcher but exports its
own data. A freshly installed Windows must first have its proper OEM drivers
and an initialized built-in Bluetooth controller. No other-device, cached or
generated-address fallback exists.

## Find anything in the project

- [Project map](docs/PROJECT-MAP.md): connected workflow and component ownership.
- [Implementation reference](docs/IMPLEMENTATION.md): software, patches, drivers and safeguards.
- [Preparation contract](docs/PREPARATION.md) and [installer design](docs/INSTALLATION.md).
- [Developer workflow](docs/WORKFLOW.md), [file index](docs/FILE-INDEX.md) and [upstream sources](docs/UPSTREAM.md).
- [Contributing](CONTRIBUTING.md), [security/privacy](SECURITY.md) and [license](LICENSE).

Project-authored build code is MIT-licensed. Linux, KDE, Debian packages,
firmware and upstream patches retain their own licenses. This source release
does not grant redistribution rights for a target-prepared ISO.
