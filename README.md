# riscv-pico

A workbench for running 32-bit RISC-V Linux on a Raspberry Pi Pico, by emulating a RISC-V CPU on
the RP2040 with SPI PSRAM as system memory and an SD card holding the kernel and rootfs. Built
around two vendored upstream projects, a desktop emulator for iterating without hardware, and a
real cross-compile toolchain for writing and running your own programs on it.

**Status: real software, not just vendored reference.** Both upstreams are here with full history.
A multi-chip PSRAM port has landed (software-verified; real hardware is parked for now). A desktop
emulator boots the actual firmware's Linux kernel with zero hardware in about a second, with a real
terminal app to drive it. A working cross-compiler for this exact target has been used to write and
run real programs, including a Tiny BASIC interpreter. See [PLAN.md](PLAN.md) for the full living
state — this file is the tour, that one is the detail.

## What's in here

| Path | What | Notes |
| --- | --- | --- |
| `upstream/pico-rv32ima/` | [tvlad1234/pico-rv32ima](https://github.com/tvlad1234/pico-rv32ima) | The fork this project builds on. No longer pristine — the PSRAM port lives here. |
| `upstream/pico-rv32ima/tiny-rv32ima/` | [tvlad1234/tiny-rv32ima](https://github.com/tvlad1234/tiny-rv32ima) | The emulator core. Also edited (same port). |
| `upstream/pico-linux/` | [ElectroBoy404NotFound/pico-linux](https://github.com/ElectroBoy404NotFound/pico-linux) | Reference only, still pristine. ST7735 LCD console, 2–4 PSRAM chips, SDIO — source of the PSRAM port logic. |
| `harness/` | This project's own code | Desktop build of the real emulator core (no hardware) plus a PyQt6 terminal app to drive it. |
| `apps/` | This project's own code | Small C programs cross-compiled for the target and proven running on it. |

All three `upstream/` paths are `git subtree`s with full history, so `git log -- upstream/<x>`
works and upstream changes can still be pulled. See [CLAUDE.md](CLAUDE.md) for the exact commands.

Everything ultimately descends from [CNLohr's mini-rv32ima](https://github.com/cnlohr/mini-rv32ima).

## Running it without any hardware

The fastest way to actually see this thing work. Build the emulator:

```sh
TINY=upstream/pico-rv32ima/tiny-rv32ima
gcc -O1 -g -Wall -I harness -I $TINY/emulator -I $TINY/psram -I $TINY/cache -I $TINY/pff \
  harness/main.c harness/console.c harness/diskio.c \
  $TINY/emulator/emulator.c $TINY/cache/cache.c $TINY/psram/psram.c $TINY/pff/pff.c \
  -o harness/rv32harness
```

Build a FAT test image (needs `mtools`, no root required) with a kernel from the
[buildroot-tiny-rv32ima](https://github.com/tvlad1234/buildroot-tiny-rv32ima) releases:

```sh
gh release download v1.0 --repo tvlad1234/buildroot-tiny-rv32ima --pattern images.zip
mkdir images && cd images && unzip ../images.zip && cd ..
dd if=/dev/zero of=harness/disk.img bs=1M count=80
mformat -F -i harness/disk.img ::
mcopy -i harness/disk.img images/Image ::IMAGE
mcopy -i harness/disk.img images/dtb   ::DTB
mcopy -i harness/disk.img images/rootfs ::ROOTFS
```

Run it in a real desktop terminal app (needs `PyQt6` and `python-pyte` — `sudo pacman -S
python-pyte` on Arch):

```sh
python3 harness/desktop_terminal.py harness/disk.img
```

Boots to a Linux shell in a couple seconds. Full details, including how the desktop harness fakes
PSRAM/SD without real hardware, are in PLAN.md's "Desktop harness" and "Desktop terminal app"
sections.

**These downloaded images don't boot under stock desktop `mini-rv32ima`** — see
[CLAUDE.md](CLAUDE.md) for why (short version: this firmware's emulator core isn't stock
mini-rv32ima, it has custom block-device CSRs). `harness/rv32harness` above is this repo's own
desktop build of the *real* core, which does work.

## Writing and running your own programs

A real cross-compiler for this target (`riscv32-buildroot-linux-uclibc-gcc`, produces the `bFLT`
no-MMU binary format this kernel needs) has been built and proven — see `apps/` for working
examples (`hello.c`, a Tiny BASIC interpreter in `basic.c`). The toolchain itself isn't checked in
(it's a real buildroot build, doesn't belong in git), but the exact rebuild recipe — including two
real gotchas already solved so you don't have to re-discover them — is in PLAN.md's "Cross-compile
toolchain" section.

## Building the firmware for real hardware

Needs the Pico SDK. A shallow clone with just the tinyusb submodule is ~65 MB:

```sh
git clone -b 2.1.1 --depth 1 https://github.com/raspberrypi/pico-sdk.git ~/pico-sdk
git -C ~/pico-sdk submodule update --init --depth 1 lib/tinyusb
```

Then, from either project's directory:

```sh
cmake -B build -DPICO_SDK_PATH=$HOME/pico-sdk -DPICO_BOARD=pico   # pico2 for RP2350
cmake --build build -j$(nproc)
```

Output is `build/pico-rv32ima/pico-rv32ima.uf2` (~140 KB) in both. Flash by holding BOOTSEL while
plugging in the Pico — it mounts as a USB drive called `RPI-RP2` — then copy the `.uf2` onto it.

`pico-rv32ima` wants `IMAGE`/`DTB`/`ROOTFS` in the root of a FAT16/FAT32 SD card (same images as
above). `pico-linux` instead wants a single `Image` file, already shipped at
`upstream/pico-linux/linux/Image`.

Real hardware bring-up (flashing, PSRAM chip testing) is parked for now — this project's current
focus is the emulator/toolchain side, which needs none of it.

## Licenses

Upstream code retains its original licensing — MIT / Apache-2.0 / BSD-3, see the `LICENSE` file in
each subtree. Credit to tvlad1234, ElectroBoy404NotFound, CNLohr, and xhackerustc.
