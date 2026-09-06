# File index

Generated from `config/project-map.json`. Every active source file is listed.
Update with `python3 -B scripts/check-source.py --render-index`; normal checks reject drift.

## Overview and maintenance

Entry points, current evidence, source metadata and the connected project map.

Status: active documentation.

- [.gitattributes](../.gitattributes)
- [.gitignore](../.gitignore)
- [AGENTS.md](../AGENTS.md)
- [BUILD-STATUS.md](../BUILD-STATUS.md)
- [CONTRIBUTING.md](../CONTRIBUTING.md)
- [LICENSE](../LICENSE)
- [README.md](../README.md)
- [SECURITY.md](../SECURITY.md)
- [SETUP.md](../SETUP.md)
- [VERSION](../VERSION)
- [config/project-map.json](../config/project-map.json)
- [docs/DevKit2023CustomLinux-Guide.pdf](../docs/DevKit2023CustomLinux-Guide.pdf)
- [docs/FILE-INDEX.md](../docs/FILE-INDEX.md)
- [docs/IMPLEMENTATION.md](../docs/IMPLEMENTATION.md)
- [docs/INSTALLATION.md](../docs/INSTALLATION.md)
- [docs/PREPARATION.md](../docs/PREPARATION.md)
- [docs/PROJECT-MAP.md](../docs/PROJECT-MAP.md)
- [docs/UPSTREAM.md](../docs/UPSTREAM.md)
- [docs/VALIDATION.md](../docs/VALIDATION.md)
- [docs/WORKFLOW.md](../docs/WORKFLOW.md)
- [scripts/build-guide.py](../scripts/build-guide.py)

## Build coordination

Native ARM64 build stages, dependencies, ISO-only publication and scoped temporary cleanup.

Status: native ARM64 builder; preparation required before boot.

- [.github/workflows/build-iso.yml](../.github/workflows/build-iso.yml)
- [build.sh](../build.sh)
- [scripts/clean-workspace.sh](../scripts/clean-workspace.sh)
- [scripts/install-build-deps.sh](../scripts/install-build-deps.sh)
- [scripts/lib/common.sh](../scripts/lib/common.sh)
- [scripts/wsl-build-bootstrap.sh](../scripts/wsl-build-bootstrap.sh)

## Windows build host

Windows entry points for generic builds, explicit target export and private ISO preparation.

Status: guided fresh Windows build and explicit target export; cleanup revision statically reviewed.

- [Start-DevKit2023CustomLinux.cmd](../Start-DevKit2023CustomLinux.cmd)
- [windows/Build-DevKit2023CustomLinuxISO.ps1](../windows/Build-DevKit2023CustomLinuxISO.ps1)
- [windows/Clean-InterruptedBuilds.ps1](../windows/Clean-InterruptedBuilds.ps1)
- [windows/DevKit.Common.ps1](../windows/DevKit.Common.ps1)
- [windows/Export-DevKit2023Target.ps1](../windows/Export-DevKit2023Target.ps1)
- [windows/Prepare-DevKit2023CustomLinux.ps1](../windows/Prepare-DevKit2023CustomLinux.ps1)
- [windows/Setup-WSL.ps1](../windows/Setup-WSL.ps1)
- [windows/Start-DevKit2023CustomLinux.ps1](../windows/Start-DevKit2023CustomLinux.ps1)

## Kernel and board

Pinned linux-next source, three patch files/four commits and Blackrock kernel configuration.

Status: pinned owner-accepted 1.0.0 board baseline.

- [config/kernel/blackrock.config](../config/kernel/blackrock.config)
- [patches/20250609-blackrock-usb0-mux-v1.mbox](../patches/20250609-blackrock-usb0-mux-v1.mbox)
- [patches/20260825-blackrock-dp-audio-altmode-v2.mbox](../patches/20260825-blackrock-dp-audio-altmode-v2.mbox)
- [patches/20260902-buffer-fix-null-b-folio.mbox](../patches/20260902-buffer-fix-null-b-folio.mbox)
- [scripts/build-kernel.sh](../scripts/build-kernel.sh)

## Root filesystem and ISO

Minimal Debian ARM64 package selection, overlay assembly, UEFI ISO and manifest.

Status: temporary target-free base before private target preparation.

- [scripts/build-iso.sh](../scripts/build-iso.sh)
- [scripts/build-rootfs.sh](../scripts/build-rootfs.sh)

## Boot integration

Live/installed GRUB, DTB install hook, initramfs permissions and firmware hook.

Status: prepared early-boot profile; reference kit boots KDE.

- [config/grub/embedded.cfg](../config/grub/embedded.cfg)
- [config/grub/grub.cfg](../config/grub/grub.cfg)
- [overlay/etc/default/grub.d/10-devkit2023customlinux.cfg](../overlay/etc/default/grub.d/10-devkit2023customlinux.cfg)
- [overlay/etc/grub.d/09_devkit2023customlinux](../overlay/etc/grub.d/09_devkit2023customlinux)
- [overlay/etc/initramfs-tools/conf.d/initramfs-permissions](../overlay/etc/initramfs-tools/conf.d/initramfs-permissions)
- [overlay/etc/initramfs-tools/hooks/devkit2023customlinux-firmware](../overlay/etc/initramfs-tools/hooks/devkit2023customlinux-firmware)
- [overlay/etc/kernel/postinst.d/zz-devkit2023customlinux-dtb](../overlay/etc/kernel/postinst.d/zz-devkit2023customlinux-dtb)

## Firmware authentication

Shared signed-catalog authentication for explicitly exported target firmware.

Status: no Linux-time Windows import or USB-cache fallback.

- [overlay/usr/local/libexec/devkit2023customlinux-validate-windows-driver](../overlay/usr/local/libexec/devkit2023customlinux-validate-windows-driver)

## Display and audio

Readiness helpers, service ordering, ALSA UCM routes and retained upstream license/source notices.

Status: reference miniDP and audible playback observed; full port matrix pending.

- [overlay/etc/systemd/system/display-manager.service.d/10-devkit2023customlinux-display.conf](../overlay/etc/systemd/system/display-manager.service.d/10-devkit2023customlinux-display.conf)
- [overlay/usr/local/libexec/devkit2023customlinux-audio](../overlay/usr/local/libexec/devkit2023customlinux-audio)
- [overlay/usr/local/libexec/devkit2023customlinux-display-ready](../overlay/usr/local/libexec/devkit2023customlinux-display-ready)
- [overlay/usr/share/alsa/ucm2/Qualcomm/sc8280xp/Blackrock-HiFi.conf](../overlay/usr/share/alsa/ucm2/Qualcomm/sc8280xp/Blackrock-HiFi.conf)
- [overlay/usr/share/alsa/ucm2/Qualcomm/sc8280xp/microsoft-blackrock.conf](../overlay/usr/share/alsa/ucm2/Qualcomm/sc8280xp/microsoft-blackrock.conf)
- [overlay/usr/share/alsa/ucm2/Qualcomm/sc8280xp/sc8280xp.conf](../overlay/usr/share/alsa/ucm2/Qualcomm/sc8280xp/sc8280xp.conf)
- [overlay/usr/share/doc/devkit2023customlinux/alsa-ucm-conf-LICENSE](../overlay/usr/share/doc/devkit2023customlinux/alsa-ucm-conf-LICENSE)
- [overlay/usr/share/doc/devkit2023customlinux/alsa-ucm-conf-source](../overlay/usr/share/doc/devkit2023customlinux/alsa-ucm-conf-source)

## Bluetooth identity and service ordering

Built-in controller udev integration; target-bound provisioning belongs to the prepared component.

Status: observed connected on the reference kit.

- [overlay/etc/systemd/system/bluetooth.service.d/10-devkit2023customlinux-address.conf](../overlay/etc/systemd/system/bluetooth.service.d/10-devkit2023customlinux-address.conf)
- [overlay/etc/udev/rules.d/80-devkit2023customlinux-bluetooth.rules](../overlay/etc/udev/rules.d/80-devkit2023customlinux-bluetooth.rules)

## Installer and target handover

Calamares flow, live launcher, preflight and installed target-data transfer.

Status: enabled Windows-free-space-only installation; see documented evidence limits.

- [overlay/etc/calamares/branding/devkit2023customlinux/branding.desc](../overlay/etc/calamares/branding/devkit2023customlinux/branding.desc)
- [overlay/etc/calamares/branding/devkit2023customlinux/devkit2023customlinux-logo.svg](../overlay/etc/calamares/branding/devkit2023customlinux/devkit2023customlinux-logo.svg)
- [overlay/etc/calamares/modules/mount.conf](../overlay/etc/calamares/modules/mount.conf)
- [overlay/etc/calamares/modules/packages.conf](../overlay/etc/calamares/modules/packages.conf)
- [overlay/etc/calamares/modules/shellprocess-check-mount.conf](../overlay/etc/calamares/modules/shellprocess-check-mount.conf)
- [overlay/etc/calamares/modules/shellprocess-cleanup.conf](../overlay/etc/calamares/modules/shellprocess-cleanup.conf)
- [overlay/etc/calamares/modules/shellprocess-finish.conf](../overlay/etc/calamares/modules/shellprocess-finish.conf)
- [overlay/etc/calamares/modules/shellprocess-target-data.conf](../overlay/etc/calamares/modules/shellprocess-target-data.conf)
- [overlay/etc/calamares/modules/users.conf](../overlay/etc/calamares/modules/users.conf)
- [overlay/etc/calamares/modules/welcome.conf](../overlay/etc/calamares/modules/welcome.conf)
- [overlay/etc/calamares/settings.conf](../overlay/etc/calamares/settings.conf)
- [overlay/etc/skel/Desktop/InstallDevKit2023CustomLinux.desktop](../overlay/etc/skel/Desktop/InstallDevKit2023CustomLinux.desktop)
- [overlay/usr/lib/calamares/modules/devkitpartition/main.py](../overlay/usr/lib/calamares/modules/devkitpartition/main.py)
- [overlay/usr/lib/calamares/modules/devkitpartition/module.desc](../overlay/usr/lib/calamares/modules/devkitpartition/module.desc)
- [overlay/usr/lib/devkit2023customlinux/install_policy.py](../overlay/usr/lib/devkit2023customlinux/install_policy.py)
- [overlay/usr/local/bin/devkit2023customlinux-installer](../overlay/usr/local/bin/devkit2023customlinux-installer)
- [overlay/usr/local/libexec/devkit2023customlinux-copy-target-data](../overlay/usr/local/libexec/devkit2023customlinux-copy-target-data)
- [overlay/usr/local/libexec/devkit2023customlinux-install-storage](../overlay/usr/local/libexec/devkit2023customlinux-install-storage)
- [overlay/usr/share/applications/install-devkit2023customlinux.desktop](../overlay/usr/share/applications/install-devkit2023customlinux.desktop)

## Desktop, branding and optional Chrome

Minimal KDE desktop, branding and user-triggered official ARM64 Chrome installation.

Status: three desktop launchers; Chrome is never bundled.

- [overlay/etc/issue](../overlay/etc/issue)
- [overlay/etc/issue.net](../overlay/etc/issue.net)
- [overlay/etc/live/config.conf.d/10-devkit2023customlinux.conf](../overlay/etc/live/config.conf.d/10-devkit2023customlinux.conf)
- [overlay/etc/os-release](../overlay/etc/os-release)
- [overlay/etc/sddm.conf.d/10-devkit2023customlinux.conf](../overlay/etc/sddm.conf.d/10-devkit2023customlinux.conf)
- [overlay/etc/skel/.config/kdeglobals](../overlay/etc/skel/.config/kdeglobals)
- [overlay/etc/skel/.config/plasma-org.kde.plasma.desktop-appletsrc](../overlay/etc/skel/.config/plasma-org.kde.plasma.desktop-appletsrc)
- [overlay/etc/skel/.config/plasmarc](../overlay/etc/skel/.config/plasmarc)
- [overlay/etc/skel/Desktop/InstallGoogleChrome.desktop](../overlay/etc/skel/Desktop/InstallGoogleChrome.desktop)
- [overlay/usr/local/bin/devkit2023customlinux-install-chrome](../overlay/usr/local/bin/devkit2023customlinux-install-chrome)
- [overlay/usr/local/libexec/devkit2023customlinux-install-chrome](../overlay/usr/local/libexec/devkit2023customlinux-install-chrome)
- [overlay/usr/share/devkit2023customlinux/install-google-chrome.desktop](../overlay/usr/share/devkit2023customlinux/install-google-chrome.desktop)
- [overlay/usr/share/wallpapers/DevKit2023CustomLinux/contents/images/3840x2160.svg](../overlay/usr/share/wallpapers/DevKit2023CustomLinux/contents/images/3840x2160.svg)
- [overlay/usr/share/wallpapers/DevKit2023CustomLinux/metadata.json](../overlay/usr/share/wallpapers/DevKit2023CustomLinux/metadata.json)

## Source and artifact verification

Inventory/privacy/link/syntax checks, synthetic tests and extracted ISO verification.

Status: active build-only tooling.

- [.github/workflows/source-check.yml](../.github/workflows/source-check.yml)
- [scripts/check-source.py](../scripts/check-source.py)
- [scripts/package-source.sh](../scripts/package-source.sh)
- [scripts/verify-artifacts.sh](../scripts/verify-artifacts.sh)
- [scripts/verify-base.py](../scripts/verify-base.py)
- [scripts/verify-installer-startup.py](../scripts/verify-installer-startup.py)
- [scripts/verify-prepared-iso.py](../scripts/verify-prepared-iso.py)
- [tests/install-chroot-test.py](../tests/install-chroot-test.py)
- [tests/install-disk-image-test.py](../tests/install-disk-image-test.py)
- [tests/install-user-vm-test.py](../tests/install-user-vm-test.py)
- [tests/test_build_layout.py](../tests/test_build_layout.py)
- [tests/test_desktop_delivery.py](../tests/test_desktop_delivery.py)
- [tests/test_early_topology.py](../tests/test_early_topology.py)
- [tests/test_install_backend.py](../tests/test_install_backend.py)
- [tests/test_install_policy.py](../tests/test_install_policy.py)
- [tests/test_installer_startup.py](../tests/test_installer_startup.py)
- [tests/test_live_tester.py](../tests/test_live_tester.py)
- [tests/test_prepared_bundle.py](../tests/test_prepared_bundle.py)
- [tests/test_prepared_early_driver.py](../tests/test_prepared_early_driver.py)
- [tests/test_prepared_runtime.py](../tests/test_prepared_runtime.py)
- [tests/test_source_hygiene.py](../tests/test_source_hygiene.py)
- [tests/test_windows_driver_validator.py](../tests/test_windows_driver_validator.py)
- [tests/test_windows_workflow.py](../tests/test_windows_workflow.py)
- [tests/windows-launcher-tests.ps1](../tests/windows-launcher-tests.ps1)

## Private Windows preparation

Explicit target export, authenticated bundle selection, ISO repacking and early-boot target-bound firmware. Never an implicit builder-data fallback.

Status: one explicit-target Windows workflow; no persistent export/cache.

- [profiles/prepared/overlay/etc/default/grub.d/20-devkit2023customlinux-prepared.cfg](../profiles/prepared/overlay/etc/default/grub.d/20-devkit2023customlinux-prepared.cfg)
- [profiles/prepared/overlay/etc/initramfs-tools/hooks/devkit2023customlinux-prepared](../profiles/prepared/overlay/etc/initramfs-tools/hooks/devkit2023customlinux-prepared)
- [profiles/prepared/overlay/etc/initramfs-tools/scripts/init-premount/devkit2023customlinux-prepared](../profiles/prepared/overlay/etc/initramfs-tools/scripts/init-premount/devkit2023customlinux-prepared)
- [profiles/prepared/overlay/etc/systemd/system/devkit2023customlinux-audio.service](../profiles/prepared/overlay/etc/systemd/system/devkit2023customlinux-audio.service)
- [profiles/prepared/overlay/etc/systemd/system/devkit2023customlinux-bluetooth-address.service](../profiles/prepared/overlay/etc/systemd/system/devkit2023customlinux-bluetooth-address.service)
- [profiles/prepared/overlay/etc/systemd/system/devkit2023customlinux-display-ready.service](../profiles/prepared/overlay/etc/systemd/system/devkit2023customlinux-display-ready.service)
- [profiles/prepared/overlay/etc/systemd/system/devkit2023customlinux-prepared.service](../profiles/prepared/overlay/etc/systemd/system/devkit2023customlinux-prepared.service)
- [profiles/prepared/overlay/usr/local/libexec/devkit2023customlinux-bluetooth-address](../profiles/prepared/overlay/usr/local/libexec/devkit2023customlinux-bluetooth-address)
- [profiles/prepared/overlay/usr/local/libexec/devkit2023customlinux-install-preflight](../profiles/prepared/overlay/usr/local/libexec/devkit2023customlinux-install-preflight)
- [profiles/prepared/overlay/usr/local/libexec/devkit2023customlinux-prepared](../profiles/prepared/overlay/usr/local/libexec/devkit2023customlinux-prepared)
- [scripts/install-preparation-deps.sh](../scripts/install-preparation-deps.sh)
- [scripts/prepare-iso.py](../scripts/prepare-iso.py)

## User diagnostics

Permanent optional support utility: one desktop launcher, hidden implementation, native KDE progress/report viewer and redacted text output. No embedded target data.

Status: integrated in base and prepared profiles; hardware acceptance remains separate.

- [docs/TESTER.md](../docs/TESTER.md)
- [overlay/etc/skel/Desktop/DevKit2023Diagnostics.desktop](../overlay/etc/skel/Desktop/DevKit2023Diagnostics.desktop)
- [overlay/usr/local/libexec/devkit2023customlinux-diagnostics](../overlay/usr/local/libexec/devkit2023customlinux-diagnostics)
- [scripts/package-diagnostics.py](../scripts/package-diagnostics.py)
