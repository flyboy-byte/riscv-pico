# HANDOFF — carrier board, 2026-10-28

Replaced each session, not appended. `STATE.md` is the durable record; this is the short path back in.

## Read first
1. `STATE.md` — stage, the two routes, decisions not to re-ask.
2. `MEASURE.md` — the next action, and the only thing blocking the board.
3. This file for what happened in the last session.

## Where it stands
Protoboard layout generated, checked, committed, pushed. Working tree clean at `1647a64`.
`python3 checks/run_all.py` → 5 checks, 0 failed, 1 advisory failed (DRC, see below), 0 skipped.

**Blocked on one thing only: six modules are still `GUESSED` in `modules.csv`.** That is physical
measurement, which no session can do. Everything that could be done without it has been done.

## Verify, don't assume
```sh
cd hardware/carrier
python3 gen_proto.py --report      # regenerates the board + wire list
python3 checks/run_all.py          # all four checks
git status                         # should be clean
```
`gen_proto.py` is deterministic: re-running it on an unchanged `modules.csv`/`pinmap.csv` must
reproduce 18 footprints, 28 nets, 61 wire links. If it doesn't, something upstream changed.

## Two things that look like bugs and are not
- **DRC reports 61 unconnected items.** That is the 61 wire links. A protoboard has no traces; the
  connections are wires you solder. DRC is marked `advisory` in `checks.json` for exactly this.
  The number matching the wire list IS the check — if they ever diverge, that is the real signal.
- **`body_check.py` passes with only 5 bodies.** Four modules are `body_on_board = no`, so they have
  no body to fit. That is a deliberate decision, not missing data.

## What was done, in order
1. Scaffolded the project from the `pcb-design` skill templates inside `riscv-pico` (owner: "def not
   new project, it's part of this").
2. `pinmap.csv` built from `hw_config.h`, 18 signals, with the critical PSRAM group marked and the
   reserved guest-SPI pins (GP5–GP8) called out so nobody reuses them again.
3. `gen_proto.py` → `carrier_proto.kicad_pcb`. Six drafts; the history table is in `STATE.md`.
4. Three project checks written and each negative-tested by breaking the design on purpose.
5. Everything measurable moved into `modules.csv`; `MEASURE.md` written as the hand-off.

## Attempts that changed the design
| # | Tried | Result |
| --- | --- | --- |
| A1 | Stock KiCad THT capacitor footprints | **Failed.** All 5.00 mm pitch → pads between protoboard holes. KiCad has no on-grid THT cap footprint at all. Wrote `carrier.pretty/`. |
| A2 | Pull-ups one hole apart | **Failed.** Resistor bodies physically overlapped. Moved to 2 holes. |
| A3 | 96.5 × 88.9 mm board | **Oversized.** Bottom third empty. Shrank to 90 × 70 mm. |
| A4 | Mounting-hole footprints in the corners | **Dropped.** A protoboard already has holes everywhere; which become mounting points is an enclosure decision. Also collided with `J_SD`. |
| A5 | All modules on-board, bodies drawn | **Failed.** 7 body collisions; SD overlapped the Pico by 18 × 23 mm; PS/2 and VGA off the edge. Led to A6. |
| A6 | SD, VGA, PS/2, OLED as header-only, bodies off-board | **Passed.** 5 on-board bodies, no collisions. This is the current design and it is a default I picked, not an owner decision. |

## Last raw output
```
board 90 x 70 mm (3.54 x 2.76 in), 35 x 27 holes; uses cols 1-31, rows 2-23
18 footprints, 28 nets, 61 wire links to solder
off-board (header only, module mounts to the enclosure wall): J_OLED, J_PS2, J_SD, J_VGA
NOT READY TO BUILD: 6 of 9 modules still GUESSED in modules.csv (J_LVL_HV, J_LVL_LV, J_OLED, J_PS2, J_SD, J_VGA)

PASS  Pin map matches firmware hw_config.h: 18 signals match
PASS  Pads on the protoboard grid: all 108 pads on the 2.54 mm grid
PASS  Module bodies do not collide: 5 on-board bodies, none overlapping
FAIL  DRC (unconnected = the wire list): 61 unconnected_items   [advisory: True]
PASS  No hand edits waiting: no drift
```

## Do not re-raise
- Whether to order a one-sided PCB. Settled: no. One-sided means a **protoboard**; an ordered board
  would be 2-layer. The owner said so on 2026-10-28.
- Whether this lives in its own repo. Settled: it lives in `riscv-pico`.
- Whether to move the VGA series resistors onto the carrier. No — they stay on the breakout.
- Whether the 3V3 split is worth it. It is load-bearing; sharing one node crashed boot on 2026-08-29.

## Next steps, in order
1. Owner measures six modules → `modules.csv` → re-run. (`MEASURE.md`)
2. Refine decoupling placement: a DIP-8's VCC and GND are diagonally opposite, so C1/C2 cannot span
   both without a detour. Most important physical detail on the board.
3. Owner decides: socket or solder the Pico; mounting holes now or later; BSS138 LV reference.
4. Only then, if the owner commits: the 2-layer PCB variant from the same two CSVs.
