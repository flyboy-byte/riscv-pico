#!/usr/bin/env bash
# Builds real pico-rv32ima firmware .uf2s for actual hardware. All four board targets
# build clean from the same source (verified 2026-08-17, see PLAN.md D-007) - this just
# wraps the per-board CMake invocation so it's one command instead of four.
#
# Usage:
#   firmware/build.sh              # builds all four boards
#   firmware/build.sh pico2_w      # builds just one (pico | pico_w | pico2 | pico2_w)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="$SCRIPT_DIR/out"
cd "$SCRIPT_DIR/../upstream/pico-rv32ima"

PICO_SDK_PATH="${PICO_SDK_PATH:-$HOME/pico-sdk}"
if [ ! -d "$PICO_SDK_PATH" ]; then
    echo "error: Pico SDK not found at $PICO_SDK_PATH" >&2
    echo "  set PICO_SDK_PATH, or see README.md's \"Building the firmware for real hardware\" section" >&2
    exit 1
fi

ALL_BOARDS=(pico pico_w pico2 pico2_w)
if [ $# -eq 0 ]; then
    BOARDS=("${ALL_BOARDS[@]}")
else
    BOARDS=("$1")
fi

mkdir -p "$OUT_DIR"

for BOARD in "${BOARDS[@]}"; do
    echo "=== building $BOARD ==="
    BUILD_DIR="build_${BOARD}"
    cmake -B "$BUILD_DIR" -DPICO_SDK_PATH="$PICO_SDK_PATH" -DPICO_BOARD="$BOARD" >/dev/null
    cmake --build "$BUILD_DIR" -j"$(nproc)"
    cp "$BUILD_DIR/pico-rv32ima/pico-rv32ima.uf2" "$OUT_DIR/pico-rv32ima-${BOARD}.uf2"
    echo "-> firmware/out/pico-rv32ima-${BOARD}.uf2"
done
