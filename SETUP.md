# The complete beginner setup guide

DevKit2023CustomLinux 1.0.0 - Microsoft Windows Dev Kit 2023.

This guide takes you from a normal Windows installation to a prepared USB,
then to Linux alongside Windows. You do not need to type a series of commands.
The same guide and technical reference are in
[the PDF](docs/DevKit2023CustomLinux-Guide.pdf).

## 1. Know what you are building

An **ISO** is a complete bootable disk image. **WSL** provides a Linux build
environment inside Windows. The launcher builds Linux there, adds only your
explicitly selected Dev Kit's required firmware and Bluetooth identity, checks
the finished image, and removes temporary build files.

Your finished ISO belongs to that one kit. The source project is reusable on
other Dev Kits; the prepared ISO is not. Never upload a prepared image to GitHub.

Already have the working ISO for this kit? You can go straight to section 4.
You do not need to rebuild it or run an APT update to make the installer open.

## 2. Get ready in Windows

1. Use the kit's normal licensed **Windows 11 ARM64** installation. Finish its
   normal Windows and OEM driver updates. An unconfigured generic Windows image
   may not contain the necessary device firmware.
2. Turn on built-in Bluetooth once in Windows. This makes its controller address
   available to the exporter. Do not substitute an external Bluetooth dongle.
3. Make a separate backup of your important files. Keep Windows recovery media
   and any BitLocker recovery key somewhere other than this kit.
4. Download or copy the complete trusted project. Extract it into a writable
   local folder, not a ZIP, cloud-synced folder or shared drive. Keep all the
   source folders together.
5. Connect mains power and internet. Allow **several hours** and approximately
   **100 GB free** on the drive holding WSL as a planning allowance. Peak space
   varies; clean builds download and compile again every time.
6. Have a USB drive of at least **8 GB** that can be erased. Do not use your only
   Windows recovery drive or backup drive.

The supported builder is Windows ARM64 with native Debian 13 ARM64 WSL 2.
An x64 Windows PC is not supported by this workflow. WSL uses its native Linux
disk, not the Windows project folder, for compilation.

## 3. Build with one launcher

1. Double-click **Start-DevKit2023CustomLinux.cmd** in the project folder.
2. Choose **Build an ISO for THIS Dev Kit (recommended)**.
3. Confirm that this computer is the intended target. The dialog explains the
   firmware and identity being included; it does not collect your passwords,
   recovery keys, full registry or Bluetooth pairing keys.
4. If an ISO already exists, confirm replacement only if you want a new build.
   The existing ISO remains intact until the replacement passes verification.
   A successful replacement does not keep an old backup.
5. Approve administrator access when Windows asks about WSL setup. The launcher
   enables the needed Windows features and installs WSL/Debian when missing.
   It never deletes an existing Linux distribution.
6. If asked to restart Windows, close your other work, restart normally and
   open the **same launcher** again. Nothing schedules itself to run at login.
   An incompatible existing Debian is reported and left untouched.
7. Leave the console open while the source is built and the target firmware is
   authenticated. No cached base image or old target export is selected.
8. Wait for **Ready** and the USB handoff dialog. The only normal final output is
   **ISO/DevKit2023CustomLinux-1.0.0-arm64.iso** inside this project.

Build signatures, source consistency and image integrity checks stay enabled.
These are automatic build checks, not a new request for manual hardware testing.

Temporary kernel sources, packages, root filesystems, manifests and the automatic
target export are removed after success or an ordinary handled failure. WSL,
Debian, installed compiler tools and normal operating-system records remain.
A power cut, forced process kill or WSL failure can interrupt cleanup; no program
can promise deletion after it has stopped running. See section 9.

### Building on a different ARM64 computer

On the **target Dev Kit**, choose **Export THIS Dev Kit for a different ARM64
builder** and select a private destination. Transfer the resulting target-bundle
folder privately. On the builder, choose **Build for another Dev Kit from its
exported bundle** and select that exact folder.

This optional export is the only deliberate non-ISO output. Because it is your
explicitly selected transfer file, the builder does not delete it. Remove your
copy after the build if you no longer need it. A future rebuild can export again
from the intended kit's Windows. Never commit the bundle to the source tree.

## 4. Write the USB

1. Open the project **ISO** folder. The launcher also has **Open ISO folder**.
2. Obtain the Windows **ARM64** version of [Rufus](https://rufus.ie/en/) from its
   official website. Rufus is not bundled or automatically executed.
3. Start Rufus and check its **Device** field carefully. Select only the USB you
   intend to erase, not the internal Windows disk or a backup drive.
4. Select the prepared ISO. If Rufus offers ISO mode versus DD mode, choose
   **DD/raw image mode** to preserve the boot layout.
5. Read and accept the USB erase warning. Wait for completion and safely eject it.

Copying the ISO as an ordinary file onto a formatted USB is not the same as
writing a bootable USB. This project's launcher never formats or writes a drive.

## 5. Start the live desktop

1. Use the reference connections: **rear USB-A** for the USB and a keyboard/mouse,
   and **mini-DisplayPort** for the monitor.
2. Shut the kit down. With the USB connected, use Power + the UEFI button to enter
   firmware setup. Follow Microsoft's
   [Dev Kit UEFI guide](https://learn.microsoft.com/en-us/windows/arm/dev-kit/).
3. This image is unsigned. **Secure Boot must be disabled** for it. Have Windows
   recovery access available before changing boot/security settings.
4. In Boot Configuration, choose USB Storage.
5. Select **Install DevKit2023CustomLinux** in GRUB. This starts the live desktop;
   it does not immediately install or change the internal disk.

The required **clk_ignore_unused pd_ignore_unused** parameters are already
included. Do not remove them. Do not add **efi=noruntime**: installation needs EFI
runtime services to create its Linux boot entry.

Firmware is already present in the prepared image. Linux does not try to scan or
unlock Windows for firmware during boot. Preparing an image from running Windows
does not require decrypting C:. This does not remove normal BitLocker recovery
risks when boot settings change.

## 6. Use the desktop

- **Install DevKit2023CustomLinux** opens the guided Windows-alongside installer.
- **Install Google Chrome** asks for confirmation and installs the current official
  Linux ARM64 stable package over the internet. In a live session, that installation
  is temporary; install it again after installing Linux to keep it.
- **Diagnostics** creates an optional report when you request one, shows it and
  offers a readable file you can copy. Review it before sharing privately.
- **Konsole** is available for commands. Dolphin is the file manager.

Wi-Fi and Bluetooth are controlled in KDE's system tray. Select the correct
audio output in Sound settings. The image includes the backend required for KDE's
speaker-test buttons as well as normal PipeWire playback.

Windows and Linux use the controller's same factory address but do not share
pairing keys. An accessory with an old/conflicting bond may need to be re-paired.
Sharing or copying pairing secrets is not automated.

The live desktop is non-persistent. Save files or diagnostic reports to a separate
writable drive before restarting; session changes disappear on reboot.

## 7. Install alongside Windows

### Prepare free space in Windows

1. Back up your data and keep recovery access available. There is no promise that
   changing firmware settings can never trigger Windows recovery.
2. Open **Disk Management** in Windows.
3. Shrink the Windows volume to leave **64 GiB unallocated** if possible
   (**32 GiB minimum**). Leave it unallocated: do not create or format a partition.
4. Keep all existing Windows, EFI, Microsoft Reserved and Recovery partitions.
5. Disable Fast Startup/hibernation for this shutdown or use a full Windows
   shutdown. Do not boot Linux against a hibernated Windows session.

If Windows cannot shrink safely, stop. The Linux installer intentionally does not
resize or decrypt Windows. Do not remove recovery partitions to make it proceed.

### Run the desktop installer

1. Boot your prepared USB and open **Install DevKit2023CustomLinux**.
2. Approve the administrator prompt. The first checks are read-only.
3. Read the proposed internal disk, Linux size and EFI reuse. It must propose
   **one new Linux partition in unallocated space**, not a Windows partition.
4. Continue to the installer. Choose language, keyboard and time zone, then
   create your own account and password.
5. Read the final summary. Only the final **Install** confirmation starts writing.
   Remain on mains power and do not remove the USB during installation.
6. After completion, restart and remove the USB. GRUB offers
   **DevKit2023CustomLinux** and **Windows Boot Manager**.
7. Use the normal system from the internal disk. You no longer need the USB.
   If you want Chrome permanently, use its installer in installed Linux.

The supported layout is one internal NVMe Windows GPT disk with one existing
ARM64 Windows EFI partition, at least **32 MiB free in EFI**, no previous Linux
installation, and an adequate unallocated gap. Mounted, ambiguous or changed
layouts are refused. Close file-manager windows accessing the internal disk.

The installer rechecks the plan before writing, formats only its new ext4 Linux
partition, preserves original EFI files and existing boot entries, and adds
Linux ahead of the preserved boot order. It does not support reinstall/overwrite,
erase, replacement or automatic rollback after a partial write.

If installation fails after writing begins, **do not repeat it blindly**. Save
the failure information and request review. Do not delete partitions or EFI
entries to bypass a refusal. Windows Boot Manager should remain available in
the kit's UEFI; keep recovery media available for unexpected failures.

## 8. Find a log or diagnose a problem

No manual APT update is needed to launch the complete image's installer.
Updating packages is not a substitute for understanding a failure.

If an installer warning closes without the main window, the error dialog offers
**Open log**. You can also open Dolphin, press **Ctrl+L**, enter
**~/.local/state/devkit2023customlinux/** and open the latest installer log.
That is the address bar, not the search field. This folder is hidden because its
name begins with a dot; Ctrl+H shows hidden files.

Run **Diagnostics** before restarting if you want a support report. Copy it to
writable storage, not into the read-only ISO filesystem. Private startup logs may
contain details beyond the redacted report: inspect them before sharing.

For no signal, first confirm the ISO belongs to this kit, use miniDP and rear
USB-A, and retain the default clock/power parameters. Capture the last error if
possible. Do not invent firmware files or re-enable retired boot-time imports.

## 9. Clean builds and interrupted cleanup

A completed normal build leaves only the ISO in **ISO/**. It does not leave the
old sibling Data folder, automatic logs, source archives or previous builds.

Temporary work is restricted to newly created directories named:

- Windows temporary storage: **DevKit2023CustomLinux-build-** plus a random ID.
- Native WSL storage: **/var/tmp/DevKit2023CustomLinux-build.** plus a random ID.

Ordinary success/failure handlers remove the invocation's files. Never force-close
the console while compiling. If power loss or a forced shutdown interrupts
cleanup, restart Windows and use **Remove interrupted build files** in the
launcher once no build is running. It removes only owned, marked temporary build
directories and partial publication files, never WSL itself or an external target
bundle. Any refused/busy path is left intact and reported.

WSL and its installed build tools are prerequisites, not old ISO build leftovers.
Deletion inside WSL frees Linux filesystem space; Windows may not immediately
shrink WSL's virtual-disk file. This workflow does not resize that virtual disk.

## 10. Publish the project on GitHub

Publish the **source folder**, including this guide, the PDF, scripts, patches,
configuration and tests. Keep its structure; these folders are the actual product.

**Exclude ISO/** and any independently exported private bundle. Git ignores ISO
automatically, but a browser/manual upload can still expose it if you select it.
Do not use force-add on ignored images.

No GitHub repository or upload is created automatically. The source can be placed
in a new empty repository, using GitHub Desktop or Git. Project code is MIT;
upstream licenses remain attached. A private prepared ISO is not a distributable
universal image.

The technical details and pinned patch list are in
[IMPLEMENTATION.md](docs/IMPLEMENTATION.md). Current scope and limitations are in
[VALIDATION.md](docs/VALIDATION.md).
