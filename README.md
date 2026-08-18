# riscv-pico

![Raspberry Pi Pico W running Linux](docs/images/header.jpg)

RISC-V Linux, running on a Raspberry Pi Pico — by emulating a full RV32IMA CPU on the RP2040
itself, with SPI PSRAM standing in for system memory and an SD card holding the kernel and rootfs.

No hardware required to try it: a desktop build of the real emulator core boots the actual firmware
kernel to a Linux shell in about a second, in a real terminal app.

## Highlights

- **Boots real Linux, zero hardware.** `harness/desktop_terminal.py` — a menu-bar app (reboot,
  RAM-config switch, disk-image picker), not a raw CLI.
- **Runs real software on it.** A working cross-compiler wrote and ran a Tiny BASIC interpreter
  and real **GNU nano 7.2**, full-screen editing included — plus `curl` and a hush-compatible
  `sysinfo` (real `neofetch` needs bash, which needs an MMU this target doesn't have).
- **Working TCP/IP stack**, loopback-verified, with a second console channel bridging it toward
  the host (half-built — see [PLAN.md](PLAN.md)).
- **Firmware builds clean for all four board targets** — `pico`, `pico_w`, `pico2`, `pico2_w` —
  one script, `firmware/build.sh`.
- **Every build output is a GitHub release**, not committed history — see the table at the
  bottom.

[PLAN.md](PLAN.md) is the living state doc — decisions, open bugs, what's next. This file is just
the tour.

## Quickstart — see it boot in under a minute

```sh
harness/build.sh
gh release download net-v1 --repo flyboy-byte/riscv-pico --pattern "*.tar.gz" -O net.tar.gz
mkdir images && tar xzf net.tar.gz -C images
dd if=/dev/zero of=harness/disk.img bs=1M count=80
mformat -F -i harness/disk.img ::
mcopy -i harness/disk.img images/Image       ::IMAGE
mcopy -i harness/disk.img images/dtb         ::DTB
mcopy -i harness/disk.img images/rootfs.ext2 ::ROOTFS
python3 harness/desktop_terminal.py harness/disk.img
```

Needs `mtools` (no root required) and `PyQt6` + `python-pyte` (`sudo pacman -S python-pyte` on
Arch). Boots to a shell in a couple seconds — try `nano`, `curl --version`, `sysinfo`.

**These images won't boot under stock `mini-rv32ima`** — this firmware's emulator core has custom
block-device and console CSRs that stock builds don't implement. `harness/build.sh` builds this
repo's own desktop build of the *real* core, which does. Details in [CLAUDE.md](CLAUDE.md).

## What's in here

| Path | What | Notes |
| --- | --- | --- |
| `upstream/pico-rv32ima/` | [tvlad1234/pico-rv32ima](https://github.com/tvlad1234/pico-rv32ima) | The fork this project builds on. No longer pristine — the PSRAM port lives here. |
| `upstream/pico-rv32ima/tiny-rv32ima/` | [tvlad1234/tiny-rv32ima](https://github.com/tvlad1234/tiny-rv32ima) | The emulator core. Also edited (same port). |
| `upstream/pico-linux/` | [ElectroBoy404NotFound/pico-linux](https://github.com/ElectroBoy404NotFound/pico-linux) | Reference only, still pristine. ST7735 LCD console, 2–4 PSRAM chips, SDIO — source of the PSRAM port logic. |
| `harness/` | This project's own code | Desktop build of the real emulator core (no hardware) plus a PyQt6 terminal app to drive it. |
| `firmware/` | This project's own code | `build.sh` — one command, real-hardware `.uf2`s for all four board targets. |
| `apps/` | This project's own code | Small C programs and scripts cross-compiled/written for the target and proven running on it. |

All three `upstream/` paths are `git subtree`s with full history, so `git log -- upstream/<x>`
works and upstream changes can still be pulled — exact commands in [CLAUDE.md](CLAUDE.md).
Everything ultimately descends from [CNLohr's mini-rv32ima](https://github.com/cnlohr/mini-rv32ima).

## Writing and running your own programs

A real cross-compiler for this target (`riscv32-buildroot-linux-uclibc-gcc`, produces the `bFLT`
no-MMU binary format this kernel needs) has been built and proven — see `apps/` for working
examples (`hello.c`, a Tiny BASIC interpreter in `basic.c`, `sysinfo.sh`). The toolchain itself
isn't checked in (it's a real buildroot build, doesn't belong in git) — the rebuild recipe,
including a few real gotchas already solved so you don't have to re-discover them, is in PLAN.md's
"Cross-compile toolchain" and "Real GNU nano" sections.

## Building the firmware for real hardware

```sh
# once — Pico SDK, shallow clone with just the tinyusb submodule (~65 MB)
git clone -b 2.1.1 --depth 1 https://github.com/raspberrypi/pico-sdk.git ~/pico-sdk
git -C ~/pico-sdk submodule update --init --depth 1 lib/tinyusb

firmware/build.sh              # all four boards, into firmware/out/*.uf2
firmware/build.sh pico2_w      # or just one
```

Output is ~140 KB per board. Flash by holding BOOTSEL while plugging in the Pico — it mounts as a
USB drive called `RPI-RP2` — then copy the `.uf2` onto it. `pico-rv32ima` wants
`IMAGE`/`DTB`/`ROOTFS` in the root of a FAT16/FAT32 SD card (same images as the quickstart above);
`pico-linux` wants a single `Image` file, already shipped at `upstream/pico-linux/linux/Image`.

Real hardware bring-up (flashing, PSRAM chip testing) is parked for now — this project's current
focus is the emulator/toolchain side, which needs none of it.

## Pre-built releases

Every build output ships as a GitHub release instead of git history — keeps `git clone` small and
avoids shipping opaque binaries in commits.

| Release | What |
| --- | --- |
| [`toolchain-v2`](https://github.com/flyboy-byte/riscv-pico/releases/tag/toolchain-v2) | `riscv32-buildroot-linux-uclibc-gcc`, wchar-enabled (needed for nano/ncurses) |
| [`apps-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/apps-v1) | Prebuilt `hello`, `basic`, `nano`, `sysinfo` |
| [`rv32harness-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/rv32harness-v1) | Desktop harness binaries, x86_64 Linux |
| [`net-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/net-v1) | Kernel + rootfs — TCP/IP stack, second HVC channel, `curl`, `sysinfo` |
| [`pico-rv32ima-boards-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/pico-rv32ima-boards-v1) | Prebuilt `.uf2` firmware, all four board targets |

Grab whichever you need, or build your own — see `apps/`, `firmware/build.sh`, and PLAN.md's
"Cross-compile toolchain" section.

## Licenses

This repo's own code (`harness/`, `apps/`, `firmware/`, docs) is MIT — see [LICENSE](LICENSE).
Upstream code under `upstream/` retains its original licensing — MIT / Apache-2.0 / BSD-3, see the
`LICENSE` file in each subtree. Credit to tvlad1234, ElectroBoy404NotFound, CNLohr, and
xhackerustc.
