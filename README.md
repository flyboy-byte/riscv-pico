# riscv-pico

A workbench for running 32-bit RISC-V Linux on a Raspberry Pi Pico, by emulating a RISC-V CPU on
the RP2040 with SPI PSRAM as system memory and an SD card holding the kernel and rootfs. Built
around two vendored upstream projects, a desktop emulator for iterating without hardware, and a
real cross-compile toolchain for writing and running your own programs on it.

**Status: real software, not just vendored reference.** Both upstreams are here with full history.
A multi-chip PSRAM port has landed (software-verified; real hardware is parked for now). A desktop
emulator boots the actual firmware's Linux kernel with zero hardware in about a second, in a real
menu-bar terminal app (reboot, RAM-config switch, disk-image picker). A working cross-compiler for
this exact target has written and run real programs on it — a Tiny BASIC interpreter, and real GNU
nano 7.2, full-screen editing included. The firmware itself builds clean for all four board targets
(`pico`, `pico_w`, `pico2`, `pico2_w`). The guest kernel has a working TCP/IP stack (loopback
verified), and a second HVC console channel for bridging it out to the host is half-built — guest→
host works, host→guest hits an open bug. See [PLAN.md](PLAN.md) for the full living state — this
file is the tour, that one is the detail.

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

The fastest way to actually see this thing work. Build the emulator (produces two binaries,
`rv32harness-8mb` and `rv32harness-16mb`, one per supported RAM config):

```sh
harness/build.sh
```

Build a FAT test image (needs `mtools`, no root required). Two kernel sources work: the upstream
`buildroot-tiny-rv32ima` images, or this project's own prebuilt image with a working TCP/IP stack
(loopback-verified — see [`net-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/net-v1)):

```sh
gh release download net-v1 --repo flyboy-byte/riscv-pico --pattern "*.tar.gz" -O net.tar.gz
mkdir images && tar xzf net.tar.gz -C images
dd if=/dev/zero of=harness/disk.img bs=1M count=80
mformat -F -i harness/disk.img ::
mcopy -i harness/disk.img images/Image    ::IMAGE
mcopy -i harness/disk.img images/dtb      ::DTB
mcopy -i harness/disk.img images/rootfs.ext2 ::ROOTFS
```

Run it in a real desktop terminal app (needs `PyQt6` and `python-pyte` — `sudo pacman -S
python-pyte` on Arch):

```sh
python3 harness/desktop_terminal.py harness/disk.img
```

Boots to a Linux shell in a couple seconds. Machine menu has reboot, a RAM-config switch (8MB/16MB),
and a disk-image picker with recent-files. Full details, including how the desktop harness fakes
PSRAM/SD without real hardware, are in PLAN.md's "Desktop harness" and "Desktop terminal app"
sections.

**These images don't boot under stock desktop `mini-rv32ima`** — see [CLAUDE.md](CLAUDE.md) for why
(short version: this firmware's emulator core isn't stock mini-rv32ima, it has custom block-device
and console CSRs). `harness/build.sh` above builds this repo's own desktop build of the *real*
core, which does work.

## Writing and running your own programs

A real cross-compiler for this target (`riscv32-buildroot-linux-uclibc-gcc`, produces the `bFLT`
no-MMU binary format this kernel needs) has been built and proven — see `apps/` for working
examples (`hello.c`, a Tiny BASIC interpreter in `basic.c`, `sysinfo.sh`), plus a real GNU nano 7.2
build (prebuilt in the [`apps-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/apps-v1)
release) — the first full-screen ncurses program proven running under the emulator. The toolchain
itself isn't checked in (it's a real buildroot build, doesn't belong in git), but the exact rebuild
recipe — including several real gotchas already solved so you don't have to re-discover them (a
`-fPIC`-vs-`-fPIE` buildroot default that crashes anything built through its normal package recipes
on this target, and a host-GCC-14+-vs-old-gnulib build failure) — is in PLAN.md's "Cross-compile
toolchain" and "Real GNU nano" sections.

The [`net-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/net-v1) rootfs also ships a
real `curl` (HTTP-only build) and `sysinfo` (a neofetch-style banner, but hush-compatible — real
neofetch needs bash, which needs an MMU this NOMMU target doesn't have, so it's a hard no here).

## Building the firmware for real hardware

Needs the Pico SDK. A shallow clone with just the tinyusb submodule is ~65 MB:

```sh
git clone -b 2.1.1 --depth 1 https://github.com/raspberrypi/pico-sdk.git ~/pico-sdk
git -C ~/pico-sdk submodule update --init --depth 1 lib/tinyusb
```

`pico-rv32ima` builds clean for all four board targets (`pico`, `pico_w`, `pico2`, `pico2_w`) —
build all of them, or just one:

```sh
firmware/build.sh              # all four, into firmware/out/*.uf2
firmware/build.sh pico2_w      # just one
```

Or drive `cmake` directly (same thing the script wraps), from `upstream/pico-rv32ima/`:

```sh
cmake -B build -DPICO_SDK_PATH=$HOME/pico-sdk -DPICO_BOARD=pico   # or pico_w / pico2 / pico2_w
cmake --build build -j$(nproc)
```

Prebuilt `.uf2`s are also in the
[`pico-rv32ima-boards-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/pico-rv32ima-boards-v1)
release if you'd rather skip building. Output is ~140 KB. Flash by holding BOOTSEL while plugging in
the Pico — it mounts as a USB drive called `RPI-RP2` — then copy the `.uf2` onto it.

`pico-rv32ima` wants `IMAGE`/`DTB`/`ROOTFS` in the root of a FAT16/FAT32 SD card (same images as
above). `pico-linux` instead wants a single `Image` file, already shipped at
`upstream/pico-linux/linux/Image`.

Real hardware bring-up (flashing, PSRAM chip testing) is parked for now — this project's current
focus is the emulator/toolchain side, which needs none of it.

## Licenses

This repo's own code (`harness/`, `apps/`, docs) is MIT — see [LICENSE](LICENSE). Upstream code
under `upstream/` retains its original licensing — MIT / Apache-2.0 / BSD-3, see the `LICENSE` file
in each subtree. Credit to tvlad1234, ElectroBoy404NotFound, CNLohr, and xhackerustc.

## Pre-built releases

Every build output for this project ships as a GitHub release instead of being checked into the
repo — keeps `git clone` small and avoids shipping opaque x86_64/RISC-V binaries in history.

| Release | What |
| --- | --- |
| [`toolchain-v2`](https://github.com/flyboy-byte/riscv-pico/releases/tag/toolchain-v2) | `riscv32-buildroot-linux-uclibc-gcc`, wchar-enabled (needed for nano/ncurses) |
| [`apps-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/apps-v1) | Prebuilt `hello`, `basic`, `nano` bFLT binaries, plus `sysinfo` |
| [`rv32harness-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/rv32harness-v1) | Desktop harness binaries (`rv32harness-8mb`/`-16mb`), x86_64 Linux |
| [`net-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/net-v1) | Kernel + rootfs with a working TCP/IP stack, a second HVC channel, `curl`, and `sysinfo` |
| [`pico-rv32ima-boards-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/pico-rv32ima-boards-v1) | Prebuilt `.uf2` firmware, all four board targets |

Grab whichever you need, or build your own from source — see `apps/` and PLAN.md's "Cross-compile
toolchain" section for the toolchain rebuild path.
