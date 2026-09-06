#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/common.sh"

require_root
require_native_arm64
require_commands debootstrap chroot mount umount rsync git m4 curl openssl cmake tar

ROOTFS="$BUILD_ROOT/rootfs"
recreate_build_dir "$ROOTFS"

cleanup() {
  unmount_tree "$ROOTFS"
}
trap cleanup EXIT

notice "Creating Debian 13 Trixie ARM64 root filesystem"
debootstrap --arch=arm64 --variant=minbase trixie "$ROOTFS" https://deb.debian.org/debian

cat > "$ROOTFS/etc/apt/sources.list" <<'EOF'
deb https://deb.debian.org/debian trixie main contrib non-free-firmware
deb https://deb.debian.org/debian trixie-updates main contrib non-free-firmware
deb https://security.debian.org/debian-security trixie-security main contrib non-free-firmware
deb https://deb.debian.org/debian trixie-backports main contrib non-free-firmware
EOF

printf 'devkit2023\n' > "$ROOTFS/etc/hostname"
cat > "$ROOTFS/etc/hosts" <<'EOF'
127.0.0.1 localhost
127.0.1.1 devkit2023
::1 localhost ip6-localhost ip6-loopback
EOF
cp -L /etc/resolv.conf "$ROOTFS/etc/resolv.conf"

mkdir -p "$ROOTFS/dev" "$ROOTFS/proc" "$ROOTFS/sys" "$ROOTFS/run"
mount --rbind /dev "$ROOTFS/dev"
mount --make-rslave "$ROOTFS/dev"
mount -t proc proc "$ROOTFS/proc"
mount --rbind /sys "$ROOTFS/sys"
mount --make-rslave "$ROOTFS/sys"
mount -t tmpfs -o mode=0755,nosuid,nodev tmpfs "$ROOTFS/run"

cat > "$ROOTFS/usr/sbin/policy-rc.d" <<'EOF'
#!/bin/sh
exit 101
EOF
chmod 0755 "$ROOTFS/usr/sbin/policy-rc.d"

export DEBIAN_FRONTEND=noninteractive
chroot "$ROOTFS" apt-get update
chroot "$ROOTFS" apt-get install -y --no-install-recommends \
  systemd-sysv dbus-user-session sudo locales console-setup keyboard-configuration \
  initramfs-tools linux-base live-boot live-config live-config-systemd user-setup \
  plasma-desktop kwin-wayland sddm sddm-theme-breeze \
  powerdevil plasma-pa systemsettings kscreen polkit-kde-agent-1 pkexec \
  dolphin kio-extras konsole nano less kdialog qdbus-qt6 xdg-desktop-portal-kde \
  network-manager plasma-nm wpasupplicant wireless-regdb bluez bluedevil rfkill \
  pipewire-audio wireplumber libcanberra-pulse power-profiles-daemon \
  calamares calamares-settings-debian \
  squashfs-tools \
  grub-efi-arm64 grub-efi-arm64-bin efibootmgr fdisk e2fsprogs dosfstools \
  ntfs-3g exfatprogs cryptsetup-bin cryptsetup-initramfs usbutils iproute2 \
  alsa-utils alsa-ucm-conf curl ca-certificates gnupg openssl \
  fonts-noto-core fonts-noto-color-emoji breeze-gtk-theme

chroot "$ROOTFS" apt-get install -y -t trixie-backports \
  firmware-qcom-soc firmware-atheros firmware-realtek

# firmware-qcom-soc currently pulls the Lenovo X13s SC8280XP DSP payloads as
# package dependencies. They are redistributable, but they target a different
# computer and use the same basenames as the three Blackrock files acquired
# from each Dev Kit's own Windows installation. Remove that unrelated board
# directory so it cannot be mistaken for, or used as, a cross-device fallback.
rm -rf "$ROOTFS/usr/lib/firmware/qcom/sc8280xp/LENOVO"
rm -f "$ROOTFS/usr/lib/firmware/qcom/sc8280xp/SC8280XP-LENOVO-X13S-tplg.bin"

# Debian 13 carries osslsigncode 2.9, which is unsafe for untrusted catalog
# verification. Build the pinned, fixed upstream 2.14 release natively and
# place only its runtime binary and license in the image.
osslsigncode_archive="$BUILD_ROOT/osslsigncode-2.14.tar.gz"
osslsigncode_source="$BUILD_ROOT/osslsigncode-2.14-source"
osslsigncode_build="$BUILD_ROOT/osslsigncode-2.14-build"
curl --proto '=https' --tlsv1.2 -fsSL \
  https://github.com/mtrojnar/osslsigncode/archive/refs/tags/2.14.tar.gz \
  -o "$osslsigncode_archive"
verify_sha256 \
  0f033fd6069387d2e489fbd2187e62f624764eb8c2758ee94e3e793e5150b5c5 \
  "$osslsigncode_archive"
recreate_build_dir "$osslsigncode_source"
recreate_build_dir "$osslsigncode_build"
tar -xf "$osslsigncode_archive" -C "$osslsigncode_source" --strip-components=1
cmake -S "$osslsigncode_source" -B "$osslsigncode_build" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build "$osslsigncode_build" --parallel "$(nproc)"
install -m 0755 "$osslsigncode_build/osslsigncode" \
  "$ROOTFS/usr/local/bin/osslsigncode"
mkdir -p "$ROOTFS/usr/share/doc/devkit2023customlinux"
install -m 0644 "$osslsigncode_source/LICENSE.txt" \
  "$ROOTFS/usr/share/doc/devkit2023customlinux/osslsigncode-LICENSE.txt"
cat > "$ROOTFS/usr/share/doc/devkit2023customlinux/osslsigncode-source" <<'EOF'
Project: https://github.com/mtrojnar/osslsigncode
Version: 2.14
Source archive SHA-256: 0f033fd6069387d2e489fbd2187e62f624764eb8c2758ee94e3e793e5150b5c5
Purpose: verify target Windows DriverStore catalogs
EOF
chroot "$ROOTFS" /usr/local/bin/osslsigncode --version | grep -Fq 'osslsigncode 2.14'

# Validate target-side Windows DriverStore catalogs against Microsoft's public
# code-signing roots. These public certificates come directly from Microsoft's
# PKI repository; no certificate or firmware is copied from the build host.
microsoft_cert_directory="$BUILD_ROOT/microsoft-driver-roots"
recreate_build_dir "$microsoft_cert_directory"
for certificate in \
  'MicRooCerAut_2010-06-23.crt:df545bf919a2439c36983b54cdfc903dfa4f37d3996d8d84b4c31eec6f3c163e' \
  'MicRooCerAut2011_2011_03_22.crt:847df6a78497943f27fc72eb93f9a637320a02b561d0a91b09e87a7807ed7c61'; do
  filename="${certificate%%:*}"
  expected_sha="${certificate##*:}"
  curl --proto '=https' --tlsv1.2 -fsSL \
    "https://www.microsoft.com/pki/certs/$filename" \
    -o "$microsoft_cert_directory/$filename"
  verify_sha256 "$expected_sha" "$microsoft_cert_directory/$filename"
  openssl x509 -inform DER -in "$microsoft_cert_directory/$filename" \
    -out "$microsoft_cert_directory/$filename.pem"
done
mkdir -p "$ROOTFS/usr/share/devkit2023customlinux"
cat "$microsoft_cert_directory"/*.pem \
  > "$ROOTFS/usr/share/devkit2023customlinux/microsoft-driver-roots.pem"
cat > "$ROOTFS/usr/share/devkit2023customlinux/microsoft-driver-roots-source" <<'EOF'
Source: https://www.microsoft.com/pkiops/docs/repository.htm
Microsoft Root Certificate Authority 2010 SHA-256: df545bf919a2439c36983b54cdfc903dfa4f37d3996d8d84b4c31eec6f3c163e
Microsoft Root Certificate Authority 2011 SHA-256: 847df6a78497943f27fc72eb93f9a637320a02b561d0a91b09e87a7807ed7c61
Purpose: verify Windows DriverStore catalogs before importing target firmware
EOF

# The sc8280xp ASoC driver requests a machine-specific AudioReach topology.
# linux-firmware has the X13s topology, but not the three-DisplayPort Blackrock
# topology yet. Build the device author's submitted topology at a pinned commit.
notice "Building the Windows Dev Kit 2023 AudioReach topology"
topology_source="$BUILD_ROOT/audioreach-topology"
topology_name="SC8280XP-MICROSOFT-BLACKROCK"
topology_m4="$topology_source/$topology_name.m4"
topology_conf="$ROOTFS/tmp/$topology_name.conf"
topology_dump="$ROOTFS/tmp/$topology_name.decoded.conf"
topology_dir="$ROOTFS/usr/lib/firmware/qcom/sc8280xp/microsoft/blackrock"
topology_target="$topology_dir/$topology_name-tplg.bin"
topology_doc="$ROOTFS/usr/share/doc/devkit2023customlinux"

recreate_build_dir "$topology_source"
git -C "$topology_source" init -q
git -C "$topology_source" remote add origin "$AUDIOREACH_TOPOLOGY_REPO"
git -C "$topology_source" fetch -q --depth=1 origin "$AUDIOREACH_TOPOLOGY_COMMIT"
git -C "$topology_source" -c advice.detachedHead=false checkout -q --detach FETCH_HEAD
[[ "$(git -C "$topology_source" rev-parse HEAD)" == "$AUDIOREACH_TOPOLOGY_COMMIT" ]] ||
  die "AudioReach topology checkout did not resolve to the pinned commit"
[[ -f "$topology_m4" ]] || die "Pinned AudioReach source has no Blackrock topology"
verify_sha256 "$AUDIOREACH_BLACKROCK_M4_SHA256" "$topology_m4"

m4 -I "$topology_source" "$topology_m4" > "$topology_conf"
mkdir -p "$topology_dir"
chroot "$ROOTFS" alsatplg \
  -c "/tmp/$topology_name.conf" \
  -o "/usr/lib/firmware/qcom/sc8280xp/microsoft/blackrock/$topology_name-tplg.bin"
[[ -s "$topology_target" ]] || die "Blackrock AudioReach topology was not generated"
ln -sfn \
  "microsoft/blackrock/$topology_name-tplg.bin" \
  "$ROOTFS/usr/lib/firmware/qcom/sc8280xp/$topology_name-tplg.bin"
chroot "$ROOTFS" alsatplg \
  -d "/usr/lib/firmware/qcom/sc8280xp/microsoft/blackrock/$topology_name-tplg.bin" \
  -o "/tmp/$topology_name.decoded.conf"
for expected_route in \
  "MultiMedia1 Playback" "MultiMedia2 Playback" "MultiMedia3 Playback" \
  "DISPLAY_PORT_RX_0" "DISPLAY_PORT_RX_1" "DISPLAY_PORT_RX_2"; do
  grep -Fq "$expected_route" "$topology_dump" ||
    die "Generated AudioReach topology is missing $expected_route"
done

mkdir -p "$topology_doc"
install -m 0644 "$topology_source/LICENSE.BSD-3-Clause" \
  "$topology_doc/audioreach-topology-LICENSE"
install -m 0644 "$topology_m4" \
  "$topology_doc/$topology_name.m4"
cat > "$topology_doc/audioreach-topology-source" <<EOF
Repository: $AUDIOREACH_TOPOLOGY_REPO
Commit: $AUDIOREACH_TOPOLOGY_COMMIT
Source: $topology_name.m4
Source-SHA256: $AUDIOREACH_BLACKROCK_M4_SHA256
EOF
rm -f "$topology_conf" "$topology_dump"

# The Windows source copy may expose every file as executable through DrvFS.
# Normalize the overlay before restoring the intended executable bits below.
rsync -a --chmod=D0755,F0644 "$PROJECT_ROOT/overlay/" "$ROOTFS/"
rsync -a --chmod=D0755,F0644 "$PROJECT_ROOT/profiles/prepared/overlay/" "$ROOTFS/"
while IFS= read -r -d '' profile_script; do
  if head -c 2 "$profile_script" | grep -Fq '#!'; then chmod 0755 "$profile_script"; fi
done < <(find "$ROOTFS/usr/local" "$ROOTFS/etc/initramfs-tools" -type f -print0)
install -m 0644 "$ROOTFS/etc/skel/Desktop/DevKit2023Diagnostics.desktop" \
  "$ROOTFS/usr/share/applications/devkit2023customlinux-diagnostics.desktop"
chmod 0755 "$ROOTFS/etc/skel/Desktop/DevKit2023Diagnostics.desktop" \
  "$ROOTFS/etc/skel/Desktop/InstallDevKit2023CustomLinux.desktop" \
  "$ROOTFS/etc/skel/Desktop/InstallGoogleChrome.desktop" \
  "$ROOTFS/usr/local/libexec/devkit2023customlinux-diagnostics"
chmod 0755 \
  "$ROOTFS/usr/local/bin/devkit2023customlinux-installer" \
  "$ROOTFS/usr/local/bin/devkit2023customlinux-install-chrome" \
  "$ROOTFS/usr/local/libexec/devkit2023customlinux-display-ready" \
  "$ROOTFS/usr/local/libexec/devkit2023customlinux-audio" \
  "$ROOTFS/usr/local/libexec/devkit2023customlinux-validate-windows-driver" \
  "$ROOTFS/usr/local/libexec/devkit2023customlinux-copy-target-data" \
  "$ROOTFS/usr/local/libexec/devkit2023customlinux-install-preflight" \
  "$ROOTFS/usr/local/libexec/devkit2023customlinux-install-chrome" \
  "$ROOTFS/usr/local/libexec/devkit2023customlinux-bluetooth-address" \
  "$ROOTFS/etc/initramfs-tools/hooks/devkit2023customlinux-firmware" \
  "$ROOTFS/etc/kernel/postinst.d/zz-devkit2023customlinux-dtb" \
  "$ROOTFS/etc/grub.d/09_devkit2023customlinux"
chmod 0644 \
  "$ROOTFS/etc/systemd/system/devkit2023customlinux-display-ready.service" \
  "$ROOTFS/etc/systemd/system/devkit2023customlinux-audio.service" \
  "$ROOTFS/etc/systemd/system/display-manager.service.d/10-devkit2023customlinux-display.conf" \
  "$ROOTFS/etc/systemd/system/devkit2023customlinux-bluetooth-address.service" \
  "$ROOTFS/etc/systemd/system/bluetooth.service.d/10-devkit2023customlinux-address.conf" \
  "$ROOTFS/etc/udev/rules.d/80-devkit2023customlinux-bluetooth.rules"

# Keep one device-aware Linux entry; the installer adds Windows explicitly. Divert
# generic Linux generators outside /etc/grub.d so a future grub-common update
# cannot restore entries that omit the mandatory Blackrock DTB.
disabled_grub_dir=/usr/lib/devkit2023customlinux/grub-disabled
mkdir -p "$ROOTFS$disabled_grub_dir"
for generator in 10_linux 20_linux_xen; do
  generator_path="/etc/grub.d/$generator"
  [[ -e "$ROOTFS$generator_path" ]] || continue
  chroot "$ROOTFS" dpkg-divert --local --rename --add \
    --divert "$disabled_grub_dir/$generator.distrib" "$generator_path"
  printf '# Generic Linux entries are disabled; use 09_devkit2023customlinux.\n' \
    > "$ROOTFS$generator_path"
  chmod 0644 "$ROOTFS$generator_path"
done

# Debian's Calamares branding and launchers are replaced by the single custom
# installer entry. The command-line wrapper remains as the privileged backend.
rm -rf "$ROOTFS/etc/calamares/branding/debian"
rm -f "$ROOTFS/usr/share/applications/calamares.desktop" \
  "$ROOTFS/usr/share/applications/calamares-install-debian.desktop" \
  "$ROOTFS/etc/xdg/autostart/calamares-desktop-icon.desktop" \
  "$ROOTFS/usr/bin/add-calamares-desktop-icon" \
  "$ROOTFS/usr/share/pixmaps/install-debian.png" \
  "$ROOTFS/usr/share/glib-2.0/schemas/96_calamares-settings-debian.gschema.override"

mkdir -p "$ROOTFS/tmp/devkit2023customlinux-kernel"
cp "$ARTIFACT_ROOT"/packages/linux-image-*.deb "$ROOTFS/tmp/devkit2023customlinux-kernel/"
if compgen -G "$ARTIFACT_ROOT/packages/linux-libc-dev-*.deb" >/dev/null; then
  cp "$ARTIFACT_ROOT"/packages/linux-libc-dev-*.deb "$ROOTFS/tmp/devkit2023customlinux-kernel/"
fi
chroot "$ROOTFS" bash -c 'apt-get install -y /tmp/devkit2023customlinux-kernel/linux-image-*.deb'

for kernel_config in "$ROOTFS"/boot/config-*-devkit2023customlinux*; do
  [[ -f "$kernel_config" ]] || die "Installed custom kernel configuration is missing"
  grep -Fqx 'CONFIG_SQUASHFS_XATTR=y' "$kernel_config" ||
    die "Installed kernel cannot preserve the live filesystem's extended attributes"
done

chroot "$ROOTFS" bash -c "echo 'en_US.UTF-8 UTF-8' > /etc/locale.gen && locale-gen"
chroot "$ROOTFS" update-initramfs -u -k all
chroot "$ROOTFS" systemctl enable NetworkManager.service \
  devkit2023customlinux-prepared.service \
  devkit2023customlinux-display-ready.service \
  devkit2023customlinux-audio.service \
  devkit2023customlinux-bluetooth-address.service bluetooth.service sddm.service
chroot "$ROOTFS" systemd-analyze verify --man=no \
  devkit2023customlinux-prepared.service \
  devkit2023customlinux-display-ready.service devkit2023customlinux-audio.service \
  devkit2023customlinux-bluetooth-address.service bluetooth.service display-manager.service
chroot "$ROOTFS" udevadm verify \
  /etc/udev/rules.d/80-devkit2023customlinux-bluetooth.rules
chroot "$ROOTFS" systemctl set-default graphical.target

rm -f "$ROOTFS/usr/sbin/policy-rc.d"
rm -rf "$ROOTFS/tmp/devkit2023customlinux-kernel"
chroot "$ROOTFS" apt-get clean
rm -rf "$ROOTFS/var/lib/apt/lists/"*
truncate -s 0 "$ROOTFS/etc/machine-id"
rm -f "$ROOTFS/var/lib/dbus/machine-id"
rm -f "$ROOTFS/var/lib/systemd/random-seed"
find "$ROOTFS/var/log" -type f -exec truncate -s 0 {} +
rm -f "$ROOTFS/etc/resolv.conf"
ln -s /run/NetworkManager/resolv.conf "$ROOTFS/etc/resolv.conf"
printf '%s %s\n' "$PRODUCT_NAME" "$VERSION" > "$ROOTFS/etc/devkit2023customlinux-release"

cleanup
trap - EXIT
notice "Root filesystem ready"
