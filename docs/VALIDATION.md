# Release scope and evidence

DevKit2023CustomLinux 1.0.0 is the definitive project baseline accepted by its
owner on 6 September 2026. No further manual testing is requested for this
handoff. This page records scope, not a new checklist blocking delivery.

| Area | Implemented / observed | Limit |
| --- | --- | --- |
| KDE and miniDP | Working live desktop observed on the reference kit | Not every display, USB-C adapter or hotplug case |
| Wi-Fi and USB | Wi-Fi and normal USB peripherals used | Not a full throughput/all-port matrix |
| Audio | Ordinary audible playback observed; DP audio/topology/UCM and KDE test backend included | Every output/profile is not separately established |
| Bluetooth | Factory-address provisioning; speaker connection observed | Phone profiles, long range and every reconnect case not certified |
| Installation | Enabled free-space-only Windows-alongside installer; owner accepted working edition | No separately supplied installed dual-boot test record |
| Firmware | Signed catalog/member checks and per-target binding | Must export from each intended kit; not transferable |
| Other Dev Kits | Same source and explicit independent preparation | No second physical kit result supplied |
| Build cleanup | Fresh temporary build, ISO-only publication and guarded cleanup implemented | Static review only for this workflow revision |
| Documentation | Beginner guide, PDF and technical implementation reference | Updates needed if source/support scope changes |

## Not claimed

Suspend/resume, hardware video codecs, NPU/compute, EL2/KVM and Secure Boot
support are not part of the claimed release. The image boots EL1 and is unsigned.
This project is not a promise of safe installation on an arbitrary Windows
partition layout or of zero Windows recovery prompts.

The installer supports one internal Windows GPT NVMe disk, existing unallocated
space, an existing ARM64 Windows EFI partition and no previous Linux partition.
Unsupported layouts stop rather than falling back to erase/resize operations.

## Ongoing integrity, not repeated acceptance

Build-time source, signature, target and image checks remain enabled. These
protect against incomplete images or wrong-target material; owner acceptance is
not a reason to remove them. Maintainer regression tests stay in source and CI,
never in the live desktop filesystem.

Future substantial driver/kernel/installer changes need their own evidence.
Static checks and QEMU cannot establish Qualcomm hardware behavior or physical
Windows recovery behavior. Do not convert untested items into pass labels.

The boot defaults retain clk_ignore_unused and pd_ignore_unused. Do not add
efi=noruntime for installation: the boot-entry step needs EFI runtime services.

Raw reports and prepared images are private. Source documentation summarizes
behavior without device addresses, account paths, registry data or pairing keys.
