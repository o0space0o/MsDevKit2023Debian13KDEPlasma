#!/usr/bin/env bash

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_ROOT="$PROJECT_ROOT/build"
ARTIFACT_ROOT="${DEVKIT2023_ARTIFACT_ROOT:-/var/tmp/DevKit2023CustomLinux-artifacts-$$}"
VERSION="$(tr -d '\r\n' < "$PROJECT_ROOT/VERSION")"
PRODUCT_NAME="DevKit2023CustomLinux"
PRODUCT_ID="devkit2023customlinux"
CANDIDATE_REVISION="prepared-workflow-v1"
ISO_BASENAME="${PRODUCT_NAME}-${VERSION}-arm64.iso"
ISO_PATH="$ARTIFACT_ROOT/iso/$ISO_BASENAME"
KERNEL_TAG="next-20260902"
KERNEL_COMMIT="32b6ef9a5d0eca44f9cd91f52f4faa89f145a0de"
KERNEL_RELEASE_BASE="7.3.0-rc1-next-20260902"
KERNEL_REPO="https://kernel.googlesource.com/pub/scm/linux/kernel/git/next/linux-next.git"
DTB_NAME="sc8280xp-microsoft-blackrock.dtb"
PATCH_AUDIO_SHA256="6c9d6cab985494ee4e90142c74ab6e85f62df4da59f17059feeb9b6ff55042bf"
PATCH_USB_SHA256="380a6b885e23c607955e67b7c8cb36baff0b3c7dad0b099049f0899e94b43300"
PATCH_BUFFER_SHA256="d469ac0df3a69765f3c5b1a1d45aaa5dded6c512f44a64ac332ca7f8e6a26ad9"
AUDIOREACH_TOPOLOGY_REPO="https://github.com/jglathe/audioreach-topology.git"
AUDIOREACH_TOPOLOGY_COMMIT="31e0451c67b9001b49118177617a3e8b7bbd4c5c"
AUDIOREACH_BLACKROCK_M4_SHA256="e03de10b7a0fbf0a5d6558b826fa6904edabff1a1229e292107d4d43d063fcac"
export PROJECT_ROOT BUILD_ROOT ARTIFACT_ROOT VERSION PRODUCT_NAME PRODUCT_ID CANDIDATE_REVISION ISO_BASENAME ISO_PATH
export KERNEL_TAG KERNEL_COMMIT KERNEL_RELEASE_BASE KERNEL_REPO DTB_NAME

notice() {
  printf '\n[DevKit2023CustomLinux] %s\n' "$*"
}

die() {
  printf '\n[DevKit2023CustomLinux] ERROR: %s\n' "$*" >&2
  exit 1
}

# Normalize before any stage can create, clear or publish artifacts. Private
# preparation outputs will have a separate entry point; this is the public build.
[[ "$ARTIFACT_ROOT" == /* ]] || die "Artifact root must be absolute"
ARTIFACT_ROOT="$(realpath -m "$ARTIFACT_ROOT")"
case "$ARTIFACT_ROOT" in
  /|/tmp|/opt|/home|/root|"$PROJECT_ROOT"|"$PROJECT_ROOT"/*|"$HOME")
    die "Artifact root must be a dedicated directory outside source" ;;
esac
export ARTIFACT_ROOT
ISO_PATH="$ARTIFACT_ROOT/iso/$ISO_BASENAME"
export ISO_PATH

require_root() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "Run this stage as root."
}

require_native_arm64() {
  case "$(uname -m)" in
    aarch64|arm64) ;;
    *) die "This release requires a native ARM64 Linux builder. Detected $(uname -m)." ;;
  esac
}

require_commands() {
  local command_name
  for command_name in "$@"; do
    command -v "$command_name" >/dev/null 2>&1 ||
      die "Missing build dependency: $command_name"
  done
}

assert_under_build_root() {
  local candidate resolved_build resolved_candidate
  resolved_build="$(realpath -m "$BUILD_ROOT")"
  resolved_candidate="$(realpath -m "$1")"
  [[ "$resolved_candidate" == "$resolved_build/"* ]] ||
    die "Refusing to modify path outside build directory: $resolved_candidate"
}

recreate_build_dir() {
  local target="$1"
  assert_under_build_root "$target"
  rm -rf --one-file-system "$target"
  mkdir -p "$target"
}

verify_sha256() {
  local expected="$1" file="$2" actual
  actual="$(sha256sum "$file" | awk '{print tolower($1)}')"
  [[ "$actual" == "$expected" ]] ||
    die "Checksum mismatch for $file: expected $expected, got $actual"
}

mounted_under() {
  findmnt -rn -o TARGET | awk -v root="$1" '$0 == root || index($0, root "/") == 1'
}

unmount_tree() {
  local root="$1" target
  while IFS= read -r target; do
    umount -lf "$target" || true
  done < <(mounted_under "$root" | sort -r)
}
