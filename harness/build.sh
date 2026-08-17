#!/usr/bin/env bash
# Builds the desktop harness in its supported RAM configs (8MB / 16MB), producing
# rv32harness-8mb and rv32harness-16mb. desktop_terminal.py picks between them at launch.
set -euo pipefail
cd "$(dirname "$0")"

TINY=../upstream/pico-rv32ima/tiny-rv32ima

for MB in 8 16; do
    gcc -O1 -g -Wall -DEMULATOR_RAM_MB=${MB} \
        -I. -I "$TINY/emulator" -I "$TINY/psram" -I "$TINY/cache" -I "$TINY/pff" \
        main.c console.c diskio.c netchan.c \
        "$TINY/emulator/emulator.c" "$TINY/cache/cache.c" "$TINY/psram/psram.c" "$TINY/pff/pff.c" \
        -o "rv32harness-${MB}mb"
    echo "built rv32harness-${MB}mb"
done
