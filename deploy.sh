#!/usr/bin/bash
# Copy the changes made in ~/saint-dev into the live SAINT (/opt/saint/app) and restart SAINT so they load.
# Only files changed since the baseline copy are copied. A full backup of the old code is in ~/saint-backup.
set -euo pipefail
cd "$(dirname "$0")"
mapfile -t FILES < <(git status --porcelain --untracked-files=all | awk '{print $2}' | grep -v -E '__pycache__|^deploy\.sh$')
echo "Copying ${#FILES[@]} files into /opt/saint/app"
if [ -w /opt/saint/app/app.py ]; then SUDO=""; else SUDO="sudo"; fi
for f in "${FILES[@]}"; do
  $SUDO install -D -m 644 "$f" "/opt/saint/app/$f"
done
git add -A >/dev/null && git -c user.name=deploy -c user.email=deploy@local commit -qm "deployed $(date +%F\ %T)" || true

echo "Restarting SAINT…"
pkill -f 'ui.halo_app' || true
pkill -f 'ui.wallpapers_app' || true
pkill -f 'ui.store_app' || true
pkill -f '/opt/saint/venv/bin/python app.py' || true
sleep 2
cd /opt/saint/app
setsid -f /usr/bin/saint --background >/dev/null 2>&1
echo "Done. Open Evolve from the app menu (or: /opt/saint/venv/bin/python -m ui.evolve_app)."
