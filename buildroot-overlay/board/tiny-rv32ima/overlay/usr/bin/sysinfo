#!/bin/sh
# riscv-pico sysinfo — a neofetch-style banner for the guest, written for busybox hush.
# Real neofetch needs bash, which needs an MMU this target doesn't have (NOMMU/RV32IMA) —
# hush is a POSIX-ish shell, no bashisms (no arrays, no [[ ]]) so this works here instead.

KERNEL=$(uname -sr)
ARCH=$(uname -m)
HOST=$(uname -n)

MEMTOTAL=""
MEMFREE=""
while read -r line; do
    case "$line" in
        MemTotal:*) MEMTOTAL=${line#MemTotal:} ;;
        MemFree:*) MEMFREE=${line#MemFree:} ;;
    esac
done < /proc/meminfo
MEMTOTAL=$(echo $MEMTOTAL)
MEMFREE=$(echo $MEMFREE)

UPTIME_SEC=$(cat /proc/uptime)
UPTIME_SEC=${UPTIME_SEC%%.*}
MIN=$((UPTIME_SEC / 60))
SEC=$((UPTIME_SEC % 60))

cat <<'BANNER'
   _     _
  (_)___(_)_____ __   ___  __(_)______
 / / __/ / ___/ /  |/  / / / / ___/ __ \
/ / /_/ / /__/ /   ___/ /_/ / /__/ /_/ /
/_/\__/_/\___/_/  /_/ \__,_/\___/\____/
BANNER

echo "-------------------------------"
echo "OS:      $KERNEL"
echo "Arch:    $ARCH ($ARCH-emulated, no MMU)"
echo "Host:    $HOST"
echo "Mem:     ${MEMFREE} free / ${MEMTOTAL} total"
echo "Uptime:  ${MIN}m ${SEC}s"
