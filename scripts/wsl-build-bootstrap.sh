#!/usr/bin/env bash
set -Eeuo pipefail
source_dir="${1:?Windows source path required}"
run="${2:?Native temporary directory required}"
bundle="${3:?Explicit target bundle required}"
publication="${4:?Temporary Windows result directory required}"
fail() { printf '[DevKit2023CustomLinux] %s\n' "$*" >&2; exit 1; }
[[ "${EUID:-$(id -u)}" -eq 0 ]] || fail 'Run as root.'
case "$(uname -m)" in aarch64|arm64) ;; *) fail 'Native ARM64 required.' ;; esac
[[ "$run" =~ ^/var/tmp/DevKit2023CustomLinux-build\.[A-Za-z0-9]{10}$ && -d "$run" && ! -L "$run" ]] || fail 'Invalid managed workspace.'
[[ "$(realpath -e "$run")" == "$run" && "$(stat -c %u "$run")" == 0 ]] || fail 'Unexpected workspace ownership/path.'
source_dir="$(realpath -e "$source_dir")"
[[ "$source_dir" == /mnt/* && -f "$source_dir/build.sh" ]] || fail 'Invalid Windows source.'
publication="$(realpath -m "$publication")"
[[ "$publication" =~ /DevKit2023CustomLinux-build-[a-f0-9]{32}/result$ && ! -e "$publication" ]] || fail 'Output must be a fresh temporary result directory.'
[[ "$publication" != "$source_dir/"* ]] || fail 'Temporary output cannot be in source.'
cleanup_script="$source_dir/scripts/clean-workspace.sh"
exec 9>"$run/.active"
flock -n 9 || fail 'This workspace is already active.'
cleanup() { flock -u 9; bash "$cleanup_script" "$run"; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates python3 rsync
python3 -B "$source_dir/scripts/check-source.py" --shell
# Explicit inventory only: never copy ISO, unregistered files or target exports.
mkdir "$run/source"
python3 -B "$source_dir/scripts/check-source.py" --list-files > "$run/source-files"
rsync -a --chmod=D0755,F0644 --files-from="$run/source-files" "$source_dir/" "$run/source/"
workspace="$run/source"
bash "$workspace/scripts/install-build-deps.sh"
bash "$workspace/scripts/install-preparation-deps.sh"
export DEVKIT2023_ARTIFACT_ROOT="$run/artifacts"
export DEVKIT2023_WORK_ROOT="$run"
bash "$workspace/build.sh"
version="$(tr -d '\r\n' < "$workspace/VERSION")"
base="$DEVKIT2023_ARTIFACT_ROOT/iso/DevKit2023CustomLinux-$version-arm64.iso"
base_hash="$(sha256sum "$base" | cut -d ' ' -f1)"
printf '\n[3/4] Preparing the selected target and verifying the finished ISO.\n'
python3 -B "$workspace/scripts/prepare-iso.py" --base "$base" --base-sha256 "$base_hash" \
  --bundle "$bundle" --output "$run/prepared" --work-parent "$run"
# Internal metadata is checked before Windows publishes only the ISO.
mkdir "$publication"
rsync -a "$run/prepared/" "$publication/"
