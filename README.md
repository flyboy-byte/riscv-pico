# riscv-pico

![Raspberry Pi Pico W running Linux](docs/images/header.jpg)

A $4 microcontroller has no business running Linux. It has no MMU, no real RAM to speak of, and
was never meant to run an OS. This project makes it happen anyway: the RP2040 software-emulates a
full RV32IMA CPU, two SPI PSRAM chips stand in for system memory, and an SD card holds the kernel
and root filesystem. The result boots to a real Linux shell, on a Pico, that you can SSH-flavored
poke at over USB serial.

It actually works. A Pico H with 16 MB of PSRAM and an SD card boots to a shell, runs GNU nano and
Lua, and drives real GPIO pins from a shell script. If you don't have the hardware yet, you can
still try the whole thing on your own machine — a desktop build of the *real* emulator core boots
the same kernel to a shell in about a second, no Pico required.

## What it actually does

- **Boots Linux on real hardware.** 16 MB across two SPI PSRAM chips, kernel + 60 MB rootfs off an
  SD card, shell in about 16 seconds. Full-screen `nano` runs and saves files on it, like a real
  computer.
- **Same thing with zero hardware.** `harness/desktop_terminal.py` is a proper little app (reboot
  button, RAM-config switch, disk-image picker) wrapping the real emulator core — not a toy stub.
- **Real GPIO, from Linux, driving real pins.** Wire an LED to a Pico pin and turn it on with
  `echo 1 > /sys/class/gpio/gpio512/value`, or use the standard `/dev/gpiochipN` chardev API and
  `libgpiod` tools instead — both are wired through to real RP2040 GPIO under the hood. Details in
  [docs/GPIO_AND_BASIC_TUTORIAL.md](docs/GPIO_AND_BASIC_TUTORIAL.md).
- **A real cross-compiler, and real software running on it.** Tiny BASIC, Lua 5.4.7, GNU nano 7.2
  (full-screen editing and all), `curl`, and a `sysinfo` command all run on the actual guest — not
  simulated, not stubbed.
- **An OLED status panel, if you want one.** SSD1306, I2C, hardware-verified — shows RAM config,
  boot stage, live MIPS, uptime.
- **A working TCP/IP stack**, loopback-verified, with a second console channel reaching toward the
  host (half-built, see [PLAN.md](PLAN.md) if you want to help finish it).
- **Firmware builds clean for all four Pico variants** — `pico`, `pico_w`, `pico2`, `pico2_w` —
  with one script.
- **Every build ships as a GitHub release**, not as binaries bloating the git history.

[PLAN.md](PLAN.md) is the living state doc — every decision, every bug, what's next. This file is
just the tour.

## See it boot, in under a minute, no hardware needed

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

You'll need `mtools` (no root required) and `PyQt6` + `python-pyte` (`sudo pacman -S python-pyte`
on Arch). It boots to a shell in a couple of seconds — poke around with `nano`, `curl --version`,
`sysinfo`, `gpioinfo gpiochip0`. (`basic`/`lua`/`gpiotest` aren't in this particular rootfs — grab
[`apps-v2`](https://github.com/flyboy-byte/riscv-pico/releases/tag/apps-v2) and inject them with
`debugfs -w` if you want them too; the exact recipe is in PLAN.md's "apps/" section.)

One thing worth knowing: **these disk images won't boot under stock `mini-rv32ima`.** This
project's emulator core has custom block-device and console CSRs that the stock upstream doesn't
implement, so `harness/build.sh` builds this repo's own desktop copy of the *real* core instead.
More on why in [CLAUDE.md](CLAUDE.md).

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
works and upstream changes can still be pulled in — exact commands in [CLAUDE.md](CLAUDE.md).
Everything here ultimately descends from [CNLohr's mini-rv32ima](https://github.com/cnlohr/mini-rv32ima).

## Writing and running your own programs

There's a real, working cross-compiler for this target
(`riscv32-buildroot-linux-uclibc-gcc`, producing the `bFLT` no-MMU binary format the kernel
actually needs). `apps/` has working examples to copy from — a Tiny BASIC interpreter (`basic.c`),
a GPIO chardev smoke test (`gpiotest.c`), `sysinfo.sh`. Real Lua 5.4.7 and GNU nano 7.2 are built
the exact same way, straight from their unmodified upstream sources — they're not vendored into
this repo. The toolchain itself isn't checked in (it's a full buildroot build, doesn't belong in
git) — the rebuild recipe, including a few real gotchas already solved so you don't have to
re-discover them, is in PLAN.md's "Cross-compile toolchain" and "Real GNU nano" sections.

## Building the firmware for real hardware

```sh
# once — Pico SDK, shallow clone with just the tinyusb submodule (~65 MB)
git clone -b 2.1.1 --depth 1 https://github.com/raspberrypi/pico-sdk.git ~/pico-sdk
git -C ~/pico-sdk submodule update --init --depth 1 lib/tinyusb

firmware/build.sh              # all four boards, into firmware/out/*.uf2
firmware/build.sh pico2_w      # or just one
```

Output is about 140 KB per board. Flash it by holding BOOTSEL while plugging in the Pico — it
mounts as a USB drive called `RPI-RP2` — then copy the `.uf2` onto it. `pico-rv32ima` wants
`IMAGE`/`DTB`/`ROOTFS` sitting in the root of a FAT16/FAT32 SD card (same images as the quickstart
above); `pico-linux` wants a single `Image` file, already shipped at
`upstream/pico-linux/linux/Image`.

### Parts you'll need

Everything below is what's actually on the verified build — roughly **$20** total, no minimum
order quantities, all single-quantity friendly. Prices are as of 2026-08 and will drift.

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

**Pin-compatible substitutes work fine** — ESP-PSRAM64H, LY68L6400, and IPUS equivalents all share
the SOP-8 pinout and the `0x5D` known-good-die ID the firmware checks for. For stock across
distributors rather than a single vendor, search [Findchips](https://www.findchips.com/search/APS6404L-3SQR-SN)
or [Octopart](https://octopart.com/search?q=APS6404L-3SQR-SN).

No level shifter needed anywhere — every part here is 3.3V-native and runs off the Pico's own 3V3
rail.

### Wiring (verified working, 2026-08-27)

Console is USB-CDC — no extra adapter needed. Everything's 3.3V-native, so no level shifting
anywhere.

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
an active-low `/RESET` or `/HOLD` on `SIO3`. One 10 kΩ resistor covers all four pins; nothing ever
actually drives them.

**SD card module** (`3V3, CS, MOSI, CLK, MISO, GND`):

| Module | Pico |
| --- | --- |
| `CS` | GP0 (pin 1) |
| `MOSI` | GP3 (pin 5) |
| `CLK` | GP2 (pin 4) |
| `MISO` | GP4 (pin 6) |

⚠️ **`MOSI` and `CLK` cross** — the module's header order doesn't match the Pico's pin order. This
is the easiest mistake to make on the whole board.

**The default build is two-chip / 16 MB** (`PSRAM_TWO_CHIPS 1` in `hw_config.h`,
`EMULATOR_RAM_MB 16` in `vm_config.h`). Going single-chip? Set both back to `0` and `8` —
mismatching them is a compile-time `#error`, not a silent address-wrap bug that'll bite you later.
`PSRAM_SPI_SPEED_MHZ` defaults to 20, which stays stable even on janky flying leads.

**SSD1306 status panel** (optional, 128×64 I2C OLED — hardware-verified 2026-08-29). Four separate
jumpers; there's no free adjacent GPIO pair left on the board for it:

| Module | Pico |
| --- | --- |
| `VCC` | 3V3(OUT) (pin 36) |
| `GND` | GND (pin 28) |
| `SDA` | GP28 (pin 34) |
| `SCL` | GP21 (pin 27) |

It shows RAM/PSRAM config, boot stage, live MIPS, uptime, and clock — a stats panel, not a second
console. It runs on core 0, which the emulator never touches, and probes for the panel at boot: if
nothing's attached the firmware behaves exactly as if the code weren't there. Turn it off entirely
with `CONSOLE_OLED 0` in `hw_config.h`; if a panel is wired up but stays blank, try
`OLED_I2C_ADDR 0x3D`.

The SD card itself is just plain FAT32 with `IMAGE`, `DTB`, `ROOTFS` copied to the root — no
special formatting needed. Full bring-up detail, including two false alarms not worth re-chasing,
is in [PLAN.md](PLAN.md)'s "First Linux boot on real hardware".

## Pre-built releases

Every build output ships as a GitHub release instead of living in git history — keeps `git clone`
fast and avoids shipping opaque binaries in commits.

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
(single-chip 8 MB builds that were never flashed and don't boot the current rootfs anyway).

Grab whichever you need, or build your own — see `apps/`, `firmware/build.sh`, and PLAN.md's
"Cross-compile toolchain" section.

## Licenses

This repo's own code (`harness/`, `apps/`, `firmware/`, docs) is MIT — see [LICENSE](LICENSE).
Everything under `upstream/` keeps its original licensing — MIT / Apache-2.0 / BSD-3, see the
`LICENSE` file in each subtree. Credit to tvlad1234, ElectroBoy404NotFound, CNLohr, and
xhackerustc, whose work this whole thing stands on.
