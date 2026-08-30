# riscv-pico

![Raspberry Pi Pico W running Linux](docs/images/header.jpg)

RISC-V Linux, running on a Raspberry Pi Pico — by emulating a full RV32IMA CPU on the RP2040
itself, with SPI PSRAM standing in for system memory and an SD card holding the kernel and rootfs.

**This works on real hardware** — a Pico H with two SPI PSRAM chips (16 MB) and an SD card boots
to a Linux shell, runs GNU nano and Lua, and drives real GPIO pins. And you can try it *without*
any hardware: a desktop build of the real emulator core boots the same kernel to a shell in about
a second, in a real terminal app.

## Highlights

- **Boots Linux on an actual Pico.** 16 MB across two SPI PSRAM chips, kernel and 60 MB rootfs off
  an SD card, shell in ~16 seconds. Full-screen GNU nano runs and saves files on it.
- **Real GPIO from the guest, two ways.** A standard `/dev/gpiochipN` chardev (`GPIO_V2` uAPI,
  `libgpiod` tools included) and the classic `/sys/class/gpio` file interface, both talking
  through custom CSRs to real RP2040 pins — wire an LED, drive it from a shell script or Lua with
  nothing but `echo`/`cat`. See [docs/GPIO_AND_BASIC_TUTORIAL.md](docs/GPIO_AND_BASIC_TUTORIAL.md).
- **Boots real Linux with zero hardware, too.** `harness/desktop_terminal.py` — a menu-bar app
  (reboot, RAM-config switch, disk-image picker), not a raw CLI.
- **Runs real software on it.** A working cross-compiler built and runs a Tiny BASIC interpreter,
  real **Lua 5.4.7**, and real **GNU nano 7.2** with full-screen editing — plus `curl` and a
  hush-compatible `sysinfo` (real `neofetch` needs bash, which needs an MMU this target doesn't
  have).
- **SSD1306 OLED status panel, hardware-verified.** Runs alongside PSRAM with no shared-power
  interference — see the wiring note below.
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
mkdir images
gh release download kernel-gpio-v2 --repo flyboy-byte/riscv-pico --pattern "*.tar.gz" -O - | tar xz -C images
gh release download net-v1 --repo flyboy-byte/riscv-pico --pattern "*.tar.gz" -O net.tar.gz
tar xzf net.tar.gz -C images dtb
dd if=/dev/zero of=harness/disk.img bs=1M count=80
mformat -F -i harness/disk.img ::
mcopy -i harness/disk.img images/Image       ::IMAGE
mcopy -i harness/disk.img images/dtb         ::DTB
mcopy -i harness/disk.img images/rootfs.ext2 ::ROOTFS
python3 harness/desktop_terminal.py harness/disk.img
```

Needs `mtools` (no root required) and `PyQt6` + `python-pyte` (`sudo pacman -S python-pyte` on
Arch). Boots to a shell in a couple seconds — try `nano`, `curl --version`, `sysinfo`, `gpioinfo
gpiochip0`. (`basic`/`lua`/`gpiotest` aren't in this rootfs — grab
[`apps-v2`](https://github.com/flyboy-byte/riscv-pico/releases/tag/apps-v2) and inject them with
`debugfs -w`, see PLAN.md's "apps/" section for the exact recipe.)

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
examples (a Tiny BASIC interpreter in `basic.c`, a GPIO chardev smoke test in `gpiotest.c`,
`sysinfo.sh`). Real Lua 5.4.7 and GNU nano 7.2 are built the same way from their unmodified
upstream sources, not vendored here. The toolchain itself isn't checked in (it's a real buildroot
build, doesn't belong in git) — the rebuild recipe, including a few real gotchas already solved so
you don't have to re-discover them, is in PLAN.md's "Cross-compile toolchain" and "Real GNU nano"
sections.

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

### Parts

Everything below is what's actually on the verified build — roughly **$20** total, no MOQs, all
single-quantity friendly. Prices are as of 2026-08 and will drift.

| Part | Qty | Notes |
| --- | --- | --- |
| Raspberry Pi Pico | 1 | Any variant. Verified on a Pico H (RP2040); firmware also builds for `pico_w`, `pico2`, `pico2_w`. |
| **APS6404L-3SQR-SN** PSRAM, SOP-8 | 2 | 8 MB each → 16 MB. Sold as [8MB PSRAM at ProtoSupplies](https://protosupplies.com/product/psram/) (~$2.39 ea, single quantity). |
| [SMD→DIP 8-pin adapter, 5-pack](https://protosupplies.com/product/pcb-smd-soic-8-msop-8-tssop-8-to-dip-adapter5-pack/) | 1 pack | ~$0.79. Headers not included. The chips are surface-mount; these put them on 0.1" pitch for breadboarding. |
| microSD breakout, SPI | 1 | Any 3.3V module labelled `3V3 CS MOSI CLK MISO GND`. |
| microSD card | 1 | **4–32 GB, FAT32.** Avoid SDXC/exFAT — Petit FatFs here only understands FAT12/16/32. |
| 10 kΩ resistor | 1 | Pull-up for `SIO2`/`SIO3` on both chips — one resistor covers all four pins. |
| SSD1306 OLED, 128×64, **I2C** (4-pin) | 0–1 | Optional status panel. Must be the I2C variant, not SPI. |
| Breadboard + jumper wires | — | |

**Get the `-SN` (SOP-8) suffix, not `-ZR`.** Same die, but `-ZR` is USON-8 — a 3×2 mm leadless
package that's far harder to hand-solder, probe, or rework. Plain `APS6404L-3SQR` with no suffix is
bare die (KGD), not a packaged part at all.

**Pin-compatible substitutes** work fine — ESP-PSRAM64H, LY68L6400, and IPUS equivalents all share
the SOP-8 pinout and the `0x5D` known-good-die ID the firmware checks. For stock across
distributors rather than a single vendor, search [Findchips](https://www.findchips.com/search/APS6404L-3SQR-SN)
or [Octopart](https://octopart.com/search?q=APS6404L-3SQR-SN).

No level shifter needed — every part here is 3.3V-native and runs off the Pico's own 3V3 rail.

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

**SSD1306 status panel** (optional, 128×64 I2C OLED — hardware-verified 2026-08-29). Four separate
jumpers; there is no free adjacent GPIO pair left on the board:

| Module | Pico |
| --- | --- |
| `VCC` | 3V3(OUT) (pin 36) |
| `GND` | GND (pin 28) |
| `SDA` | GP28 (pin 34) |
| `SCL` | GP21 (pin 27) |

Shows RAM/PSRAM config, boot stage, live MIPS, uptime and clock — it's a stats panel, not a
console. It runs on core 0, which the emulator doesn't use, and it probes at boot: with nothing
attached the firmware behaves exactly as before. Turn it off entirely with `CONSOLE_OLED 0` in
`hw_config.h`; if a panel is wired but stays blank, try `OLED_I2C_ADDR 0x3D`.

Card is plain FAT32 with `IMAGE`, `DTB`, `ROOTFS` copied to the root — no special formatting.
Full bring-up detail, including two false alarms worth not re-chasing, is in
[PLAN.md](PLAN.md)'s "First Linux boot on real hardware".

## Pre-built releases

Every build output ships as a GitHub release instead of git history — keeps `git clone` small and
avoids shipping opaque binaries in commits.

| Release | What |
| --- | --- |
| [`toolchain-v2`](https://github.com/flyboy-byte/riscv-pico/releases/tag/toolchain-v2) | `riscv32-buildroot-linux-uclibc-gcc`, wchar-enabled (needed for nano/ncurses) |
| [`pico-rv32ima-boards-v5`](https://github.com/flyboy-byte/riscv-pico/releases/tag/pico-rv32ima-boards-v5) | **Current firmware, all four boards** — two-chip 16 MB, SSD1306 status panel, GPIO CSR handler. |
| [`kernel-gpio-v2`](https://github.com/flyboy-byte/riscv-pico/releases/tag/kernel-gpio-v2) | **Current kernel + rootfs** — `/sys/class/gpio` alongside `/dev/gpiochipN`, root-rw fix, `libgpiod` tools, working `sleep`. |
| [`apps-v2`](https://github.com/flyboy-byte/riscv-pico/releases/tag/apps-v2) | **Current apps** — `basic` (bugfix), `lua`, `gpiotest`, `libgpiod` CLI tools. `nano`/`sysinfo` unchanged, still on `apps-v1`. |
| [`apps-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/apps-v1) | `nano`, `sysinfo` (still current); `hello`, old `basic` — superseded by `apps-v2`. |
| [`rv32harness-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/rv32harness-v1) | Desktop harness binaries, x86_64 Linux |
| [`net-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/net-v1) | TCP/IP stack, second HVC channel — superseded for GPIO by `kernel-gpio-v2`, still the reference for networking |

`pico-rv32ima-boards-v3`/`v4` are earlier firmware and still boot fine; `-v1`/`-v2` are superseded
(single-chip 8 MB builds, never flashed, don't boot the current rootfs).

Grab whichever you need, or build your own — see `apps/`, `firmware/build.sh`, and PLAN.md's
"Cross-compile toolchain" section.

## Licenses

This repo's own code (`harness/`, `apps/`, `firmware/`, docs) is MIT — see [LICENSE](LICENSE).
Upstream code under `upstream/` retains its original licensing — MIT / Apache-2.0 / BSD-3, see the
`LICENSE` file in each subtree. Credit to tvlad1234, ElectroBoy404NotFound, CNLohr, and
xhackerustc.
