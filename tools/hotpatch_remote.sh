#!/usr/bin/bash
# Runs on the HalOS machine (copied there by tools/hotpatch.sh / hotpatch.ps1): unpacks the working tree's files
# into /opt/saint/app and restarts every running SAINT on it. Needs root (ssh as root, or a user with sudo).
#   hotpatch_remote.sh /tmp/saint-hotpatch.tar
set -eu
TAR="${1:?tarball}"
APP=/opt/saint/app
[ -f "$APP/app.py" ] || { echo "hotpatch: $APP isn't a SAINT install" >&2; exit 1; }
if [ "$(id -u)" -ne 0 ]; then
  exec sudo -n "$0" "$@"
fi
# Whose SAINT is running (the desktop user's, normally), before it's stopped.
users=$(ps -eo user=,args= | awk '/\/opt\/saint\/venv\/bin\/python/ && / app\.py/ {print $1}' | sort -u)
n=$(tar -tf "$TAR" | wc -l)
tar -xf "$TAR" -C "$APP" --no-same-owner
rm -f "$TAR" "$APP/.halo-update.json"         # it's a dev tree now, not a release (core/updater.py)
echo "hotpatch: $n files in $APP updated (SAINT starts about 15 s after a restart)"
for u in $users; do
  pkill -u "$u" -f '/opt/saint/venv/bin/python .*app\.py' || true
  sleep 1
  # saint.service (systemctl --user) is how HalOS starts SAINT; it comes back in the background.
  systemctl --user -M "$u@" restart saint.service && echo "hotpatch: SAINT restarted for $u" \
    || echo "hotpatch: couldn't restart SAINT for $u (start it from the menu)"
done
[ -n "$users" ] || echo "hotpatch: SAINT wasn't running; it starts with the new files next time"
