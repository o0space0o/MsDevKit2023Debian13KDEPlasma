# Upstream sources and provenance

Reference date: 6 September 2026. The implementation reference records exactly
what this project uses; a linked repository is not automatically imported in
full. Read the checked-in pins before adopting a newer upstream change.

## Hardware and boot

- [Microsoft Windows Dev Kit 2023 guide](https://learn.microsoft.com/en-us/windows/arm/dev-kit/): target platform, miniDP pre-boot display, UEFI and USB boot.
- [Jens Glathe's Linux Dev Kit repository](https://github.com/jglathe/linux_ms_dev_kit): Blackrock platform development and wider Qualcomm context. This project builds its own pinned linux-next selection, not that repository's current moving branch.
- [Linux Surface organization](https://github.com/linux-surface): related community context, not a blanket dependency or source of every driver in this image.
- [Kernel parameter reference](https://www.kernel.org/doc/html/latest/admin-guide/kernel-parameters.html): clock/power-domain controls and EFI runtime semantics.
- [Pinned linux-next source](https://kernel.googlesource.com/pub/scm/linux/kernel/git/next/linux-next.git/+/32b6ef9a5d0eca44f9cd91f52f4faa89f145a0de): base for the source-built kernel.

## Exact patch selection

- [Original DP audio and four-lane discussion](https://lkml.iu.edu/2608.2/12170.html): August 23 cover letter supplied during research. This is background; the project applies the August 25 v2 mailbox.
- [DP audio v2](https://lore.kernel.org/all/20260825-blackrock-audio-v2-1-659cc4724d57@oldschoolsolutions.biz/): Jens Glathe, replace obsolete sound nodes and enable DP audio; the local mailbox also contains the second four-lane altmode commit.
- [USB0 mux correction](https://lore.kernel.org/all/20250609-blackrock-usb0-mux-v1-1-7903c3b071e4@oldschoolsolutions.biz/): Jens Glathe, USB0 enable GPIO polarity. Canonical message IDs are retained in the checked-in mailbox even when an archive is unavailable.
- [NULL buffer-folio fix](https://lkml.iu.edu/2609.0/02958.html): Joseph Qi, guard the folio check in journal write submission.
- [AudioReach topology pin](https://github.com/jglathe/audioreach-topology/tree/31e0451c67b9001b49118177617a3e8b7bbd4c5c): Blackrock topology used by the build.
- [ALSA UCM pin](https://github.com/jglathe/alsa-ucm-conf/tree/77b4b779ab42cc37ddd18052732aa4dc1e3fb37e): board audio routes; the source notice and BSD-3-Clause license are retained under the overlay.

The local patch files and hashes in scripts/lib/common.sh are authoritative for
this edition. The two lore message pages were not retrievable by this session's
browser; their provenance comes from the retained original mailbox headers.
No extra legacy Bluetooth patch is applied: the pinned kernel already contains
the required board-ID firmware selection checked by the build.

## Firmware and Bluetooth

- [Windows-side Blackrock firmware collection](https://github.com/jglathe/wdk2023_fw_fetch): device-community reference for Windows firmware acquisition.
- [Microsoft SMBIOS UUID documentation](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-computersystemproduct): identity property used for target binding.
- [osslsigncode 2.14](https://github.com/mtrojnar/osslsigncode/tree/2.14): pinned catalog verification implementation.
- [BlueZ 5.82 shell](https://github.com/bluez/bluez/blob/5.82/src/shared/shell.c): stdin/event-loop behavior relevant to the service command pipe.
- [BlueZ management API](https://github.com/bluez/bluez/blob/5.82/doc/mgmt-api.txt): controller configuration/public address operations.

Our helper's input-pipe correction and explicit reply validation are project
userspace integration, not a claim that the kernel Bluetooth driver is replaced.

## Desktop and installer

- [KDE 6.3.4 speaker test](https://github.com/KDE/plasma-pa/blob/v6.3.4/src/speakertest.cpp): the libcanberra Pulse backend used by the test buttons.
- [Debian libcanberra-pulse](https://packages.debian.org/trixie/libcanberra-pulse): explicit package needed for that backend.
- [Debian kio-extras](https://packages.debian.org/trixie/kio-extras): filename-search worker and related KIO components.
- [Calamares 3.3.14 branding](https://github.com/calamares/calamares/blob/v3.3.14/src/branding/default/branding.desc): slideshow/image-list contract.
- [Calamares mount job](https://github.com/calamares/calamares/blob/v3.3.14/src/modules/mount/main.py) and [fstab job](https://github.com/calamares/calamares/blob/v3.3.14/src/modules/fstab/main.py): integration used after the project's guarded partition plan.
- [sfdisk reference](https://man7.org/linux/man-pages/man8/sfdisk.8.html): GPT operations used by the narrow storage backend.

## Windows setup, USB and Chrome

- [Microsoft WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install) and [command reference](https://learn.microsoft.com/en-us/windows/wsl/basic-commands): setup, distribution installation and WSL 2.
- [Rufus official downloads](https://rufus.ie/en/): choose Windows ARM64 and check the USB target before writing.
- [Google Chrome installation requirements](https://support.google.com/chrome/answer/95346?hl=en-GB): Linux ARM64 support.
- [Google Linux repositories](https://www.google.com/linuxrepositories/): official package/key distribution.

Chrome remains an optional current-stable download. Its earlier successful
isolated package installation is not a GPU/browser hardware test. The current
working ISO is retained; this documentation does not mean the repositories or
drivers were upgraded during cleanup.
