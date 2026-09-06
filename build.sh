#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT_DIR/scripts/lib/common.sh"

require_root
require_native_arm64
require_commands python3 flock
python3 -B "$PROJECT_ROOT/scripts/check-source.py" --shell
python3 -B -m unittest discover -s "$PROJECT_ROOT/tests" -p 'test_*.py'
mkdir -p "$BUILD_ROOT"
exec 9>"$BUILD_ROOT/.full-build.lock"
flock -n 9 || die "Another full build is using this source/build cache"

# A full build owns a fresh output directory. Existing candidates are evidence,
# not a scratch area, and must never be replaced by the build launcher.
[[ ! -e "$ARTIFACT_ROOT" ]] || die "Choose a new DEVKIT2023_ARTIFACT_ROOT; output already exists"
export DEVKIT2023_ARTIFACT_ROOT="$ARTIFACT_ROOT"
require_commands git make debootstrap chroot mksquashfs grub-mkstandalone \
  mkfs.vfat mmd mcopy xorriso dtc sha256sum rsync

mkdir -p "$BUILD_ROOT" "$ARTIFACT_ROOT/packages" "$ARTIFACT_ROOT/iso"

bash "$ROOT_DIR/scripts/build-kernel.sh"
bash "$ROOT_DIR/scripts/build-rootfs.sh"
bash "$ROOT_DIR/scripts/build-iso.sh"
bash "$ROOT_DIR/scripts/verify-artifacts.sh"

notice "Build complete: $ISO_PATH"
