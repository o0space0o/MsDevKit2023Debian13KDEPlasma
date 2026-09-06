#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/common.sh"
require_commands python3 tar gzip sha256sum

# Validate every file, not just selected extensions. The source archive uses
# this explicit inventory rather than recursively adding an open directory.
python3 -B "$PROJECT_ROOT/scripts/check-source.py"
source_output="$ARTIFACT_ROOT/source"
source_name="${PRODUCT_NAME}-${VERSION}-source.tar.gz"
source_path="$source_output/$source_name"
[[ ! -e "$source_path" && ! -e "$source_path.sha256" ]] || die 'Source artifact already exists'
mkdir -p "$source_output"
tar --sort=name --mtime='@0' --owner=0 --group=0 --numeric-owner \
  --mode='u=rw,go=r,a+X' --no-recursion --verbatim-files-from \
  -czf "$source_path" -C "$PROJECT_ROOT" \
  -T <(python3 -B "$PROJECT_ROOT/scripts/check-source.py" --list-files)
(
  cd "$source_output"
  sha256sum "$source_name" > "$source_name.sha256"
  sha256sum -c "$source_name.sha256"
)
python3 -B "$PROJECT_ROOT/scripts/check-source.py" --archive "$source_path"
notice "Verified development source archive: $source_path"
