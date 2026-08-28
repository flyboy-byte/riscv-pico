# riscv-pico

![Raspberry Pi Pico W running Linux](docs/images/header.jpg)

RISC-V Linux, running on a Raspberry Pi Pico — by emulating a full RV32IMA CPU on the RP2040
itself, with SPI PSRAM standing in for system memory and an SD card holding the kernel and rootfs.

**This works on real hardware** — a Pico H with two SPI PSRAM chips (16 MB) and an SD card boots
to a Linux shell and runs GNU nano. And you can try it *without* any hardware: a desktop build of
the real emulator core boots the same kernel to a shell in about a second, in a real terminal app.

## Highlights

- **Boots Linux on an actual Pico.** 16 MB across two SPI PSRAM chips, kernel and 60 MB rootfs off
  an SD card, shell in ~16 seconds. Full-screen GNU nano runs and saves files on it.
- **Boots real Linux with zero hardware, too.** `harness/desktop_terminal.py` — a menu-bar app
  (reboot, RAM-config switch, disk-image picker), not a raw CLI.
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

### Wiring (verified working, 2026-08-27)

Console is USB-CDC — no extra adapter needed. All parts are 3.3V-native, so no level shifting.

**Two PSRAM chips** (APS6404L / ESP-PSRAM64H, SOP-8). They share the SPI bus and differ only in
chip-select:

| Chip pin | Signal | Chip 1 | Chip 2 |
| --- | --- | --- | --- |
| 1 | `/CE` | GP13 (pin 17) | GP14 (pin 19) |
| 2 | `SO` | GP12 (pin 16) | GP12 — shared |
| 5 | `SI` | GP11 (pin 15) | GP11 — shared |
| 6 | `SCLK` | GP10 (pin 14) | GP10 — shared |
| 3, 7 | `SIO2`, `SIO3` | → 3V3 via one shared 10 kΩ | same |
| 4, 8 | `VSS`, `VDD` | GND, 3V3 | GND, 3V3 |

`SIO2`/`SIO3` are unused in SPI mode. Pull them **high**, not low — some pin-compatible parts put
an active-low `/RESET` or `/HOLD` on `SIO3`. One 10 kΩ for all four pins is fine; nothing ever
drives them.

**SD card module** (`3V3, CS, MOSI, CLK, MISO, GND`):

| Module | Pico |
| --- | --- |
| `CS` | GP0 (pin 1) |
| `MOSI` | GP3 (pin 5) |
| `CLK` | GP2 (pin 4) |
| `MISO` | GP4 (pin 6) |

⚠️ **`MOSI` and `CLK` cross** — the module's header order doesn't match the Pico's pin order. This
is the easiest mistake to make here.

**The default build is now two-chip / 16 MB** (`PSRAM_TWO_CHIPS 1` in `hw_config.h`,
`EMULATOR_RAM_MB 16` in `vm_config.h`). For a single 8 MB chip, set both back to `0` and `8` —
mismatching them is a compile-time `#error`, not a silent address-wrap bug.
`PSRAM_SPI_SPEED_MHZ` defaults to 20, stable even on flying leads.

Card is plain FAT32 with `IMAGE`, `DTB`, `ROOTFS` copied to the root — no special formatting.
Full bring-up detail, including two false alarms worth not re-chasing, is in
[PLAN.md](PLAN.md)'s "First Linux boot on real hardware".

## Pre-built releases

Every build output ships as a GitHub release instead of git history — keeps `git clone` small and
avoids shipping opaque binaries in commits.

| Release | What |
| --- | --- |
| [`toolchain-v2`](https://github.com/flyboy-byte/riscv-pico/releases/tag/toolchain-v2) | `riscv32-buildroot-linux-uclibc-gcc`, wchar-enabled (needed for nano/ncurses) |
| [`apps-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/apps-v1) | Prebuilt `hello`, `basic`, `nano`, `sysinfo` |
| [`rv32harness-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/rv32harness-v1) | Desktop harness binaries, x86_64 Linux |
| [`net-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/net-v1) | Kernel + rootfs — TCP/IP stack, second HVC channel, `curl`, `sysinfo` |
| [`pico-rv32ima-boards-v2`](https://github.com/flyboy-byte/riscv-pico/releases/tag/pico-rv32ima-boards-v2) | **Prebuilt `.uf2` firmware, all four boards — two-chip 16 MB, verified booting on real hardware.** Plus `sdtest.uf2`, a standalone SD-over-SPI diagnostic. |

`pico-rv32ima-boards-v1` is superseded — it holds the single-chip 8 MB builds, which were never
flashed and no longer boot the current rootfs.

Grab whichever you need, or build your own — see `apps/`, `firmware/build.sh`, and PLAN.md's
"Cross-compile toolchain" section.

## Licenses

This repo's own code (`harness/`, `apps/`, `firmware/`, docs) is MIT — see [LICENSE](LICENSE).
Upstream code under `upstream/` retains its original licensing — MIT / Apache-2.0 / BSD-3, see the
`LICENSE` file in each subtree. Credit to tvlad1234, ElectroBoy404NotFound, CNLohr, and
xhackerustc.
