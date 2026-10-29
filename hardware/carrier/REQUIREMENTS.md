# Requirements — Pico carrier board

Partly answered by Logan on 2026-10-28; the rest is open and marked so. Answers taken from the
existing project docs are attributed, not invented.

| Requirement | Answer | Notes |
| --- | --- | --- |
| What the board does | Carries the finished `riscv-pico` circuit on something soldered: a Pico, 2 × SPI PSRAM, SD breakout, SSD1306 OLED, VGA breakout, PS/2 via a BSS138 converter | Packaging job. The circuit is verified working on a breadboard |
| Is a breakout board or perfboard enough? | **Perfboard is the preferred route**, 2026-10-28 | So the PCB route stays optional. See STATE.md's two-route table |
| Size target, and which edge is the hard limit | Protoboard: whatever stock fits. PCB: **≤100 × 100 mm (3.94 × 3.94 in)**, hard | Past 100 mm JLCPCB adds an engineering fee |
| Wire edge | **Open.** Proposal: all off-board wires leave one long edge — external 5 V/3.3 V supply, VGA cable, PS/2 cable | Owner to confirm |
| Antenna / radio / SIM end | n/a | No radio on this board |
| Mounting | **Open.** Recommendation: a hole in each corner now, since a 3D-printed enclosure is already on the owner's list | Free to add, expensive to retrofit |
| Temperature range | Indoor desk use. No −40 °C requirement | Not outdoor gear |
| User-handled parts | Pico (socketed?), all six module headers, external supply terminal, VGA cable, PS/2 cable, microSD insert/eject | Each needs the 3D access check at stage 7 |
| Power source and rails | External bench supply. 5 V rail → VSYS (pin 39) **and** the keyboard; 3.3 V rail → SD and OLED; Pico's own 3V3 (pin 36) → PSRAM VCC and the WP/HOLD pull-ups only. Single-point ground tie | From PLAN.md. **This split is load-bearing** — see the 2026-08-29 incident |
| Programming method | Pico's own USB, unchanged | BOOTSEL + drag a `.uf2`. Needs physical access to the Pico |
| Assembly | Protoboard: all by hand, iron only. PCB: bare board, hand-soldered headers; no SMD to place | Owner has no hot air, so nothing finer than 0805 by hand |
| Quantity, first batch | Protoboard: 1. PCB: 5 (the minimum) | |
| Ships to others? | No units shipped, but the **design is published** — the repo's pitch is "build one yourself" | Gerbers would be shareable; a hand-wired protoboard is not reproducible |

## Risk probes asked

- **High-speed SPI bus next to a faster switching bus** → the PSRAM group (GP10–GP14, `spi1` at
  20 MHz) and the VGA group (GP16–GP20, a real PIO pixel clock) must not share a return path or run
  parallel for any distance. The PSRAM group gets its own ground return at pin 18; VGA uses pin 23.
- **A supply node feeding both a chip's VCC and its own pull-up reference** → this is the known
  fault. Pin 36 currently feeds PSRAM VCC *and* the WP/HOLD pull-ups on both chips, so a sag there
  can both brown out the chip and make WP/HOLD read as asserted mid-transaction. Decoupling goes
  within a few mm of each chip's VCC/GND pair, and nothing else loads pin 36.
- **Hand-soldered parts of unknown provenance** → the PSRAM chips are SOP-8 hand-soldered onto DIP
  adapters, then run on flying leads. They are the least trusted parts in the circuit. Socketing the
  adapters removes the flying leads; moving to on-board SOP-8 (JLC-placed) removes the adapters too,
  and is the identified fallback if the first board still misbehaves.
- **Heavy cable on a soldered joint** → the VGA cable has real mass. PLAN.md already records that it
  will lever pads off a board, so strain relief is a requirement and not a nicety.
- **Overclocked, overvolted host** → the Pico runs at 400 MHz on `VREG_VOLTAGE_MAX`. Deliberate and
  load-bearing for emulator throughput. It means the Pico runs hotter and noisier than stock; do not
  "fix" it, but do not put heat-sensitive parts against it either.

## What working means (bring-up tests, decided before layout)

All checkable with a multimeter and the serial console. The owner has no scope, no logic analyzer
and no bench supply, so nothing here needs them. Changing a test later needs a dated reason in
`STATE.md`.

| # | Do | Measure / observe | Pass |
| --- | --- | --- | --- |
| T1 | Unpowered, meter across each rail to GND | resistance | > 1 kΩ on every rail (no short) |
| T2 | Unpowered, continuity from every Pico pin in `pinmap.csv` to its module header pin | continuity | Every row in `pinmap.csv` beeps; nothing else does |
| T3 | Power up with no Pico fitted | voltage at the 5 V terminal and the 3.3 V rail | 4.8–5.2 V and 3.2–3.4 V |
| T4 | Fit the Pico, power up | voltage at Pico pin 36 | 3.2–3.4 V |
| T5 | Boot with the serial console attached | the boot log | `PSRAM OK` then `SD init OK` |
| T6 | Boot to a shell, run `sysinfo` | guest RAM reported | 16 MB, both chips seen |
| T7 | OLED and VGA both attached, 10 consecutive cold boots | kernel panics | 0 of 10. This is the fault the board exists to fix, and it was intermittent |
| T8 | **The real proof.** Raise `PSRAM_SPI_SPEED_MHZ` from 20 and rebuild, stepping up | highest stable speed | **> 20 MHz.** The breadboard needed 20, dropped from a 50 nominal. If the soldered board holds 50, the layout fixed the problem; if it still caps at 20, it did not |

T8 is the headline: it turns "does the board help?" into a number, needs no instruments, and the
breadboard's figure is already on record for comparison.
