#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/common.sh"
require_root
require_native_arm64
require_commands python3 xorriso unsquashfs unmkinitramfs grub-file grub-fstest grub-script-check mcopy fdtget
python3 -B "$ROOT_DIR/scripts/check-source.py" --shell
python3 -B "$ROOT_DIR/scripts/verify-base.py" --iso "$ISO_PATH" --manifest "$ARTIFACT_ROOT/iso/build-manifest.json"
notice "Public preparation base verified; it must be prepared for its target in Windows."
