#!/usr/bin/env bash
set -Eeuo pipefail

[[ "${EUID:-$(id -u)}" -eq 0 ]] || {
  echo "Run as root." >&2
  exit 1
}

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  bc bison build-essential ca-certificates cmake curl debootstrap device-tree-compiler \
  debhelper dosfstools dpkg-dev dwarves fakeroot file flex git gnupg \
  grub-efi-arm64-bin jq kmod libdw-dev libelf-dev libssl-dev lsb-release \
  m4 mtools python3 python3-yaml rsync \
  squashfs-tools xorriso zlib1g-dev zstd
