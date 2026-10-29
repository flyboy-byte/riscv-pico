# STATE — Pico carrier board

Status: **Stage 4, fit check — blocked on measurement (2026-10-28)**
**Next action: [MEASURE.md](MEASURE.md).** Six modules are still guessed; that is the only thing between here and a buildable protoboard.
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
| 3 | Schematic | Generated from code; netlist self-check passes | **Done 2026-10-28** — `gen_proto.py` holds it as a table; all 61 links verified against `pinmap.csv` |
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

## Protoboard draft (2026-10-28)

`gen_proto.py` → `carrier_proto.kicad_pcb`, rendered in `renders/proto-draft6/`, wire list in
`BUILD_SHEET.md`. 18 footprints, 28 nets, **61 wire links to solder**, on a 90 × 70 mm
(3.54 × 2.76 in) protoboard, 35 × 27 holes, using cols 1–31 and rows 2–23.

**Everything measurable lives in two CSVs.** `pinmap.csv` is the electrical truth, generated from
`hw_config.h` and guarded by a check. `modules.csv` holds every physical guess — pin counts, pin
order, body outlines, confidence. Measuring a module means editing one row and re-running; nothing
else is touched. `gen_proto.py` refuses to run if a `pin_order` names a function it has no net for,
or if a pin count disagrees with the chosen footprint.

- Left half: SD and the PSRAM group, each DIP socket two holes from the Pico's left pin row with
  the SCK/MOSI side of the DIP facing it. Right half: power in, OLED, PS/2 through the BSS138, VGA
  furthest from the PSRAM group. That split is the separation HARDWARE_SCHEMATIC.md asks for.
- **DRC's 61 "unconnected items" are the 61 wire links**, not faults. There are deliberately no
  traces — on a protoboard the connections are wires. The two numbers matching is the check; if
  they ever disagree, something is wrong. This is why DRC is marked advisory in `checks.json`.
- The Pico is **two 1×20 sockets 0.7 in apart**, not one 2×20. That is how it is actually built on
  protoboard, and it makes the pin numbering unambiguous instead of depending on KiCad's 2×20 pad
  order. Right socket pad *n* is Pico pin 41−*n*, because pins 21–40 run back up the right side.

### What the checks caught

Four checks, three of them written for this project. Each was negative-tested by deliberately
breaking the design and confirming it failed.

| Check | What it caught |
| --- | --- |
| `grid_check.py` | Draft 1 used KiCad's stock THT capacitor footprints. **Every one of them is 5.00 mm pitch**, so the decoupling caps landed between protoboard holes. There are no on-grid THT capacitor footprints in KiCad at all, so `carrier.pretty/` now holds two. |
| `body_check.py` | Pads fitting does not mean modules fit. With all modules on-board the bodies collided in **7 places** — the SD breakout alone overlapped the Pico by 18 × 23 mm, and PS/2 and VGA hung off the board edge. Led to the off-board decision below. |
| `fw_pinmap_check.py` | Nothing yet, but it is the one that matters most long-term: it reads `hw_config.h` directly and fails if any of the 18 signals drifts from `pinmap.csv`. Without it, a firmware pin change would leave the layout, the wire list and the build sheet all self-consistent and all wrong. |
| KiCad DRC | 6 courtyard overlaps and a mounting hole inside `J_SD`'s courtyard, in draft 2. |

### Draft history

| Draft | What changed |
| --- | --- |
| 1 | First placement on a 96.5 × 88.9 mm board. Wasted the bottom third; the four PSRAM pull-ups physically overlapped each other; capacitors off-grid. |
| 2 | Re-placed, shrank the board to 90 × 70 mm. |
| 3 | Cleared 6 courtyard overlaps; dropped the mounting-hole footprints (a protoboard already has holes everywhere, so which become mounting points is an enclosure decision). |
| 4 | Moved every physical guess into `modules.csv`; drew module **bodies** on F.Fab for the first time, which exposed the 7 collisions. |
| 5 | SD, VGA, PS/2 and OLED bodies moved off-board; added the Pico's own 21 × 51 mm outline. |
| 6 | Hid part-name text that collided on the silkscreen at this density. Current. |

### Decision I made for you, which you can reverse

**SD, VGA, PS/2 and the OLED are `body_on_board = no`** — only their headers are on the carrier, and
the modules mount to the enclosure wall on short cables. Reasoning: all four are things a user
touches or looks at (a card slot, two panel connectors, a display), so a wall is where they belong
anyway, and with them on-board the bodies simply do not fit. Flip any row in `modules.csv` to `yes`
and re-run to see the cost. Recorded in `MEASURE.md` too.

## Checks
<!-- checks:start -->
| Check | Result | Summary | Date | Files (sha256/12) |
| --- | --- | --- | --- | --- |
| Pin map matches firmware hw_config.h | PASS | PASS firmware pinmap: 18 signals match hw_config.h | 2026-10-28 | `pinmap.csv` 4ae5c3210bba |
| Pads on the protoboard grid | PASS | PASS grid: all 108 pads on the 2.54 mm grid | 2026-10-28 | `carrier_proto.kicad_pcb` 41280eb1efca |
| Module bodies do not collide | PASS | PASS bodies: 5 on-board bodies (J_LVL_LV, PICO, TB1, U_RAM1, U_RAM2), none overlapping, all on the board | 2026-10-28 | `bodies.json` f88fb4b391ff, `modules.csv` 51aa061fb3c0 |
| DRC (unconnected = the wire list) | FAIL (advisory) | DRC 61 errors: unconnected_items 61 (report checks/out/carrier_proto-drc.json) | 2026-10-28 | `carrier_proto.kicad_pcb` 41280eb1efca |
| No hand edits waiting | PASS | no drift | 2026-10-28 |  |

Written by `checks/run_all.py` at commit 1647a64. Don't edit by hand.
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
  and corner holes are free to add, expensive to retrofit. The protoboard draft has **no**
  mounting-hole footprints — the board already has holes everywhere, so which ones become mounting
  points is an enclosure decision. The PCB variant would need real ones in the corners.
- **Decoupling placement needs a refinement pass.** C1/C2 are on the grid beside each PSRAM chip,
  but a DIP-8's VCC (pin 8) and GND (pin 4) are diagonally opposite, so the cap cannot sit across
  both without a detour. Getting this as tight as possible is the single most important physical
  detail on the board, since a sagging PSRAM VCC is the suspected fault mechanism.
- **Where does the BSS138's LV reference come from?** The draft takes it from the external 3.3 V
  rail, to respect the rule that pin 36 feeds PSRAM and its pull-ups only. But a level converter's
  LV reference should match the logic it translates, which is the Pico's own I/O rail. The
  converter draws microamps, so taking LV from pin 36 would be electrically more correct and
  practically harmless. Owner decides; the draft took the conservative reading of the rule.
