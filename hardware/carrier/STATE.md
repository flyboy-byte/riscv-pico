# STATE — Pico carrier board

Status: **Stage 1, requirements — in progress (2026-10-28)**
Revision in progress: none yet.   Revisions used (never reused): none.
Review pages: scope and PCB-vs-protoboard call <https://claude.ai/artifact/X4U9icB6S6mdqby3T4im1R>

## What this board is

The `riscv-pico` machine currently runs on a solderless breadboard and has a documented
signal-integrity fault because of it (single-bit PSRAM read corruption through the shared
power/ground rail — see `../../docs/HARDWARE_SCHEMATIC.md` and PLAN.md's 2026-08-29 incident).
This board moves the same circuit onto something soldered. The circuit is finished and verified;
this is a packaging job, not a design exploration.

**Two routes, and only two.** The owner set these on 2026-10-28:

| Route | Status | What it is |
| --- | --- | --- |
| **Protoboard** | **Preferred. Current work.** | A one-sided prototype board, hand-wired. KiCad is used as the *layout planning tool* for it — real footprints on a 0.1 in grid, a netlist that proves the wiring, and a printable build sheet. Nothing is ordered. |
| JLC 2-layer PCB | Held. "Full commitment." | An ordered board with a real ground plane. Scoped and costed on the review page above. Only if and when the owner commits. |

A one-sided *ordered* board is **not** a route. It gives up the ground plane, which is the whole
electrical reason to leave the breadboard, and costs the same as 2-layer at JLC.

## Stages
Mark a stage done only when its exit condition is true. Strike through, don't delete.

| # | Stage | Exit condition | Done |
| --- | --- | --- | --- |
| 1 | Requirements | `REQUIREMENTS.md` answered by the owner; breakout/perfboard ruled out | In progress — and see note |
| 2 | Parts | Every part in `parts_research.md` with pinout, land pattern, temp rating, stock, source URL; real 3D model seen for user-handled and tall parts | |
| 3 | Schematic | Generated from code; netlist self-check passes | |
| 4 | Fit check | Artifact page with the to-scale picture and size table (mm + in) approved by the owner | |
| 5 | Placement | Fixed parts and critical loops locked; back side checked | |
| 6 | Routing | Best run chosen by DRC count, not router score; vias out of SMD pads | |
| 7 | 3D and mechanical | Access check done for every user-handled part; renders looked at, then published and approved by the owner | |
| 8 | Fab files | `checks/run_all.py` all PASS (DRC included, nothing skipped) on the current design | |
| 9 | Audit | `AUDIT.md` round with no open BLOCKER or BUG; earlier fixes re-confirmed | |
| 10 | Order | `checks/release.py` released `fab/<rev>/`; committed the same day; row in `ORDERS.md` | |
| 11 | Bring-up | Bring-up tests from `REQUIREMENTS.md` run and recorded below; RISK items checked; lessons in `LESSONS.md` | |

**Note on stage 1's exit condition.** It says "breakout/perfboard ruled out". Perfboard is
deliberately **not** ruled out here — the owner prefers it. So stage 1 will not close for the PCB
route unless the owner later commits to ordering. Stages 2–7 still apply to the protoboard draft
(parts, schematic, fit, placement); stages 8–10 are PCB-only and stay empty.

## Decisions already made (do not re-ask)
- 2026-10-28 **Lives inside `riscv-pico`**, at `hardware/carrier/`, not as a separate project — owner's
  call ("def not new project, it's part of this").
- 2026-10-28 **"One-sided" means a protoboard build**, not ordering a 1-layer PCB.
- 2026-10-28 **Protoboard is the preferred route**; the JLC 2-layer order is the full-commitment
  alternative, not the default.
- 2026-10-28 **If a PCB is ever ordered, stay at or under 100 × 100 mm** (3.94 × 3.94 in). Past that
  JLCPCB's cheap tier stops applying and an engineering fee is added. This rules out the 160 × 100 mm
  Eurocard idea from the earlier notes.
- 2026-10-28 **The VGA series resistors stay on the Serial Wombat breakout** (3 × 270 Ω, 2 × 68 Ω).
  PLAN.md's "Breakout construction" section is explicit about not relocating them.
- 2026-08-29 **The 3.3 V supply split is load-bearing, not a preference.** PSRAM on the Pico's 3V3;
  SD and OLED on the external supply; all grounds meeting at one point. Sharing one 3V3 node is what
  crashed boot. Any layout preserves this.
- Pin assignments are **frozen in firmware** (`hw_config.h`). The layout routes around them. They
  live in `pinmap.csv` and nowhere else.

## Checks
<!-- checks:start -->
Not run yet. `checks/run_all.py` writes this table from `checks/checks.json`; don't edit it by hand.
No KiCad files exist yet, so DRC/ERC would be SKIPPED rather than passed.
<!-- checks:end -->

## Bring-up results
| Test | Board # | Reading | Pass? | Date |
| --- | --- | --- | --- | --- |

## Firmware tested on
| Board revision | Firmware commit | Result |
| --- | --- | --- |

## Open
- **THE GATE: no module has been measured.** Only the Pico's dimensions and pin positions are known
  (21 × 51 mm, datasheet). The SD breakout, OLED, both PSRAM DIP adapters, the BSS138 converter, the
  Serial Wombat VGA breakout and the PS/2 breakout are all estimates, and the PS/2 one is a pure
  guess. Owner to measure: outline, hole positions, header pin count, pin pitch, and which pin is
  pin 1. This blocks stage 4 for either route, though the protoboard route is far more tolerant of
  it — on a 0.1 in grid what matters is pin count and pitch, not exact outlines.
- Socket the Pico or solder it down? Recommendation: socket, so it stays reflashable and reusable.
  Owner decides.
- Does the VGA breakout mount on the board, or stay on a cable? It is the largest unknown footprint
  and a heavy connector. Owner decides.
- Mounting holes and enclosure now, or later? A 3D-printed enclosure is already on the owner's list
  and corner holes are free to add, expensive to retrofit.
