#!/usr/bin/bash
# Runs as root over SSH inside the Halo build VM after prepare.sh: fetches the branch and builds the ISO
# in the installed Arch build host (arch-chroot). Log: /mnt/hb/root/work/build.log
set -euo pipefail
BRANCH="${1:-halo/roadmap-2026-11}"
ROOT=/mnt/hb/root
mountpoint -q /mnt/hb || { echo "run prepare.sh first" >&2; exit 1; }
mountpoint -q "$ROOT" || mount --bind "$ROOT" "$ROOT"
cp /etc/resolv.conf "$ROOT/etc/resolv.conf"
arch-chroot "$ROOT" bash -euo pipefail -c "
  if [ -d /work/src/.git ]; then
    git -C /work/src fetch -q origin '$BRANCH' && git -C /work/src checkout -q -B build FETCH_HEAD
  else
    git clone -q --branch '$BRANCH' https://github.com/uberdiz/Halo.git /work/src
  fi
  git -C /work/src log --oneline -1
  cd /work/src && packaging/arch/build_iso.sh --workdir /work/halo-build --dist /work/dist
" > "$ROOT/work/build.log" 2>&1
echo "BUILD-EXIT $?"
