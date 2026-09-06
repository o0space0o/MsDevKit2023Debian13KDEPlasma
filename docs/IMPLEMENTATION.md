# Implementation reference

DevKit2023CustomLinux 1.0.0. This describes the implemented source, not a promise
that every capability of the hardware has been validated. The owner accepted the
working edition; the runtime and pinned kernel are unchanged by repository cleanup.

## 1. Product and architecture

The target is Microsoft Windows Dev Kit 2023, board name Blackrock, using Qualcomm
SC8280XP (Snapdragon 8cx Gen 3 platform). The kernel boots ARM64 in EL1 with the
Blackrock device tree. This is not an x86 image and not a generic ARM computer ISO.

Userspace is Debian 13 Trixie ARM64 created by debootstrap minbase. Essential
KDE Plasma, KWin Wayland, SDDM, Dolphin, Konsole, NetworkManager, BlueZ, PipeWire,
WirePlumber and Calamares are installed without recommended optional packages.
Dependencies still bring many supporting libraries; minimal does not mean a
desktop can run without its normal services and libraries.

Debian repositories are Trixie, updates, security and backports. Qualcomm,
Atheros and Realtek firmware packages come from backports. Package versions are
not snapshot-frozen: a fresh build may contain newer Debian security updates.
The kernel, patch files, topology and security-sensitive verifier are pinned.
This is a source-controlled build recipe, not a byte-for-byte reproducible Debian
snapshot or a supported rolling kernel-update service.

## 2. Source and patch pins

The authoritative values live in scripts/lib/common.sh and are checked during
building. Three patch mailbox files apply four commits.

| Input | Pin or purpose |
| --- | --- |
| Kernel source | linux-next, tag next-20260902 |
| Kernel commit | 32b6ef9a5d0eca44f9cd91f52f4faa89f145a0de |
| Kernel release | 7.3.0-rc1-next-20260902-devkit2023customlinux |
| Device tree | sc8280xp-microsoft-blackrock.dtb |
| 20260825-blackrock-dp-audio-altmode-v2.mbox | Two commits: replace obsolete sound nodes with DP audio; enable four DP lanes on the board endpoints |
| 20250609-blackrock-usb0-mux-v1.mbox | Correct USB0 SBU-mux enable GPIO polarity for connector orientation |
| 20260902-buffer-fix-null-b-folio.mbox | Guard a NULL buffer folio during journal write submission |
| AudioReach topology | jglathe/audioreach-topology, commit 31e0451c67b9001b49118177617a3e8b7bbd4c5c |
| ALSA UCM routes | jglathe/alsa-ucm-conf, commit 77b4b779ab42cc37ddd18052732aa4dc1e3fb37e |
| Catalog verifier | osslsigncode 2.14, built from its hash-checked upstream archive |

The complete patch SHA-256 values are:

- DP/audio v2: 6c9d6cab985494ee4e90142c74ab6e85f62df4da59f17059feeb9b6ff55042bf
- USB0 mux: 380a6b885e23c607955e67b7c8cb36baff0b3c7dad0b099049f0899e94b43300
- Buffer fix: d469ac0df3a69765f3c5b1a1d45aaa5dded6c512f44a64ac332ca7f8e6a26ad9

These are a reviewed selection, not every LKML patch. The supplied August 23
audio link describes an earlier series; the checked-in **August 25 v2** is what
this project applies. Do not stack older versions of the same patch.

The buffer fix addresses the NULL-folio journal-write failure found during the
earlier isolated VM investigation. It is not claimed as an explanation of a
mini-DisplayPort signal-loss event.

## 3. Board support and dependencies

| Function | Implemented Linux path | Important dependency |
| --- | --- | --- |
| Display/GPU | DRM MSM, SC8280XP display clocks, Blackrock DTB | Authenticated target graphics firmware, early loading |
| DP audio | SC8280XP ASoC, QDSP6/AudioReach, ALSA UCM | Target ADSP firmware, board topology, DP sink |
| Wi-Fi | ath11k PCI, cfg80211/mac80211 | Packaged Atheros/Qualcomm firmware |
| Bluetooth | HCI UART QCA, btqca, BlueZ/Bluedevil | WCN6855 NVM selection and the target's public address |
| Ethernet | USB RTL8152 | Built-in Ethernet device and normal USB stack |
| USB | DWC3 Qualcomm, XHCI, Type-C/PMIC GLINK | Board mux GPIO, power, PHY and interconnect definitions |
| NVMe | Qualcomm PCIe, NVMe | Board regulators/clocks and GPT layout |
| Boot/storage | EFI, ext4, FAT, SquashFS/Zstd, OverlayFS | ARM64 EFI loader and matching initramfs |

config/kernel/blackrock.config enables the relevant Qualcomm pinctrl, PMIC,
regulators, remote processors, DMA, interconnects, clocks, PHYs and storage.
The kernel builder verifies the WCN6855 Bluetooth compatible, TLMM GPIO 133
Bluetooth enable, TLMM GPIO 100 active-low USB0 mux control, sound model,
four-lane DP endpoints, GPI DMA masks and board-ID-aware Bluetooth NVM selection.

The authoritative pin and endpoint mapping is the pinned kernel's Blackrock DTS
plus the checked-in patches. No guessed board wiring or manually invented
Bluetooth address is compiled into the DTB. Linux uses Linux drivers; the
exported Windows files are firmware, not Windows .sys driver execution.

## 4. Why prepared early boot matters

The boot sequence is deliberately ordered:

1. ARM64 UEFI loads GRUB and the Blackrock DTB.
2. GRUB supplies clk_ignore_unused and pd_ignore_unused. These retain clocks
   and power domains otherwise considered unused while this platform starts.
3. Automatic loading of msm, qcom_q6v5_pas and snd_soc_sc8280xp is blacklisted.
   This prevents those drivers starting before the prepared firmware checks.
4. The initramfs hook checks Blackrock compatibility, the hashed SMBIOS binding
   and firmware integrity before normal live-storage discovery.
5. After successful checks it explicitly loads those three modules. It clears
   inherited MODPROBE_OPTIONS for these deliberate loads and checks that each
   module actually appeared in sysfs. A successful command alone is insufficient.
6. System services revalidate the prepared data and sequence display, audio,
   Bluetooth address provisioning and the desktop.

The deliberate module loading does not bypass firmware authentication.
The public base lacks a target binding and therefore stops before hardware
startup. A wrong-target image stops too; it does not proceed with substitutes.

The topology is included at the kernel-requested location:
usr/lib/firmware/qcom/sc8280xp/SC8280XP-MICROSOFT-BLACKROCK-tplg.bin,
both in the root filesystem and early image. Firmware copied only after the
desktop starts would be too late for this workflow.

efi=noruntime is not a default. It disables EFI runtime access needed by the
installer's boot-entry step. It is not a universal display fix. Secure Boot is
unsupported because the custom boot chain is unsigned.

## 5. Firmware preparation and privacy

The explicit Windows exporter collects exactly three firmware payloads:
qcadsp8280.mbn, qccdsp8280.mbn and qcdxkmsuc8280.mbn, with their original INF and
CAT evidence. It does not copy the full DriverStore, Windows drivers, user files,
registry hives, recovery keys, credentials or accessory pairing secrets.

The preparer independently verifies Microsoft catalog signatures and exact
SHA-256 membership of both INF and MBN. Digestless catalog entries do not qualify.
The highest authenticated DriverVer wins; conflicting same-version material is
rejected. Only the three selected packages, nine evidence/payload files, are
embedded and reverified. Another board's Lenovo SC8280XP firmware directory is
removed from the generic base so it cannot substitute for Blackrock firmware.

The export holds a SHA-256 binding to the target's canonical SMBIOS UUID and its
built-in Qualcomm Bluetooth factory public address. Missing or ambiguous identity
fails; no disk/MAC/other-machine identity is substituted. A stable hash is still
an identifier, not anonymity or hardware attestation.

The prepared ISO contains this private target material. The public source and
temporary generic base do not. The collection/preparation protocol is
prepared-workflow-v1. See PREPARATION.md for its exact binding format.

## 6. Bluetooth: the actual repair

The pinned kernel already has the QCA UART driver and board-ID-based WCN6855 NVM
selection. This project does not add an arbitrary old Bluetooth patch on top.

At boot the helper finds exactly one built-in WCN6855 controller through its
device-tree ancestry, rather than assuming every hci0 is the right device. It
unblocks that controller only, verifies the management reply, and provisions the
prepared target's address only when the controller is positively identified as
unconfigured and missing its public address.

A controller already configured with another address is rejected. Pairing keys
are not imported or synthesized. BlueZ is ordered after address provisioning.

The userspace service repair supplies an empty input **pipe** to btmgmt. The
BlueZ 5.82 shell path used here registers stdin with epoll; systemd's /dev/null
can prevent the command from reaching the controller. The helper uses bounded
timeouts, validates replies even after exit status zero, and handles the global
unconfigured-controller list correctly. This is distinct from a missing kernel
driver or replacing firmware.

A connected Bluetooth speaker was observed. That does not establish every phone
profile, accessory, range, reconnect or simultaneous-radio case.

## 7. Audio, search, Chrome and support tools

The DP audio patches, target ADSP firmware, AudioReach topology and Blackrock UCM
routes provide the board's audio path. PipeWire/WirePlumber expose it to KDE.
The KDE speaker-test popup saying No such driver was a missing libcanberra Pulse
backend: libcanberra-pulse is now explicitly installed. It was not proof that
Bluetooth's kernel driver was missing.

Dolphin's Invalid protocol filenamesearch error was a missing KIO worker.
kio-extras is explicitly included, and image verification checks its worker file.
No manual APT update is required for these delivered components.

Chrome is optional. The desktop installer downloads Google's signing key,
accepts only the pinned primary fingerprint
EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796 and its subkeys, scopes it to the official
ARM64 APT repository, and installs current stable google-chrome-stable:arm64.
The binary and repository key are not prebundled. Upstream key rotation may
require a reviewed installer update; signature failures are not bypassed.

Diagnostics 1.4 is a permanent, optional product support tool, not a directory
of development checkup files. Its hidden implementation presents a KDE progress
dialog, redacts selected identifiers and offers a text report/viewer. No report
exists in a fresh image until the user requests one. Tests and project documents
are not copied into the live overlay.

## 8. Installation implementation

The single windows-free-space-v1 policy uses existing unallocated space on one
internal Windows GPT NVMe disk. It has no erase/replace/resize paths. Read-only
preflight checks the target, readiness, EFI runtime, Secure Boot state, existing
partitions, EFI free space and absence of ambiguous/mounted layouts.

The normal-user launcher receives a readable plan summary over the authorized
preflight's stdout. Root-owned JSON and Calamares summary cache remain mode 0600.
Private-log umask is reset to 022 before privileged children run. Errors retain
the real exit status and offer Open log. Calamares uses the packaged executable
with its existing policy authorization, XCB and restricted temporary root display
access. The branding slideshow is a supported image list.

Before writing, the backend rechecks disk identity, complete GPT, original EFI
file hashes and boot variables. It appends only the new Linux partition, disables
signature wiping for existing devices, formats only that new ext4 partition and
verifies Calamares's mount targets.

Target firmware/address records and early boot data are transferred into installed
Linux. No live pairing keys are copied. The user's account is created during setup.
GRUB is installed under EFI/DevKit2023CustomLinux without overwriting Microsoft
or fallback EFI files. A Linux boot entry is added while original entries and
relative ordering are preserved. Linux and Windows get explicit GRUB entries.

A partial write is not automatically rolled back or blindly retried. Recovery
media and backups remain necessary. Full safeguards and maintainer entry points
are in INSTALLATION.md.

## 9. Clean Windows build and repository organization

The supported launcher always makes a fresh native Linux workspace. Source is
copied from the explicit project inventory, never by copying arbitrary root
contents. Temporary public-base/manifests/checksums are used internally for
verification; the selected target is then prepared in a private mount namespace.

Windows checks the preparation completion metadata and copied ISO bytes before
atomically publishing only ISO/DevKit2023CustomLinux-1.0.0-arm64.iso. Replacing an
existing image requires confirmation; it is not removed before the new image is
ready. The final source/ISO folders contain no automatic build logs or history.

Normal completion and handled failures clean the run's native and Windows
temporary directories. An interrupted-build cleanup action recognizes private
ownership records, refuses active builds and linked/unexpected paths, and never
deletes external bundles or the installed WSL distribution. Power loss can
interrupt cleanup; prerequisites and normal OS metadata are not build outputs.

The repository's explicit file map rejects unmapped content, stale indexes,
missing service executables and private payload extensions. ISO is intentionally
excluded from source and Git. Only the named public guide PDF is allowed as a
document asset. Synthetic tests remain maintenance source, not old build history.

This cleanup preserves the accepted ISO byte-for-byte. It does not rebuild,
upgrade or change the running board support. New build orchestration was reviewed
with static checks only, at the owner's request; a fresh full build was not
repeated for this handoff.

## 10. Sources and scope

Primary source links and version context are in [UPSTREAM.md](UPSTREAM.md).
The checked-in patch files retain their upstream authorship and notices. MIT
covers project-authored code, not all software inside an assembled ISO.

There is no bundled custom Windows, no Chrome binary, no public private-firmware
release, no blanket all-drivers certification and no promise of unattended
installation on every Windows partition layout. Suspend/resume, NPU, hardware
video codecs, EL2/KVM and Secure Boot are outside the claimed release scope.
