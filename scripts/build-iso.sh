#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/common.sh"

require_root
require_native_arm64
require_commands chroot mksquashfs grub-mkstandalone grub-script-check mkfs.vfat mmd mcopy xorriso sha256sum find stat grep

ROOTFS="$BUILD_ROOT/rootfs"
[[ ! -e "$ISO_PATH" && ! -e "$ISO_PATH.sha256" ]] ||
  die "Refusing to overwrite an existing ISO; choose a new artifact directory"
[[ -d "$ROOTFS" ]] || die "Build the root filesystem first"
[[ "$PRODUCT_NAME" == "DevKit2023CustomLinux" && "$VERSION" == "1.0.0" ]] ||
  die "Public release metadata must identify DevKit2023CustomLinux 1.0.0"

python3 -B "$PROJECT_ROOT/scripts/verify-base.py" --root "$ROOTFS"

ISO_STAGE="$BUILD_ROOT/iso-stage"
recreate_build_dir "$ISO_STAGE"
mkdir -p "$ISO_STAGE/EFI/BOOT" "$ISO_STAGE/boot/grub" \
  "$ISO_STAGE/boot/grub/fonts" "$ISO_STAGE/boot/dtbs" \
  "$ISO_STAGE/live" "$ARTIFACT_ROOT/iso"

kernel_image="$(find "$ROOTFS/boot" -maxdepth 1 -type f -name 'vmlinuz-*-devkit2023customlinux*' | sort -V | tail -n1)"
[[ -n "$kernel_image" ]] || die "Custom DevKit2023CustomLinux kernel is missing from rootfs"
kernel_version="$(basename "$kernel_image" | sed 's/^vmlinuz-//')"
kernel_config="$ROOTFS/boot/config-$kernel_version"
initrd_image="$ROOTFS/boot/initrd.img-$kernel_version"
dtb_source="$ROOTFS/usr/lib/linux-image-$kernel_version/qcom/$DTB_NAME"
grub_font="/usr/share/grub/unicode.pf2"
[[ -f "$initrd_image" ]] || die "Initramfs is missing: $initrd_image"
[[ -f "$kernel_config" ]] || die "Matching kernel configuration is missing: $kernel_config"
for required_kernel_setting in \
  CONFIG_SQUASHFS_XATTR=y CONFIG_DRM_MSM=m CONFIG_QCOM_Q6V5_PAS=m CONFIG_SND_SOC_SC8280XP=m; do
  grep -Fqx "$required_kernel_setting" "$kernel_config" ||
    die "Selected live kernel lacks required boot setting: $required_kernel_setting"
done
[[ -f "$dtb_source" ]] || die "Blackrock DTB is missing: $dtb_source"
[[ -f "$grub_font" ]] || die "GRUB Unicode font is missing: $grub_font"

cp "$kernel_image" "$ISO_STAGE/live/vmlinuz"
cp "$initrd_image" "$ISO_STAGE/live/initrd.img"
cp "$dtb_source" "$ISO_STAGE/boot/dtbs/$DTB_NAME"
cp "$PROJECT_ROOT/config/grub/grub.cfg" "$ISO_STAGE/boot/grub/grub.cfg"
cp "$grub_font" "$ISO_STAGE/boot/grub/fonts/unicode.pf2"
printf '%s %s\n' "$PRODUCT_NAME" "$VERSION" > "$ISO_STAGE/DEVKIT2023CUSTOMLINUX_ID"

grub-script-check "$PROJECT_ROOT/config/grub/embedded.cfg"
grub-script-check "$ISO_STAGE/boot/grub/grub.cfg"

notice "Compressing live filesystem"
mksquashfs "$ROOTFS" "$ISO_STAGE/live/filesystem.squashfs" \
  -comp zstd -Xcompression-level 15 -noappend -no-progress
du -sx --block-size=1 "$ROOTFS" | cut -f1 > "$ISO_STAGE/live/filesystem.size"

grub-mkstandalone -O arm64-efi \
  --modules="part_gpt part_msdos fat iso9660 ext2 normal linux fdt gzio search search_fs_file search_fs_uuid configfile all_video gfxterm" \
  --locales="" --fonts="" \
  -o "$ISO_STAGE/EFI/BOOT/BOOTAA64.EFI" \
  "boot/grub/grub.cfg=$PROJECT_ROOT/config/grub/embedded.cfg"

truncate -s 128M "$ISO_STAGE/boot/grub/efi.img"
mkfs.vfat -F 32 -n DEVKIT2023 "$ISO_STAGE/boot/grub/efi.img"
mmd -i "$ISO_STAGE/boot/grub/efi.img" ::/EFI ::/EFI/BOOT
mcopy -i "$ISO_STAGE/boot/grub/efi.img" \
  "$ISO_STAGE/EFI/BOOT/BOOTAA64.EFI" ::/EFI/BOOT/BOOTAA64.EFI

notice "Creating UEFI ARM64 ISO"
xorriso -as mkisofs \
  -iso-level 3 -full-iso9660-filenames -volid DevKit2023CustomLinux \
  -eltorito-alt-boot -e boot/grub/efi.img -no-emul-boot \
  -efi-boot-part --efi-boot-image \
  -o "$ISO_PATH" "$ISO_STAGE"

(
  cd "$ARTIFACT_ROOT/iso"
  sha256sum "$ISO_BASENAME" > "$ISO_BASENAME.sha256"
)

iso_sha="$(sha256sum "$ISO_PATH" | awk '{print $1}')"
kernel_sha="$(sha256sum "$ISO_STAGE/live/vmlinuz" | awk '{print $1}')"
kernel_config_sha="$(sha256sum "$kernel_config" | awk '{print $1}')"
dtb_sha="$(sha256sum "$ISO_STAGE/boot/dtbs/$DTB_NAME" | awk '{print $1}')"
patched_kernel_commit="$(git -C "$BUILD_ROOT/kernel/linux-next" rev-parse HEAD)"
package_inventory="$BUILD_ROOT/package-inventory.tsv"
chroot "$ROOTFS" dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\n' |
  LC_ALL=C sort > "$package_inventory"
package_inventory_sha="$(sha256sum "$package_inventory" | awk '{print $1}')"
package_count="$(wc -l < "$package_inventory" | tr -d '[:space:]')"
cp "$package_inventory" "$ARTIFACT_ROOT/iso/packages.tsv"
cat > "$ARTIFACT_ROOT/iso/build-manifest.json" <<EOF
{
  "distribution": "$PRODUCT_NAME",
  "version": "$VERSION",
  "candidateRevision": "$CANDIDATE_REVISION",
  "architecture": "arm64",
  "releaseProfile": "public-base",
  "base": "Debian 13 Trixie",
  "kernelTag": "$KERNEL_TAG",
  "kernelCommit": "$KERNEL_COMMIT",
  "patchedKernelCommit": "$patched_kernel_commit",
  "kernelVersion": "$kernel_version",
  "displayPortPatchSha256": "$PATCH_AUDIO_SHA256",
  "usbMuxPatchSha256": "$PATCH_USB_SHA256",
  "bufferNullFolioPatchSha256": "$PATCH_BUFFER_SHA256",
  "deviceTree": "qcom/$DTB_NAME",
  "bootLevel": "EL1",
  "iso": "$ISO_BASENAME",
  "sha256": "$iso_sha",
  "kernelSha256": "$kernel_sha",
  "kernelConfigSha256": "$kernel_config_sha",
  "dtbSha256": "$dtb_sha",
  "audioReachTopologyCommit": "$AUDIOREACH_TOPOLOGY_COMMIT",
  "audioReachTopologySourceSha256": "$AUDIOREACH_BLACKROCK_M4_SHA256",
  "packageCount": $package_count,
  "packageInventorySha256": "$package_inventory_sha",
  "secureBoot": false,
  "googleChromeBundled": false,
  "googleChromeRepositoryBundled": false,
  "googleChromeSigningKeyBundled": false,
  "googleChromeDelivery": "user-initiated-official-runtime-install",
  "privateOwnerBuild": false,
  "containsBuilderIdentity": false,
  "containsDeviceIdentity": false,
  "checkupFilesBundled": false,
  "diagnosticsIncluded": true,
  "installationEnabled": false,
  "installerPolicy": "windows-free-space-v1",
  "windowsImportAtBoot": false,
  "requiresWindowsPreparation": true,
  "bluetoothAddressProvisioning": "automatic-per-target",
  "bluetoothAddressMode": "explicit-target-windows-export",
  "deterministicBluetoothFallback": false,
  "bluetoothIdentityCache": "target-local-after-acquisition",
  "builderIdentityDataBundled": false,
  "bundledProprietaryDeviceFirmware": false,
  "embeddedBlackrockFirmware": false,
  "targetFirmwareAcquisition": "signed-explicit-windows-export-before-boot",
  "targetFirmwareCatalogVerification": true,
  "firmwareValidatorRevision": "catalog-table-boundary-and-digestless-records-v1",
  "targetFirmwareFiles": [
    "qcadsp8280.mbn",
    "qccdsp8280.mbn",
    "qcdxkmsuc8280.mbn"
  ],
  "targetFirmwarePersistence": "private-prepared-iso",
  "targetFirmwareProvenance": "authenticated-before-private-preparation",
  "firstBootFirmwareFlow": "target-bound-authenticated-early-load",
  "officialWcnFirmwarePackage": "firmware-atheros",
  "redistributionAudit": "pending",
  "staticVerification": "pending",
  "hardwareValidation": {
    "status": "required",
    "referenceHardwareResult": "prepared-test-4-desktop-network-audio-bluetooth-observed",
    "currentCandidateResult": "not-yet-tested",
    "automaticBluetooth": "reference-tested; fresh-prepared-image-retest-required",
    "dualBootInstallation": "not-yet-tested-on-version-1.0.0"
  }
}
EOF

cat > "$ARTIFACT_ROOT/iso/PREPARE-IN-WINDOWS.txt" <<EOF
TARGET-FREE PREPARATION BASE - ${CANDIDATE_REVISION}

This is the reusable, target-free preparation BASE, not a ready-to-boot desktop.
Run the Windows launcher with a fresh export from the intended Dev Kit to create
its private bootable image. No boot-time Windows import or USB cache exists.

Keep the private prepared image on its own target. Do not publish it.
The prepared image includes a free-space-only, Windows-preserving installer.
Back up Windows before installing. Real installed-system and Windows reboot
acceptance remains necessary before calling the edition a production release.

The hardware-tested reference is the prepared test-4 image. The source retains
its kernel, firmware validation, topology, Bluetooth helper and normal boot line:
clk_ignore_unused pd_ignore_unused

EOF

notice "ISO created: $ISO_PATH"

if [[ "${CLEAN_AFTER_STAGE:-0}" == "1" ]]; then
  assert_under_build_root "$ROOTFS"
  assert_under_build_root "$ISO_STAGE"
  rm -rf --one-file-system "$ROOTFS" "$ISO_STAGE"
  notice "Removed rootfs and ISO staging tree to conserve builder storage"
fi
