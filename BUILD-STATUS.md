# Release status

DevKit2023CustomLinux 1.0.0 - definitive project baseline, 6 September 2026.
Preparation format: prepared-workflow-v1. Installer: windows-free-space-v1.

## Current delivery

The owner reported that the current edition was working and requested a clean
final project without further testing. The accepted ISO has been preserved
byte-for-byte in ISO/DevKit2023CustomLinux-1.0.0-arm64.iso.

This handoff changes Windows build orchestration, output cleanup and public
documentation. It does not change the live/installed overlay, board drivers,
kernel, DTB, Bluetooth helper, sound configuration or installer policy.

The old Data folder is not part of the new layout and is never used as input.
Its deletion was blocked by this session's execution policy, so that obsolete
Windows folder remains for the owner to remove manually after confirming the
ISO copy. The old native WSL build/artifact/private trees and the old UCM test
directory were removed permanently. Source and the ignored ISO folder are the
only active project/output trees.
The generated page previews also remain in the Windows temporary directory
DevKit2023CustomLinux-guide-review-20260906 because their cleanup was blocked by
the same execution policy. They are outside source and are not build inputs.
Future normal Windows builds publish only the finished target-prepared ISO;
intermediate data is temporary. An explicitly requested export-only transfer
bundle remains at the location chosen by its owner.

## Evidence boundary

The working reference has demonstrated KDE through miniDP, Wi-Fi, audible audio
and a Bluetooth speaker connection. Earlier source checks, synthetic tests,
image verification and isolated installer/filename-search VM checks were passed
during implementation. Those checks are not being represented as fresh results.

The latest owner acceptance does not supply a separate per-port, installed
dual-boot or second-kit test record. No such results are invented. This is a
community project release, not a certified hardware support guarantee.

No additional hardware, QEMU or full compilation was run for the cleanup handoff,
as requested. Changed files receive syntax, inventory, documentation and privacy
checks; the guide is rendered and visually reviewed. The new from-scratch
orchestration is not claimed to have completed a fresh end-to-end run.

Cleanup handoff checks completed:

- Source inventory, public-payload rules, local documentation links and shell
  syntax passed: 133 mapped files across 14 components.
- All PowerShell scripts parsed; 25 Python files passed syntax parsing.
- The 15-page PDF was rendered and every final page visually reviewed. It has
  linked contents/references and no embedded attachments; checked private
  identifiers and builder paths were absent from its extracted text.
- The final ISO copy matched the accepted image's SHA-256. Only that ISO is in
  ISO/; its private identity and checksum are not embedded in public documents.
- No new unit, hardware, QEMU or end-to-end build tests were run for this handoff.

Git publication uses only the explicit 133-file public inventory. The entire
ISO directory is ignored. PDF files are marked binary so Git cannot rewrite
their line endings; executable scripts retain their executable mode. The
publication regression assertion was added without running another test suite.

## Frozen board baseline

- Kernel: next-20260902, commit 32b6ef9a5d0eca44f9cd91f52f4faa89f145a0de.
- Release: 7.3.0-rc1-next-20260902-devkit2023customlinux.
- Three mailbox patch files / four applied commits, listed in
  [IMPLEMENTATION.md](docs/IMPLEMENTATION.md).
- Kernel bytes SHA-256: 52bfbcf6a9df69259cbc4bd54da831a4eaa7b086a69db135e6ffaaedc5ba0a2e.
- Blackrock DTB SHA-256: 59a9324cd338b03c567c4ec6773ed0b20f4f9306f6f45549e4734bbb2377ee01.
- Normal boot retains clk_ignore_unused and pd_ignore_unused.
- EFI runtime remains available; efi=noruntime is not an installation default.
- Firmware signature/member checks and target-bound Bluetooth identity are unchanged.

Package repositories can advance; rebuilding later does not promise identical
Debian package versions or ISO bytes. The current accepted image is not rebuilt
merely to reorganize its source folder.

Read [SETUP.md](SETUP.md) for use, [release scope](docs/VALIDATION.md) for limits,
and [implementation reference](docs/IMPLEMENTATION.md) for the complete design.
Publish source only; keep the contents of ISO private.
