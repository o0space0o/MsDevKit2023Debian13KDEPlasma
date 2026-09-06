#!/usr/bin/env bash
# Delete exactly one root-owned temporary build directory, never a broad parent.
set -Eeuo pipefail
target="${1:?Exact temporary build directory required}"
[[ "${EUID:-$(id -u)}" -eq 0 ]] || { echo 'Cleanup requires root.' >&2; exit 1; }
[[ "$target" =~ ^/var/tmp/DevKit2023CustomLinux-build\.[A-Za-z0-9]{10}$ ]] || { echo 'Unsafe cleanup path.' >&2; exit 1; }
[[ "$(realpath -m "$target")" == "$target" && ! -L "$target" ]] || { echo 'Linked cleanup path refused.' >&2; exit 1; }
[[ -e "$target" ]] || exit 0
[[ -d "$target" && "$(stat -c %u "$target")" == 0 ]] || { echo 'Unexpected cleanup target/owner.' >&2; exit 1; }
exec 9>"$target/.active"
flock -n 9 || { echo 'An active build owns this directory; left intact.' >&2; exit 1; }
# Do not follow a chroot bind mount into host devices or EFI.
while IFS= read -r mounted; do
  [[ "$mounted" == "$target" || "$mounted" == "$target/"* ]] || exit 1
  umount -- "$mounted" || { echo 'Busy build mount; cleanup stopped safely.' >&2; exit 1; }
done < <(findmnt -rn -o TARGET | awk -v root="$target" '$0 == root || index($0, root "/") == 1' | sort -r)
rm -rf --one-file-system -- "$target"
