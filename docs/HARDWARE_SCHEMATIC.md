# Hardware schematic — handoff doc for circuit/layout review

**Purpose of this file:** this project (`riscv-pico`, a RISC-V Linux emulator running on a Pico
RP2040) currently runs on a solderless breadboard, and has hit a real signal-integrity problem
that a breadboard can't solve. The plan is to move to a soldered perfboard/stripboard. This doc
exists to hand the current wiring to a separate AI session (or human) with layout/signal-integrity
expertise, so they can propose a soldered layout — not just "which pin goes where" (that's already
fixed by firmware, see below) but grounding strategy, decoupling placement, wire/trace length
budgets, and separation between the SPI bus and the newer, faster VGA lines.

**What is fixed vs. what is open:**
- **GPIO pin assignments are fixed** — they're compiled into firmware (`hw_config.h`), changing
  them means a rebuild, so treat the pinout below as given, not as a variable to optimize.
- **Physical layout, grounding topology, decoupling, wire routing, and power distribution are all
  open** — that's what this handoff is asking for reasoning about.
- **Board size is not yet known.** The available perfboard/stripboard has not been measured against
  this component count. If layout requires more board than is on hand, say so explicitly rather
  than compressing the layout past a safe margin — a second cheap board is not a real constraint.

## The target board

Raspberry Pi Pico (RP2040), running heavily overclocked and overvolted: 400 MHz core clock,
`VREG_VOLTAGE_MAX` (~1.30 V core). This is intentional and load-bearing for emulator throughput —
not something to design around or flag as a problem, but worth knowing it means the Pico itself is
running hotter/noisier than stock.

## Components in the current circuit

| Component | Role | Notes |
|---|---|---|
| Raspberry Pi Pico (RP2040) | Host MCU | Core 0 = I/O, core 1 = RV32IMA emulator |
| 2× PSRAM chip (LY68L6400 or ESP-PSRAM64H, 8 MB each) | Emulated guest RAM (16 MB total) | Hand-soldered onto DIP adapters, connected to the breadboard by flying leads. This is the **most timing-sensitive bus in the system** — see incident below. |
| SD card breakout | Guest root filesystem storage | SPI, low activity, not implicated in any issue so far |
| SSD1306 128×64 OLED | Status panel (currently software-disabled) | I2C, address 0x3C, 12.2 mA measured draw. **Wiring this in destabilizes the PSRAM bus — see incident below.** |
| VGA output (not yet wired) | Primary console, PIO-generated | Needs a resistor-ladder DAC: 3× 330 Ω on R/G/B lines per the project README. Continuous, high-frequency (real VGA pixel clock, tens of MHz), not yet built. |
| PS/2 keyboard port (not yet wired) | Console input | Low frequency (~10–16 kHz clock), driven by the keyboard, not the Pico |

Everything is currently powered from the Pico's own 3V3 regulator via USB — no external supply.

**Power distribution is single-point and this matters a lot for the incident below.** Physical
pin 36 (3V3 OUT) is the sole 3V3 source on the breadboard, and it directly feeds: the SD card's
VCC, both PSRAM chips' VCC, and the WP/HOLD pull-ups on **both** PSRAM chips (pins 3 and 7 on the
LY68L6400/ESP-PSRAM64H SOIC-8 footprint — these need pulling to VCC in single-SPI mode or the chip
can misbehave with them floating). Every device sharing that node — including the OLED when it's
wired in, and eventually VGA/PS2 if their logic taps 3V3 — loads the same net that PSRAM's supply
voltage and pull-up reference both depend on.

## Full GPIO pinout (as compiled — do not renumber without a firmware rebuild)

Source of truth: `upstream/pico-rv32ima/pico-rv32ima/hw_config.h`.

| Function | GPIO(s) | Notes |
|---|---|---|
| UART (disabled, `CONSOLE_UART 0`) | 0, 1 | Not in use |
| SD card SPI (`spi0`) | CK=2, TX=3, RX=4, CS=0 | |
| Bit-banged SPI, exposed to the **guest OS** via custom CSRs 0x180–0x183 | CS=5, SCK=6, MOSI=7, MISO=8 | Not a spare bus — the RISC-V guest can drive this directly. Looked "free" in an earlier pin audit and wasn't; don't reuse it. |
| PSRAM SPI (`spi1`, hardware SPI) | CK=10, TX=11, RX=12, S1(chip 1 CS)=13, S2(chip 2 CS)=14 | Currently clocked at 20 MHz (dropped from a 50 MHz nominal for breadboard bring-up). **This is the bus that breaks.** |
| VGA | VSYNC=16, HSYNC=17, R=18 (G/B implied at 19/20 by the emulator's PIO program, consecutive from `VGA_R_PIN`) | Not yet wired |
| PS/2 keyboard | DATA=26, CLK=27 | Not yet wired |
| I2C0 (OLED, currently disabled in firmware) | SDA=28, SCL=21 | Only free I2C-capable pair once everything else claimed its pins — RP2040 muxes i2c0 onto GPIOs where `n/2` is even, i2c1 where odd, SDA always even/SCL the odd pin above. No free *adjacent* pair existed; this needs two separate jumpers from the module. |

Power/ground reference points already in use: GND near pin 28, 3V3(OUT) near pin 36 (physical pin
numbers, for the OLED tap).

## The incident this handoff exists because of

With the OLED wired in (I2C0 on GP28/GP21 — physically far from the PSRAM pins, GP10–14), the
guest kernel panics shortly after boot, at both 20 MHz and 28.6 MHz PSRAM clock. The panic was
decoded to a single bit flip in kernel text re-read from PSRAM (faulting instruction word
`0x000a1027`, an `fsd` on a CPU with no FP extension — one opcode bit away from a valid `sh`
instruction with a plausible kernel pointer in the source register). Firmware was ruled out three
ways: a build predating every OLED-related change panics identically; a from-scratch rebuild at the
same PSRAM speed byte-matches the working binary; the same emulator core boots cleanly in a desktop
harness with no PSRAM bus at all. Unplugging the OLED and reflashing a build with the OLED driver
compiled out restores a stable boot.

Because GP28/21 is nowhere near GP10–14, the coupling is suspected to be through the shared
breadboard power/ground rail rather than direct lead-to-lead crosstalk — i.e. **any** new
switching activity added to this breadboard is a candidate to reproduce the failure, not just I2C
specifically. That's the open risk for VGA, which is a much more sustained, higher-frequency
switcher than the OLED's twice-a-second I2C flush ever was.

**Sharper version of the hypothesis, given the single-point 3V3 supply above:** this may not be
pure ground bounce. Pin 36 feeds PSRAM VCC directly, so any load transient on that node (I2C
switching, SD SPI activity, the OLED's own current draw) can sag or ripple the actual operating
voltage of the chip that's corrupting reads — and the same node also references the WP/HOLD
pull-ups on both PSRAM chips, so a sag there risks those pins reading as an unintended
hold/write-protect assertion mid-transaction, not just a marginal SPI signal. That's a more direct
fault mechanism than ground-return inductance and fits the symptom (isolated bit corruption on a
PSRAM re-read) at least as well. Whoever picks this up should treat "PSRAM VCC/pull-up supply
integrity" as at least as strong a lead as "ground rail," not a secondary concern.

One isolation test remains unrun as of this writing: reflash the OLED-disabled build with the OLED
still physically wired (present but idle) to separate "the wires being there" from "I2C traffic
being active." Whoever picks up the layout question should treat both as live hypotheses until
that's actually run.

## What to reason about

1. **Grounding topology.** Breadboards are known to behave as a bus of long, closely-spaced,
   moderately inductive metal strips rather than a low-impedance plane — a shared rail is a
   plausible fault path here even between physically distant pins. On a soldered board, what
   grounding scheme (star vs. bus, dedicated return per bus, ground fill/pour if the board
   supports it) actually removes that fault path, versus just relocating it?
2. **Decoupling.** Where do 0.1 µF ceramics need to sit relative to each PSRAM chip's VCC/GND and
   the Pico's own supply pins? Is that sufficient given the PSRAM chips are already the least
   trusted parts in this circuit (hand-soldered onto DIP adapters of unknown provenance)?
3. **Separation.** Physical/routing separation between the PSRAM SPI bus (10–14, the sensitive
   one) and the VGA lines (16–20, not yet built, high switching activity) — how much distance or
   isolation is actually needed, and does routing them on perpendicular rows/strips instead of
   parallel ones matter as much on perfboard as it would on a PCB?
4. **Wire/trace length budgets.** At 20–30 MHz SPI, what's a sane maximum lead length for the
   PSRAM chip-to-Pico connections before signal integrity (not just noise pickup) becomes the
   limiting factor, and does that change the DIP-adapter-plus-flying-leads approach or just
   tighten it?
5. **Power.** Everything currently runs off the Pico's onboard 3V3 reg via USB. Does adding VGA's
   resistor DAC + OLED + PS/2 change that recommendation, or is a single Pico-sourced rail still
   fine at this component count?
6. **Board size.** Given the component list above (Pico header footprint, 2× DIP-adapter PSRAM
   chips, SD breakout, OLED breakout, VGA DAC resistors + header, PS/2 header), what's a realistic
   minimum board size, and does a single perfboard/stripboard of common hobbyist size (e.g.
   ~7×9 cm / 7×5 cm protoboard) actually fit it with the separation called for in (3), or does this
   want two boards / a specific board shape?

## Sources consulted for the mitigation reasoning that produced this doc

- [Solderless Breadboard Parasitics — Hackaday](https://hackaday.com/2016/01/19/solderless-breadboard-parasitics/)
- [Ground Bounce in PCB Design — AllPCB](https://www.allpcb.com/allelectrohub/ground-bounce-in-pcb-design-causes-effects-and-mitigation-strategies)
- [How to Reduce Ground Bounce — All About Circuits](https://www.allaboutcircuits.com/technical-articles/how-to-reduce-ground-bounce-mitigating-noise-pcb-design-best-practices/)
- [Hardware Design with RP2040 — Raspberry Pi official docs](https://manuals.plus/m/4639a3852ae690a5a431b6cc95d7c2a57abac6e1a059b110b2d007ae2b9b76b8)
- [PIO Assembly VGA Driver for RP2040 — Van Hunter Adams](https://vanhunteradams.com/Pico/VGA/VGA.html)
