# Windows-preserving installer

The end-user instructions are in [SETUP.md](../SETUP.md). This file explains the
single `windows-free-space-v1` implementation for maintainers in the definitive
owner-accepted 1.0.0 baseline. Scope is recorded in VALIDATION.md; the owner's
acceptance is not a separately supplied installed dual-boot test record.

## One disk plan, not general-purpose partitioning

The desktop launcher authorizes a read-only preflight. The prepared bundle is
authenticated again, matched to this Blackrock, and display/audio/Bluetooth
readiness is checked. EFI runtime services and Secure Boot disabled are required.
There must be exactly one non-removable NVMe disk with Windows GPT/MSR/EFI layout,
an ARM64 Windows Boot Manager, no existing Linux/unknown partition, no active
mounts/holders, and at least 32 GiB of aligned unallocated space.

`install_policy.py` creates one plan: add one ext4 root in the largest suitable
gap. It retains every original partition field. The user sees the disk/size and
EFI reuse before Calamares asks for account settings and final confirmation.
The native Calamares partition view/job and generic bootloader job are not in the
sequence. There is no hidden erase, replace or resize alternative.

The human-readable summary returns on the authorized preflight's standard output
to the normal-user launcher. It is not saved to a desktop-readable file or startup
log. The authoritative JSON transaction and Calamares's text-summary cache remain
root-owned mode 0600. This avoids an
inherited restrictive umask preventing the desktop from reading its summary;
never loosen JSON permissions or bypass preflight to work around this boundary.
Startup errors offer a log viewer; Diagnostics extracts bounded technical errors.

The privileged `install-storage` backend then:

1. Revalidates target, disk identity, complete GPT snapshot, original EFI file
   hashes and boot variables. A stale plan stops before any write.
2. Appends exactly the planned partition, with signature wiping disabled; checks
   every original GPT field and new kernel partition mapping; formats only that
   new device. A plan is marked used before writing, so retries cannot reformat it.
3. Verifies Calamares mounted the exact new root and original EFI before unpacking.
   Windows/Recovery/MSR volumes are never mounted. The prepared bundle, early
   records and factory Bluetooth address follow this target into installed Linux.
4. Rebuilds/checks the installed initramfs, kernel, Blackrock DTB and required
   clock/power options. Removes live-installer components, without broad package
   autoremove. The user creates their own account; no live pairing keys are copied.
5. Generates explicit Linux and Windows entries, with os-prober disabled.
   Installs ARM64 GRUB under `EFI/DevKit2023CustomLinux` using `--no-nvram`, without
   replacing `EFI/Microsoft` or `EFI/BOOT`. Verifies original EFI file hashes.
6. Creates only a new Linux Boot entry; verifies every original Boot entry and
   the old order, then prepends Linux to that same order. Checks the final order
   and GPT again. Private installation evidence stays on the installed target.

There is no automatic partition-table rollback after a write failure. A partial
new Linux partition is retained for review, not reformatted on retry. Power loss
and firmware failures cannot be ruled out by software checks; backups and
recovery access remain required.

## Evidence and limits

- The launcher runs the packaged policy-authorized Calamares executable directly,
  with XCB display access limited to local root and revoked on exit. It retains
  the actual exit status and shows a failure dialog. It no longer uses Debian's
  wrapper, which restored the live fstab after Calamares and hid its failure code.
  No live fstab rename is needed for our explicit partition plan.
- The required branding `slideshow` key is an image **list**, using the existing
  logo. Omitting it makes Calamares 3.3.14 exit before showing a window; using an
  SVG as a scalar wrongly selects its QML loader. This distinction follows the
  [upstream branding contract](https://github.com/calamares/calamares/blob/v3.3.14/src/branding/default/branding.desc).
- Every base ISO verification now launches actual Calamares in a disposable
  overlay and isolated mount/network namespace, with no physical disks, EFI or
  real desktop sockets. Success requires window/module initialization and a
  running event loop, not just a settings-file message. The optional `--x11`
  mode also checks a viewable main window on test-host Xvfb. Neither test clicks
  Install or establishes real hardware/dual-boot acceptance.

- `tests/install-user-vm-test.py <trusted-public-rootfs> <new-native-output>` boots
  the exact release kernel on a new file-backed QEMU disk with no network or host
  disks. Only its disposable rootfs gets virtual-display tools, a synthetic
  preflight and test authorization. The normal-user launcher, real pkexec, private
  plan permissions, Continue dialog, actual Calamares window and filename search
  are exercised. No Install click occurs; this is not a full installation test.
  The output is VM-only evidence, never an ISO build input or release image.
- Pure policy tests cover 512/4096-byte sectors, free gaps, missing/ambiguous EFI,
  overlaps, unknown partitions, changed layouts and attempts to format Windows.
- Backend tests use synthetic EFI variables and command doubles, including failed
  writes, altered original entries and ignored BootOrder writes. They never read
  or modify the host's EFI variables or physical partitions.
- `tests/install-disk-image-test.py` creates its own sparse file and verifies its
  exact loop backing file before writing. It runs real GPT append/ext4 formatting
  and hashes every byte of all original fixture partitions before/after. It takes
  no disk/path argument. These tests are not a real Windows installation.
- `tests/install-chroot-test.py` uses a trusted public rootfs as read-only input
  and another disposable loop disk. It exercises the actual Calamares fstab code,
  live-package removal, installed initramfs generation, GRUB configuration and
  ARM64 GRUB installation with `--no-nvram`. Existing EFI sentinel files remain
  unchanged. Firmware is synthetic; physical authentication and EFI-variable
  access are mocked in this test, not removed from the shipped installer.
- The owner accepted the working edition. The separate installed-boot,
  Windows-reboot, reconnection, second-kit and full-port evidence was not supplied;
  no new testing is requested for this handoff. See [scope](VALIDATION.md).

Primary implementation references: [Calamares partition configuration](https://github.com/calamares/calamares/blob/v3.3.14/src/modules/partition/partition.conf),
[Calamares mount job](https://github.com/calamares/calamares/blob/v3.3.14/src/modules/mount/main.py),
[Calamares fstab job](https://github.com/calamares/calamares/blob/v3.3.14/src/modules/fstab/main.py),
[sfdisk manual](https://man7.org/linux/man-pages/man8/sfdisk.8.html).
