#!/usr/bin/env bash
set -Eeuo pipefail
[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo 'Root is required.' >&2; exit 1; }
# This path executes the trusted Debian 13 base's signer on its ARM64 builder.
. /etc/os-release
[[ ${ID:-} == debian && ${VERSION_ID:-} == 13 && $(uname -m) == aarch64 ]] || {
  echo 'Use the Debian 13 ARM64 WSL distribution for ISO preparation.' >&2
  exit 1
}
missing=no
for tool in python3 xorriso unsquashfs mksquashfs grub-script-check grub-file unmkinitramfs mcopy mount chroot zstd; do
  command -v "$tool" >/dev/null || missing=yes
done
if [[ $missing == yes ]]; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 xorriso squashfs-tools grub-efi-arm64-bin grub-common \
    initramfs-tools-core mtools util-linux coreutils zstd
fi
