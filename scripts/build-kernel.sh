#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/common.sh"

require_root
require_native_arm64
require_commands git make sha256sum

KERNEL_STAGE="$BUILD_ROOT/kernel"
KERNEL_SRC="$KERNEL_STAGE/linux-next"
KERNEL_OUT="$KERNEL_STAGE/out"
PATCH_AUDIO="$PROJECT_ROOT/patches/20260825-blackrock-dp-audio-altmode-v2.mbox"
PATCH_USB="$PROJECT_ROOT/patches/20250609-blackrock-usb0-mux-v1.mbox"
PATCH_BUFFER="$PROJECT_ROOT/patches/20260902-buffer-fix-null-b-folio.mbox"

verify_sha256 "$PATCH_AUDIO_SHA256" "$PATCH_AUDIO"
verify_sha256 "$PATCH_USB_SHA256" "$PATCH_USB"
verify_sha256 "$PATCH_BUFFER_SHA256" "$PATCH_BUFFER"
# Each managed build starts fresh; no previous kernel tree is a build input.
recreate_build_dir "$KERNEL_STAGE"
notice "Cloning $KERNEL_TAG"
git clone --depth 1 --branch "$KERNEL_TAG" "$KERNEL_REPO" "$KERNEL_SRC"
actual_commit="$(git -C "$KERNEL_SRC" rev-parse HEAD)"
[[ "$actual_commit" == "$KERNEL_COMMIT" ]] ||
  die "Kernel tag moved: expected $KERNEL_COMMIT, got $actual_commit"

git -C "$KERNEL_SRC" config user.name "DevKit2023CustomLinux Builder"
git -C "$KERNEL_SRC" config user.email "builder@devkit2023customlinux.invalid"
export GIT_COMMITTER_DATE="2026-09-02T12:24:50Z"
git -C "$KERNEL_SRC" am --3way "$PATCH_AUDIO"
git -C "$KERNEL_SRC" am --3way "$PATCH_USB"
git -C "$KERNEL_SRC" am --3way "$PATCH_BUFFER"
unset GIT_COMMITTER_DATE

grep -Fq 'if (bh->b_folio && folio_test_dropbehind(bh->b_folio) &&' \
  "$KERNEL_SRC/fs/buffer.c" ||
  die "Pinned buffer_head NULL-folio correction is missing"

notice "Checking Blackrock hardware definitions"
dts="$KERNEL_SRC/arch/arm64/boot/dts/qcom/sc8280xp-microsoft-blackrock.dts"
grep -Fq 'compatible = "qcom,wcn6855-bt";' "$dts" ||
  die "WCN6855 Bluetooth node is missing"
grep -Fq 'bt-enable-gpios = <&tlmm 133 GPIO_ACTIVE_HIGH>;' "$dts" ||
  die "Blackrock Bluetooth enable GPIO is missing"
grep -Fq 'enable-gpios = <&tlmm 100 GPIO_ACTIVE_LOW>;' "$dts" ||
  die "USB0 orientation GPIO fix is missing"
grep -Fq 'model = "SC8280XP-MICROSOFT-BLACKROCK";' "$dts" ||
  die "DisplayPort audio patch is missing"
[[ "$(grep -Fc 'data-lanes = <0 1 2 3>;' "$dts")" -ge 3 ]] ||
  die "Four-lane DisplayPort endpoints are incomplete"
[[ "$(grep -Fc 'dma-channel-mask' "$dts")" -ge 3 ]] ||
  die "Blackrock GPI DMA safety masks are missing"
grep -Fq 'qca_read_fw_board_id(hdev, &boardid);' \
  "$KERNEL_SRC/drivers/bluetooth/btqca.c" ||
  die "WCN6855 board-ID-specific Bluetooth NVM selection is missing"

# The generic image intentionally has no device-specific Bluetooth address in
# its DTB. A boot-time provisioner selects the Windows factory address for the
# target kit's own Windows installation. No builder identity or fallback
# Bluetooth address is compiled into the kernel or image.
! grep -Fq 'local-bd-address' "$dts" ||
  die "Generic Blackrock device tree unexpectedly contains a fixed Bluetooth address"

mkdir -p "$KERNEL_OUT" "$ARTIFACT_ROOT/packages"
make -C "$KERNEL_SRC" O="$KERNEL_OUT" ARCH=arm64 defconfig
"$KERNEL_SRC/scripts/kconfig/merge_config.sh" -m -O "$KERNEL_OUT" \
  "$KERNEL_OUT/.config" "$PROJECT_ROOT/config/kernel/blackrock.config"
make -C "$KERNEL_SRC" O="$KERNEL_OUT" ARCH=arm64 olddefconfig

grep -Fqx '# CONFIG_LOCALVERSION_AUTO is not set' "$KERNEL_OUT/.config" ||
  die "CONFIG_LOCALVERSION_AUTO must stay disabled for the branded kernel release"
kernel_localversion="-devkit2023customlinux"
resolved_kernel_release="${KERNEL_RELEASE_BASE}${kernel_localversion}"
makefile_version="$(awk -F ' = ' '
  /^VERSION = / { version=$2 }
  /^PATCHLEVEL = / { patchlevel=$2 }
  /^SUBLEVEL = / { sublevel=$2 }
  /^EXTRAVERSION = / { extraversion=$2 }
  END { printf "%s.%s.%s%s", version, patchlevel, sublevel, extraversion }
' "$KERNEL_SRC/Makefile")"
source_localversion="$(find "$KERNEL_SRC" -maxdepth 1 -type f \
  -name 'localversion*' -print0 | sort -z | xargs -0r cat)"
[[ "${makefile_version}${source_localversion}" == "$KERNEL_RELEASE_BASE" ]] ||
  die "Pinned kernel release base changed: expected $KERNEL_RELEASE_BASE, got ${makefile_version}${source_localversion}"
[[ "${#resolved_kernel_release}" -le 64 ]] ||
  die "Kernel release exceeds the 64-character UTS_RELEASE limit: $resolved_kernel_release"
[[ "$resolved_kernel_release" == *"$kernel_localversion" ]] ||
  die "Kernel release lost the exact product suffix: $resolved_kernel_release"

notice "Verifying the resolved Blackrock kernel configuration"
while IFS= read -r requested; do
  [[ "$requested" =~ ^CONFIG_[A-Z0-9_]+= ]] || continue
  if ! grep -Fqx "$requested" "$KERNEL_OUT/.config"; then
    symbol="${requested%%=*}"
    actual="$(grep -E "^${symbol}=|^# ${symbol} is not set$" \
      "$KERNEL_OUT/.config" || true)"
    [[ -n "$actual" ]] || actual="<symbol absent from this kernel>"
    die "Kernel configuration rejected '$requested' (resolved as '$actual')"
  fi
done < "$PROJECT_ROOT/config/kernel/blackrock.config"

export KBUILD_BUILD_USER=devkit2023customlinux
export KBUILD_BUILD_HOST=arm64-builder
export KBUILD_BUILD_TIMESTAMP="2026-09-02T12:24:50Z"
export SOURCE_DATE_EPOCH=1788351890
export DEB_BUILD_PROFILES="pkg.devkit2023customlinux.nokernelheaders pkg.devkit2023customlinux.nokerneldbg"

# Regenerate packaging metadata so profile and source-name changes are honored
# when resuming after a packaging dependency failure.
rm -rf "$KERNEL_OUT/debian"
rm -f "$KERNEL_STAGE"/linux-*.deb

notice "Building the kernel and Debian packages"
# Debian package names are required to be lowercase; this is the technical
# package identifier, while all user-facing labels use PRODUCT_NAME exactly.
make -C "$KERNEL_SRC" O="$KERNEL_OUT" ARCH=arm64 \
  -j"$(nproc)" bindeb-pkg \
  DPKG_FLAGS="-j$(nproc)" \
  KDEB_SOURCENAME="devkit2023customlinux" \
  KDEB_PKGVERSION="${VERSION}+${KERNEL_TAG}" \
  KERNELRELEASE="$resolved_kernel_release"

rm -f "$ARTIFACT_ROOT/packages"/linux-*.deb
find "$KERNEL_STAGE" -maxdepth 2 -type f -name '*.deb' -exec cp -f {} "$ARTIFACT_ROOT/packages/" \;
compgen -G "$ARTIFACT_ROOT/packages/linux-image-*.deb" >/dev/null ||
  die "Kernel image package was not produced"

notice "Kernel packages copied to $ARTIFACT_ROOT/packages"

if [[ "${CLEAN_AFTER_STAGE:-0}" == "1" ]]; then
  assert_under_build_root "$KERNEL_STAGE"
  rm -rf --one-file-system "$KERNEL_STAGE"
  notice "Removed kernel work tree to conserve builder storage"
fi
