#!/usr/bin/bash
# Runs as root over SSH inside the Halo *build* VM (Arch live ISO in VirtualBox). Never on a real PC.
#  1. formats the VM's empty virtual disk (only a VBOX HARDDISK with no partitions and no signature) and mounts it
#  2. installs a full Arch system on it (the build host), so builds don't use the live session's RAM overlay
set -euo pipefail
[ "$(systemd-detect-virt)" = oracle ] || { echo "not a VirtualBox VM; refusing" >&2; exit 1; }
MNT=/mnt/hb
mkdir -p "$MNT"
if ! mountpoint -q "$MNT"; then
  if [ -e /dev/disk/by-label/halobuild ]; then
    mount /dev/disk/by-label/halobuild "$MNT"
  else
    d=/dev/sda
    model=$(cat /sys/block/sda/device/model 2>/dev/null | xargs)
    parts=$(find /sys/block/sda -maxdepth 1 -name 'sda[0-9]*' | wc -l)
    sig=$(wipefs --no-act --noheadings "$d" | wc -l)
    size_gb=$(( $(cat /sys/block/sda/size) * 512 / 1000000000 ))
    if [ "$model" = "VBOX HARDDISK" ] && [ "$parts" -eq 0 ] && [ "$sig" -eq 0 ] && [ "$size_gb" -ge 100 ]; then
      mkfs.ext4 -q -L halobuild "$d"
      mount "$d" "$MNT"
    else
      echo "refusing: $d is model=$model parts=$parts signatures=$sig size=${size_gb}GB" >&2; exit 1
    fi
  fi
fi
ROOT="$MNT/root"
if [ ! -e "$ROOT/etc/arch-release" ]; then
  mount -o remount,size=4G /run/archiso/cowspace 2>/dev/null || true
  systemctl is-active -q pacman-init.service || systemctl start pacman-init.service
  mkdir -p "$ROOT"
  pacstrap -K "$ROOT" base base-devel git sudo openssh rsync >/dev/null
fi
cp /etc/resolv.conf "$ROOT/etc/resolv.conf"
mkdir -p "$ROOT/work"
echo "BUILD-HOST-READY $(df -h --output=avail "$MNT" | tail -n1)"
