<p align="center">
  <img src="docs/images/header.jpg" alt="" width="72%">
</p>

<h1 align="center">riscv-pico</h1>

<p align="center">
  <strong>A Raspberry Pi Pico running real Linux, with its own keyboard and screen.</strong><br>
  The RP2040 emulates a RISC-V CPU, SPI PSRAM becomes system memory,<br>
  and the Linux guest drives real GPIO pins.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/board-RP2040-c51a4a" alt="RP2040">
  <img src="https://img.shields.io/badge/guest-Linux%206.6-informational" alt="Linux 6.6">
  <img src="https://img.shields.io/badge/CPU-RV32IMA%20(emulated)-5c4ee5" alt="RV32IMA">
  <img src="https://img.shields.io/badge/RAM-16%20MB%20SPI%20PSRAM-orange" alt="16MB PSRAM">
  <img src="https://img.shields.io/badge/console-PS%2F2%20%2B%20VGA-2e8b57" alt="PS/2 + VGA">
</p>

<p align="center">
  <a href="https://flyboy-byte.github.io/riscv-pico/"><b>Website</b></a> •
  <a href="#try-it-in-60-seconds-no-hardware">Try it</a> •
  <a href="#how-it-actually-works">How it works</a> •
  <a href="#build-one-yourself">Build one</a> •
  <a href="#programming-on-the-pico">Programming</a> •
  <a href="#downloads">Downloads</a> •
  <a href="PLAN.md">PLAN.md</a>
</p>

---

> [!NOTE]
> **This is a build log, not an upstream improvement.** It's my own vibe-coded "Linux on a Pico"
> project — the real projects below did the hard work; this repo forks, ports, and glues them
> together and writes down what happened. Posted in case it's useful to someone chasing the same
> idea. The code, docs, and this README were written by
> [Claude Code](https://claude.com/claude-code); I directed it, tested on real hardware, and made
> the calls.

### Built on

| Project | What it gave this repo |
| --- | --- |
| **[tvlad1234/pico-rv32ima](https://github.com/tvlad1234/pico-rv32ima)** + **[tiny-rv32ima](https://github.com/tvlad1234/tiny-rv32ima)** | **The fork point.** Actively maintained, the emulator core, and the VGA and PS/2 console code. |
| [ElectroBoy404NotFound/pico-linux](https://github.com/ElectroBoy404NotFound/pico-linux) | The multi-chip PSRAM port and LCD console approach. |
| [cnlohr/mini-rv32ima](https://github.com/cnlohr/mini-rv32ima) | The original RV32IMA-in-C emulator all of the above descends from. |
| [xhackerustc/uc-rv32ima](https://github.com/xhackerustc/uc-rv32ima) | The cache implementation this actually runs. |
| [rswier/c4](https://github.com/rswier/c4) via [tvlad1234/c4](https://github.com/tvlad1234/c4) | The C compiler that runs on the machine itself. |

**Go star their repos, not this one.**

---

## The short version

A Pico has no MMU and about 264 KB of RAM. It was never meant to run an operating system. So:
core 1 of the RP2040 runs a full RV32IMA interpreter, two SPI PSRAM chips stand in for system
memory, and an SD card holds the kernel and root filesystem. Linux boots on top of that — and
custom kernel drivers let the guest reach back out through the emulator to drive **real hardware**.

Add a PS/2 keyboard, a VGA monitor and a breadboard power supply, and it runs with no computer
attached. You can write a program in nano on the Pico, run it, and have it blink an LED.

<p align="center">
  <img src="docs/images/breadboard.jpg" alt="The build on a breadboard — Pico, PSRAM, SD card, and an OLED showing live stats" width="90%">
</p>

<p align="center"><sub>The OLED is reporting on the machine it's plugged into: 16 MB across 2 chips, live MIPS, uptime, 400 MHz clock.</sub></p>

---

## Status

What's actually verified, versus what merely compiles. No wishful thinking in this table.

| | Feature | Notes |
|---|---|---|
| ✅ | **Linux boots on a real Pico** | RP2040, 16 MB PSRAM, 60 MB rootfs off SD. Shell in well under a minute. |
| ✅ | **Runs standalone** | PS/2 keyboard in, VGA out, its own power supply. Files edited and saved with no PC attached. |
| ✅ | **GPIO from Linux → real pins** | Both `/dev/gpiochipN` (chardev + `libgpiod`) *and* `/sys/class/gpio`. Verified lighting an actual LED. |
| ✅ | **Runs real software** | Tiny BASIC, Lua 5.4.7, GNU nano 7.2 (full-screen), `sysinfo`, and minesweeper. |
| 🚧 | **nano on the VGA screen** | Firmware v6 rewrote the VGA terminal so nano draws correctly at 53×30. It matches a reference emulator on recorded nano sessions; first hardware run pending. On v5, nano over VGA is unusable. |
| ✅ | **Custom kernel drivers** | Block device, GPIO, second console channel — real Linux drivers, not shims. |
| ✅ | **Desktop harness** | Boots the same kernel on your PC in about a second. No hardware needed. |
| ✅ | **SSD1306 OLED panel** | A live stats visualizer. Not essential, just fun. |
| ✅ | **Programming on the Pico** | Lua with sleep and raw key input, and GPIO from Lua and the shell, verified on hardware. Minesweeper too. The c4 C compiler and BASIC's exit command run in the harness and haven't been reported from hardware yet. |
| ✅ | **Slimmer kernel** | Networking removed, about 1 MB of RAM back. Boots on hardware. |
| 🚧 | **`pico2` / `pico2_w` (RP2350)** | Builds clean for all four board targets. Never actually flashed. |
| ❌ | **Networking on the Pico** | Removed on purpose for the RAM. The stack and a half-built host bridge live on in [`net-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/net-v1). |
| ❌ | **I²C / SPI / PWM / ADC for the guest** | Documented as an idea in [PLAN.md](PLAN.md). Deliberately not built. |

---

## Try it in 60 seconds (no hardware)

A desktop build of the **real** emulator core, booting the same SD card image the Pico uses.

```sh
git clone https://github.com/flyboy-byte/riscv-pico && cd riscv-pico
harness/build.sh

mkdir images
REL=https://github.com/flyboy-byte/riscv-pico/releases/download/sdcard-v2
curl -L $REL/riscv-pico-sdcard-v2.tar.gz | tar xz -C images

# lay the three files out on a FAT image, the way the firmware expects
dd if=/dev/zero of=harness/disk.img bs=1M count=80
mformat -F -i harness/disk.img ::
mcopy -i harness/disk.img images/IMAGE images/DTB images/ROOTFS ::

python3 harness/desktop_terminal.py harness/disk.img
```

Needs `mtools`, plus `PyQt6` and `python-pyte` (`sudo pacman -S python-pyte` on Arch). Boots to a
shell in a couple of seconds. Then try:

| Command | What happens |
| --- | --- |
| `lua /root/blink.lua 3` | Blinks GPIO line 0 three times. The harness prints each pin change |
| `c4 /root/hello.c` | Compiles and runs C on the emulated machine |
| `basic` | Tiny BASIC. `BYE` gets you back out |
| `lua /root/mines.lua` | Minesweeper. Arrow keys, space digs, `f` flags, `q` quits |
| `nano`, `sysinfo`, `gpioinfo gpiochip0` | Editor, system banner, the GPIO chip |

> [!IMPORTANT]
> **These images won't boot under stock `mini-rv32ima`.** This project's emulator core adds custom
> block-device and console CSRs that upstream doesn't implement, so `harness/build.sh` builds this
> repo's own desktop copy of the *real* core instead. Background in [CLAUDE.md](CLAUDE.md).

---

## How it actually works

The interesting part isn't that Linux boots. It's that the emulated guest can reach **real
hardware** — so `echo 1 > /sys/class/gpio/gpio512/value`, typed into a Linux shell, ends with
current flowing out of a physical pin.

```
┌─────────────────────────────────────────────────────────────────┐
│  RISC-V Linux guest                                 (emulated)  │
│                                                                 │
│      shell  ·  BASIC  ·  Lua  ·  c4  ·  nano                    │
│                       │                                         │
│      Linux 6.6, nommu, RV32IMA                                  │
│                       │                                         │
│      drivers:  gpio-tinyrv32  ·  block  ·  console              │
└───────────────────────┬─────────────────────────────────────────┘
                        │   CSR instructions   (GPIO = 0x1a0-0x1a3)
┌───────────────────────┴─────────────────────────────────────────┐
│  RP2040  @ 400 MHz                              (real silicon)  │
│                                                                 │
│      core 1  ──▶  tiny-rv32ima, the RV32IMA interpreter         │
│      core 0  ──▶  CSR handlers, VGA, PS/2, OLED                 │
└───────────────────────┬─────────────────────────────────────────┘
                        │
     ┌──────────────────┼──────────────────┬──────────────────┐
     ▼                  ▼                  ▼                  ▼
 2x SPI PSRAM      microSD card        GPIO pins        console I/O
 16 MB = RAM     kernel + rootfs     LEDs, buttons    PS/2, VGA, OLED
```

Linux sees ordinary devices — a block device, a `gpiochip`, a console. The RP2040 does the
translating underneath. Full GPIO walkthrough, including wiring an LED and the exact ioctls, is in
**[docs/GPIO_AND_BASIC_TUTORIAL.md](docs/GPIO_AND_BASIC_TUTORIAL.md)**. The
**[website](https://flyboy-byte.github.io/riscv-pico/)** draws the whole machine, including where
the 16 MB of memory actually lives.

---

## Build one yourself

### Parts — about $20 for the core

Everything here is what's on the verified build. No minimum order quantities, all single-quantity
friendly. Prices drift; this isn't a live feed.

| Part | Qty | Notes |
| --- | --- | --- |
| Raspberry Pi Pico | 1 | Verified on a Pico H (RP2040). Builds for `pico_w`/`pico2`/`pico2_w` too, but RP2350 is untested. |
| **APS6404L-3SQR-SN** PSRAM, SOP-8 | 2 | 8 MB each → 16 MB. [ProtoSupplies](https://protosupplies.com/product/psram/), ~$2.39 ea. |
| [SMD→DIP 8-pin adapter](https://protosupplies.com/product/pcb-smd-soic-8-msop-8-tssop-8-to-dip-adapter5-pack/) | 1 pack | ~$0.79 for 5. Headers not included. The PSRAM is surface-mount; these get it onto 0.1" pitch. |
| microSD breakout, SPI | 1 | Any 3.3 V module labelled `3V3 CS MOSI CLK MISO GND`. |
| microSD card | 1 | **4–32 GB, FAT32.** Not SDXC/exFAT — Petit FatFs only speaks FAT12/16/32. |
| 10 kΩ resistor | 1 | Pull-up for `SIO2`/`SIO3` on both chips. One resistor covers all four pins. |
| SSD1306 OLED, 128×64 | 0–1 | Optional. Must be the **I²C** 4-pin variant, not SPI. |
| Decoupling caps | a few | 100 nF ceramic + 10–100 µF bulk. Cheap insurance — see the power warning below. |
| Breadboard + jumpers | — | |

To run it without a PC, add:

| Part | Qty | Notes |
| --- | --- | --- |
| **[Serial Wombat PCB_0024 VGA breakout](https://www.amazon.com/Breakout-Resistors-Serial-Wombat-Arduino/dp/B0D4F7H59M)** | 1 | Resistors already fitted. Plug in an ordinary VGA cable; six jumpers to the Pico. |
| VGA monitor + cable | 1 | Anything that takes 640×480 at 60 Hz. |
| PS/2 keyboard | 1 | A real PS/2 keyboard, not a USB keyboard on a passive purple adapter. |
| Logic level converter, BSS138 4-channel | 1 | PS/2 is a 5 V bus. Only the keyboard needs it. |
| USB-C breadboard power supply | 1 | 5 V rail powers the Pico and keyboard; 3.3 V rail powers the SD card and OLED. |

> [!CAUTION]
> **Get the `-SN` (SOP-8) suffix, not `-ZR`.** Same silicon, but `-ZR` is USON-8 — a 3×2 mm
> leadless package that is genuinely painful to hand-solder or rework. Plain `APS6404L-3SQR` with
> no suffix is bare die, not a packaged part at all.

**Substitutes work fine.** ESP-PSRAM64H, LY68L6400, and IPUS equivalents share the SOP-8 pinout and
the `0x5D` known-good-die ID the firmware checks for. For stock across distributors, try
[Findchips](https://www.findchips.com/search/APS6404L-3SQR-SN) or
[Octopart](https://octopart.com/search?q=APS6404L-3SQR-SN).

### Wiring

The core build is 3.3 V native and its console is USB serial, so no adapter is needed. The
**[website](https://flyboy-byte.github.io/riscv-pico/)** has the full 40-pin map, a power and
ground diagram, and a [VGA wiring bench card](https://flyboy-byte.github.io/riscv-pico/vga.html).

> [!WARNING]
> **On the SD card module, `MOSI` and `CLK` cross over.** The module's header order does not match
> the Pico's pin order. This is the single easiest mistake to make on the whole board, and it costs
> you an afternoon.

> [!WARNING]
> **The PS/2 keyboard runs at 5 V, and RP2040 pins are not 5 V tolerant.** Route `CLK` and `DATA`
> through the level converter. Before the Pico is connected, meter the converter's low-voltage
> outputs: they must idle at 3.3 V, never 5 V. A resistor divider does not work on this bus.

<details>
<summary><b>PSRAM — two chips on a shared SPI bus</b></summary>

<br>

They differ only in chip-select:

| Chip pin | Signal | Chip 1 | Chip 2 |
| --- | --- | --- | --- |
| 1 | `/CE` | GP13 (pin 17) | GP14 (pin 19) |
| 2 | `SO` | GP12 (pin 16) | GP12 — shared |
| 5 | `SI` | GP11 (pin 15) | GP11 — shared |
| 6 | `SCLK` | GP10 (pin 14) | GP10 — shared |
| 3, 7 | `SIO2`, `SIO3` | → 3V3 via one shared 10 kΩ | same |
| 4, 8 | `VSS`, `VDD` | GND, 3V3 | GND, 3V3 |

`SIO2`/`SIO3` go unused in SPI mode. Pull them **high**, not low — some pin-compatible parts put an
active-low `/RESET` or `/HOLD` on `SIO3`. One 10 kΩ covers all four pins; nothing ever drives them.

**Default build is two-chip / 16 MB** (`PSRAM_TWO_CHIPS 1` in `hw_config.h`, `EMULATOR_RAM_MB 16` in
`vm_config.h`). Going single-chip? Set them to `0` and `8`. Mismatching them is a compile-time
`#error`, not a silent address-wrap bug that bites you three hours later.
`PSRAM_SPI_SPEED_MHZ` defaults to 20, which stays stable even on messy breadboard leads.

</details>

<details>
<summary><b>microSD card module</b></summary>

<br>

| Module | Pico |
| --- | --- |
| `CS` | GP0 (pin 1) |
| `MOSI` | GP3 (pin 5) |
| `CLK` | GP2 (pin 4) |
| `MISO` | GP4 (pin 6) |

⚠️ **`MOSI` and `CLK` cross over** — see the warning above. The module's header order does not
match the Pico's pin order.

The card itself is plain FAT32 with `IMAGE`, `DTB`, and `ROOTFS` in the root. No special
formatting.

</details>

<details>
<summary><b>PS/2 keyboard, through the level converter</b></summary>

<br>

| Keyboard (mini-DIN-6) | Converter | Pico |
| --- | --- | --- |
| Pin 1, `DATA` | HV1 → LV1 | GP26 (pin 31) |
| Pin 5, `CLK` | HV2 → LV2 | GP27 (pin 32) |
| Pin 4, +5 V | HV | 5 V rail of the breadboard supply |
| Pin 3, GND | GND | Common ground |
| — | LV | 3V3 OUT (pin 36) |

Wire colours are not standardised, so identify pins with a meter rather than by colour. Getting
`DATA` and `CLK` swapped is harmless; if no keys arrive, swap them. The driver only receives, so
Caps Lock and Num Lock lights never come on. No firmware change is needed — the keyboard driver is
already in the firmware.

</details>

<details>
<summary><b>VGA, through the Serial Wombat PCB_0024 breakout</b></summary>

<br>

Use the breakout's **outer** header column, which is its 3.3 V input. The inner column is sized for
5 V and gives a dim picture.

| Breakout | Pico |
| --- | --- |
| `V` | GP16 (pin 21) |
| `H` | GP17 (pin 22) |
| `GND` header | GND (pin 23) |
| `R` | GP18 (pin 24) |
| `G` | GP19 (pin 25) |
| `B` | GP20 (pin 26) |

Reading the column bottom to top lands on the Pico's pins in order, so the jumpers run straight.
Leave the five round pads along the top and the solder jumpers on the back unconnected. Green and
blue aren't configurable in firmware: they always follow red on the next two pins. The picture is
320×240 in eight colours, and the terminal is 53×30 characters.

</details>

<details>
<summary><b>SSD1306 OLED status panel (optional)</b></summary>

<br>

Four separate jumpers — there's no free adjacent GPIO pair left on the board:

| Module | Pico |
| --- | --- |
| `VCC` | 3.3 V from a **separate supply**, not pin 36 — see the power warning below |
| `GND` | GND (pin 28), tied to that supply's ground at one point |
| `SDA` | GP28 (pin 34) |
| `SCL` | GP21 (pin 27) |

Shows RAM/PSRAM config, boot stage, live MIPS, uptime, and clock — a stats panel, not a second
console. It runs on core 0, which the emulator never touches, and probes at boot: with nothing
attached, the firmware behaves exactly as if the code weren't there. Disable entirely with
`CONSOLE_OLED 0` in `hw_config.h`. If a panel is wired but stays blank, try `OLED_I2C_ADDR 0x3D`.
It runs alongside VGA without conflict.

</details>

<details>
<summary><b>Running without a PC</b></summary>

<br>

Feed the breadboard supply's **5 V** rail into **VSYS (pin 39)**. Never feed 3.3 V into pin 36: that
is the output of the Pico's own regulator, not an input. With USB unplugged there's no serial
console, so the VGA screen shows the boot. Before pulling power, run `sync` or `halt`, or the ext2
root filesystem can be damaged.

</details>

> [!WARNING]
> **Breadboard power is the thing that will actually bite you.** Wiring up the OLED destabilised
> the PSRAM bus and crashed boot — despite the two sharing no GPIO pins at all. The cause was a
> single 3V3 supply pin feeding PSRAM VCC, both chips' pull-ups, the SD card *and* the OLED, so any
> load spike on that node bled into everything else on it.
>
> The fix was a single-point (star) power layout: separate supply for OLED/SD, PSRAM on its own
> clean VCC/GND, short jumpers, and decoupling caps at each chip's supply pins. **If you see random
> resets or PSRAM failures that only appear once a second peripheral is wired up, check power
> distribution before you suspect the chip.** Full writeup — including the wrong theories tried
> first — in [PLAN.md](PLAN.md) and [docs/HARDWARE_SCHEMATIC.md](docs/HARDWARE_SCHEMATIC.md).

### Firmware

**Just want to flash something?** Grab
**[`pico-rv32ima-boards-v6`](https://github.com/flyboy-byte/riscv-pico/releases/tag/pico-rv32ima-boards-v6)**
— prebuilt `.uf2` for all four board variants, ready to go. It includes the VGA, PS/2 and OLED
consoles, and a VGA terminal that full-screen programs like nano can draw on.

<details>
<summary><b>Or build it from source</b></summary>

<br>

```sh
# once — Pico SDK, shallow clone with just the tinyusb submodule (~65 MB)
git clone -b 2.1.1 --depth 1 https://github.com/raspberrypi/pico-sdk.git ~/pico-sdk
git -C ~/pico-sdk submodule update --init --depth 1 lib/tinyusb

firmware/build.sh              # all four boards → firmware/out/*.uf2
firmware/build.sh pico2_w      # or just one
```

About 150 KB per board. Flash by holding **BOOTSEL** while plugging in the Pico — it mounts as a
USB drive called `RPI-RP2` — then copy the `.uf2` across.

</details>

Then copy `IMAGE`, `DTB` and `ROOTFS` from
**[`sdcard-v2`](https://github.com/flyboy-byte/riscv-pico/releases/tag/sdcard-v2)** to the root of
the card.

---

## Programming on the Pico

You can write and run programs on the machine itself: open a file in nano, save it, run it. No PC.

| Language | Try | Notes |
| --- | --- | --- |
| **Lua 5.4** | `lua blink.lua` | Adds `sys.sleep(seconds)`, `sys.ms()` and `sys.raw()`, which stock Lua lacks. GPIO goes through `/sys/class/gpio`. |
| **C, via c4** | `c4 gpio_set.c 1` | Compiles C to bytecode and interprets it. This copy adds `for` and `write`, and it can compile itself. |
| **Tiny BASIC** | `basic` | Line-numbered BASIC. `BYE` returns to the shell. |
| **Shell** | `sh script.sh` | busybox `hush`, not bash. |

Every command for all of this is on one page in
**[docs/CHEATSHEET.md](docs/CHEATSHEET.md)**, and the same thing is on the card at `/root/help.txt`,
so `nano -v /root/help.txt` pages through it when there's no PC attached.

The examples are in `/root` on the SD image. Blinking an LED in Lua looks like this:

```lua
local function put(path, text)
  local f = io.open(path, "w"); f:write(text); f:close()
end

put("/sys/class/gpio/export", "512")                 -- GPIO line 0 = Pico GP1, pin 2
put("/sys/class/gpio/gpio512/direction", "out")
for i = 1, 10 do
  put("/sys/class/gpio/gpio512/value", "1"); sys.sleep(0.2)
  put("/sys/class/gpio/gpio512/value", "0"); sys.sleep(0.2)
end
put("/sys/class/gpio/unexport", "512")               -- release it, or gpioset says busy
```

There's a game, too: **`lua /root/mines.lua`** is minesweeper on the VGA screen. Arrow keys move,
space digs, `f` flags, `r` restarts, `q` quits. Board size is optional —
`lua /root/mines.lua 20 14 40`. Single keypresses need `sys.raw()`, another call the Lua build adds;
where that isn't available it falls back to typed commands, so it works over a pipe too.

`os.execute` and `io.popen` don't work from Lua here: they need `fork()`, which a no-MMU machine
doesn't have. Details on c4's language and limits are in
**[apps/c4/README.md](apps/c4/README.md)**.

<details>
<summary><b>Cross-compiling bigger programs on a PC</b></summary>

<br>

There's a real cross-compiler for this target — `riscv32-buildroot-linux-uclibc-gcc`, producing the
`bFLT` no-MMU binary format the kernel needs. `apps/` holds the hand-written pieces: Tiny BASIC
(`basic.c`), the Lua `sys` extension (`lua_sys.c`), c4, a GPIO chardev smoke test (`gpiotest.c`),
and `sysinfo.sh`. Lua 5.4.7 and GNU nano 7.2 build straight from unmodified upstream sources and
aren't vendored here.

The toolchain isn't checked in; grab
[`toolchain-v2`](https://github.com/flyboy-byte/riscv-pico/releases/tag/toolchain-v2). The rebuild
recipe and the gotchas already solved live in PLAN.md's "Cross-compile toolchain", "Real GNU nano"
and "apps/" sections.

</details>

---

## Downloads

Build outputs ship as GitHub releases rather than committed binaries, which keeps `git clone` fast.

| Release | Contents |
| --- | --- |
| **[`sdcard-v2`](https://github.com/flyboy-byte/riscv-pico/releases/tag/sdcard-v2)** | **Current SD card image.** No-network kernel; rootfs with Lua, c4, BASIC and examples, with the console sized for the VGA screen. v1 of it booted on hardware; v2 is harness-verified. |
| **[`pico-rv32ima-boards-v6`](https://github.com/flyboy-byte/riscv-pico/releases/tag/pico-rv32ima-boards-v6)** | **Current firmware**, all four boards — 16 MB two-chip, VGA with a rewritten VT102 terminal, PS/2 with working Home/End/Delete/Page keys, OLED panel, GPIO CSRs. |
| [`toolchain-v2`](https://github.com/flyboy-byte/riscv-pico/releases/tag/toolchain-v2) | The cross-compiler, wchar-enabled (needed for nano/ncurses). |
| [`rv32harness-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/rv32harness-v1) | Desktop harness binaries, x86-64 Linux. |
| [`kernel-gpio-v2`](https://github.com/flyboy-byte/riscv-pico/releases/tag/kernel-gpio-v2) | Previous kernel + rootfs, with networking. Hardware-verified. |
| [`net-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/net-v1) | The networking reference: TCP/IP stack and the second console channel's SLIP work. |
| [`apps-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/apps-v1), [`apps-v2`](https://github.com/flyboy-byte/riscv-pico/releases/tag/apps-v2) | Older loose binaries. Everything current is in `sdcard-v2`. |

Firmware `-v5` boots `sdcard-v2` fine, but nano on its VGA screen is unusable. `-v3`/`-v4` still boot too. `-v1`/`-v2` are superseded single-chip 8 MB builds that
don't boot the current rootfs.

---

## Repo layout

| Path | What | Notes |
| --- | --- | --- |
| `harness/` | *this repo* | Desktop build of the real emulator core, plus a PyQt6 terminal app to drive it. |
| `firmware/` | *this repo* | `build.sh` — one command, `.uf2`s for all four board targets. |
| `apps/` | *this repo* | Programs for the target: Tiny BASIC, the Lua `sys` extension, examples. |
| `apps/c4/` | [rswier](https://github.com/rswier/c4) via [tvlad1234](https://github.com/tvlad1234/c4) | The on-device C compiler, with `for` and `write` added here. GPL-2.0. |
| `buildroot-overlay/` | *this repo* | Kernel config and the patches that create every custom device — block, GPIO, second console. |
| `site/` | *this repo* | The [website](https://flyboy-byte.github.io/riscv-pico/). Plain HTML, published to `gh-pages`. |
| `docs/` | *this repo* | GPIO and BASIC tutorial, hardware schematic handoff notes, images. |
| `experiments/` | *this repo* | Side quests, like a Raspberry Pi 4 pretending to be an SD card. |
| `upstream/pico-rv32ima/` | [tvlad1234](https://github.com/tvlad1234/pico-rv32ima) | The fork this builds on. No longer pristine — the PSRAM port lives here. |
| `upstream/pico-rv32ima/tiny-rv32ima/` | [tvlad1234](https://github.com/tvlad1234/tiny-rv32ima) | The emulator core. Also edited by the same port. |
| `upstream/pico-linux/` | [ElectroBoy404NotFound](https://github.com/ElectroBoy404NotFound/pico-linux) | Reference only, still pristine. Source of the PSRAM port logic. |

All three `upstream/` paths are `git subtree`s with full history, so `git log -- upstream/<x>` works
and upstream changes can still be pulled — commands in [CLAUDE.md](CLAUDE.md).

**[PLAN.md](PLAN.md) is the living state doc** — every decision, every bug, every dead end, and
what's next. It's far more detailed than this file.

---

## License

This repo's own code (`harness/`, `apps/`, `firmware/`, `buildroot-overlay/`, `site/`, docs) is MIT —
see [LICENSE](LICENSE) — **except `apps/c4/`, which is GPL-2.0** like the c4 it comes from. Everything
under `upstream/` keeps its original licensing (MIT / Apache-2.0 / BSD-3); see the `LICENSE` in each
subtree.
