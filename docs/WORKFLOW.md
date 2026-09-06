# Developer workflow

The end-user entry point is Start-DevKit2023CustomLinux.cmd and
[SETUP.md](../SETUP.md). There is one build/preparation path, not separate legacy
and recovery ISO variants.

## Windows entry points

The guided UI calls Build-DevKit2023CustomLinuxISO.ps1, a thin public entry point
into Prepare-DevKit2023CustomLinux.ps1. Target selection is mandatory:

```powershell
.\windows\Build-DevKit2023CustomLinuxISO.ps1 -TargetThisDevice
```

For a bundle explicitly exported elsewhere:

```powershell
.\windows\Build-DevKit2023CustomLinuxISO.ps1 -TargetBundle 'D:\Private\target-bundle'
```

Use -ReplaceExisting only after deliberately approving replacement of the
current version ISO. No previous backup is retained after successful replacement.

Export-only is an explicit transfer operation, not an automatic build output:

```powershell
.\windows\Export-DevKit2023Target.ps1 -TargetThisDevice -OutputDirectory 'D:\Private\target-bundle'
```

A compatible Debian 13 ARM64 WSL 2 builder is established before compiling.
No existing distribution is deleted or silently upgraded. Setup may require a
Windows restart; reopen the same launcher. No autorun/scheduled task is added.
The WSL installer, Debian packages and compiler tools remain installed.

## Lifetime of one build

1. Windows allocates a fresh ACL-restricted temporary directory with a private
   ownership record and explicit target bundle, if collecting on this target.
2. WSL allocates one fresh root-owned native directory below /var/tmp.
3. The bootstrap runs in a private mount namespace, takes a build lock and copies
   only config/project-map.json's public source inventory.
4. build.sh creates the pinned kernel, minimal Debian rootfs and generic base.
   Source checks/tests and image verification run; no source archive is emitted.
5. prepare-iso.py authenticates the explicitly selected bundle, adds early
   firmware/binding, repacks and verifies the target image.
6. Completion metadata is copied to the Windows temporary directory and checked.
   Only the final ISO is published to the project ISO folder. Its copied hash
   must match before a same-volume atomic rename/replacement.
7. Finally/EXIT handlers remove the run's temporary native/Windows material.
   An existing ISO stays intact until a successful replacement is ready.

No previous base or hidden cached target is selected. The accepted image in ISO
does not become an input to future builds. Private payloads never enter the
source inventory or generic base. Manifests/checksums still serve as internal
verification records, but are not retained as extra normal output files.

## Interrupted cleanup

The Windows ownership record holds only the temporary paths, owner/process
information and selected distribution. It is never put in source or the ISO.
The launcher cleanup action filters exact product names, source/owner identity
and process lifetime; it skips a live process. Native cleanup also requires an
unlocked build directory, exact canonical path and root ownership. It refuses
links, unexpected paths and busy mounts rather than deleting a broader tree.

A power cut or forced kill can prevent handlers running. The explicit cleanup
action handles recognized interrupted runs once no build is active. Unmarked
or unexpected files are not guessed at or recursively swept away. Normal OS
logs, package manager metadata, WSL and external transfer bundles are outside
the disposable build scope. Deleting Linux files does not guarantee immediate
Windows VHDX shrinking.

## Maintainer tools

The lower-level build.sh and scripts are components of the managed build.
Calling individual stages manually makes the maintainer responsible for their
explicit staging/output directory and cleanup. The Windows launcher is the
supported ISO-only end-user workflow.

Synthetic tests are maintenance source, not leftovers. They do not use real
Windows partitions, EFI variables or real firmware/identity fixtures.

```sh
python3 -B scripts/check-source.py --shell
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

Windows maintainer checks: parse the PowerShell files and optionally run
tests/windows-launcher-tests.ps1. These commands are not extra end-user setup
steps. No additional test suites were run for this final cleanup at the owner's
request. CI remains available for later contributions.

Source-only packaging is an explicit maintainer operation, not part of normal
ISO output. scripts/package-source.sh uses the exact inventory and excludes ISO.
The optional GitHub build job produces a target-free base, not a prepared image;
it cannot collect or supply another kit's private firmware.

The guide PDF is generated from SETUP.md, IMPLEMENTATION.md and UPSTREAM.md using
scripts/build-guide.py (reportlab), with rendering review before publishing.
Update the map/index when adding or removing a source/document asset.

[Project map](PROJECT-MAP.md), [installer design](INSTALLATION.md) and
[release scope](VALIDATION.md) are the connected implementation references.
