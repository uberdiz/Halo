#!/usr/bin/env bash
# Dev hot-patch: copy this working tree's SAINT files to a running HalOS over SSH (into /opt/saint/app) and
# restart SAINT there. Defaults to the test VM (127.0.0.1:2224, root). Uncommitted changes are included; files
# git ignores are not. Windows: tools/hotpatch.ps1 does the same.
#   tools/hotpatch.sh [-H host] [-p port] [-u user] [-i key]
set -euo pipefail
HOST=127.0.0.1 PORT=2224 USER_=root KEY=""
while getopts "H:p:u:i:h" o; do
  case "$o" in
    H) HOST=$OPTARG ;; p) PORT=$OPTARG ;; u) USER_=$OPTARG ;; i) KEY=$OPTARG ;;
    *) sed -n '2,5p' "$0"; exit 64 ;;
  esac
done
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
SSH=(-p "$PORT" -o StrictHostKeyChecking=accept-new) SCP=(-P "$PORT" -o StrictHostKeyChecking=accept-new)
[ -n "$KEY" ] && SSH+=(-i "$KEY") && SCP+=(-i "$KEY")
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
# Tracked and new files, without the ones deleted in the working tree.
git ls-files -co --exclude-standard -z | while IFS= read -r -d '' f; do [ -f "$f" ] && printf '%s\0' "$f"; done \
  | tar -cf "$TMP/saint-hotpatch.tar" --null -T -
echo "hotpatch: $(tar -tf "$TMP/saint-hotpatch.tar" | wc -l) files -> $USER_@$HOST:$PORT"
scp "${SCP[@]}" "$TMP/saint-hotpatch.tar" tools/hotpatch_remote.sh "$USER_@$HOST:/tmp/"
ssh "${SSH[@]}" "$USER_@$HOST" "bash /tmp/hotpatch_remote.sh /tmp/saint-hotpatch.tar"
