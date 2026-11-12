#!/usr/bin/bash
# HalOS boot benchmark. Run on an installed HalOS (VM or PC) right after signing in:
#   bash boot-benchmark.sh [out.json]
# Records where boot time went (firmware, loader, kernel, initrd, userspace, until the desktop's session
# target), the slowest units, idle memory after a settle, the initramfs size and the kernel command line,
# as one JSON file. Reads only; changes nothing. Numbers go into HALOS_STATUS.md.
set -u
out="${1:-halos-boot-$(date +%Y%m%d-%H%M%S).json}"
settle="${SETTLE_SECONDS:-60}"

secs() {   # "1.234s" / "567ms" / "1min 2.3s" -> seconds
  awk '{t=0; for(i=1;i<=NF;i++){v=$i; if(v~/min$/){sub(/min/,"",v);t+=v*60} else if(v~/ms$/){sub(/ms/,"",v);t+=v/1000}
        else if(v~/s$/){sub(/s/,"",v);t+=v}} printf "%.3f", t}'
}
phase() {  # the time before "(name)" in systemd-analyze's first line; 0 when that phase isn't reported
  local v
  v=$(systemd-analyze time 2>/dev/null | head -1 | grep -oE "[0-9.]+(min|ms|s)( [0-9.]+(ms|s))? \($1\)" \
      | sed "s/ ($1)//" | secs)
  echo "${v:-0}"
}

until systemctl is-system-running 2>/dev/null | grep -qE 'running|degraded'; do sleep 2; done
sleep "$settle"                                   # idle memory once first-login work has calmed down

total=$(systemd-analyze time 2>/dev/null | head -1 | grep -oE '= [0-9.]+(min|ms|s)( [0-9.]+(ms|s))?' | sed 's/= //' | secs)
graphical=$(systemd-analyze time 2>/dev/null | grep -oE 'graphical.target reached after [0-9.]+(min|ms|s)( [0-9.]+(ms|s))?' \
            | sed 's/.*after //' | secs)
blame=$(systemd-analyze blame --no-pager 2>/dev/null | head -12 | awk '{u=$NF; $NF=""; printf "%s{\"unit\":\"%s\",\"time\":\"%s\"}", (NR>1?",":""), u, $0}' \
        | sed 's/ "}/"}/g')
mem_used=$(free -m | awk '/^Mem:/{print $3}')
mem_total=$(free -m | awk '/^Mem:/{print $2}')
initrd=$(stat -c %s /boot/initramfs-linux.img 2>/dev/null || echo 0)
cmdline=$(sed 's/"/\\"/g' /proc/cmdline)
cat > "$out" <<EOF
{
  "when": "$(date -Iseconds)",
  "host": "$(systemd-detect-virt 2>/dev/null || echo unknown)",
  "kernel": "$(uname -r)",
  "firmware_s": $(phase firmware),
  "loader_s": $(phase loader),
  "kernel_s": $(phase kernel),
  "initrd_s": $(phase initrd),
  "userspace_s": $(phase userspace),
  "total_s": ${total:-0},
  "graphical_target_s": ${graphical:-0},
  "slowest_units": [${blame}],
  "idle_ram_used_mb": ${mem_used:-0},
  "ram_total_mb": ${mem_total:-0},
  "initramfs_bytes": ${initrd},
  "cmdline": "${cmdline}"
}
EOF
echo "$out"
cat "$out"
