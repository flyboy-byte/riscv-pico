# LESSONS — carrier board

Mistakes caught and what caught them. A lesson earns a line here only once something actually
caught it; "I thought about it" does not count.

| # | Mistake | What caught it | Fix |
| --- | --- | --- | --- |
| L1 | Used KiCad's stock THT capacitor footprints on a 2.54 mm protoboard layout. **Every THT capacitor footprint KiCad ships is off-grid** (5.00 mm pitch and similar) — there is not one on-grid option in the whole library. The caps' pads landed between holes. | `checks/grid_check.py`, written for this project | `carrier.pretty/` with `C_THT_P2.54mm` and `C_THT_P5.08mm` |
| L2 | Assumed that if the pads fit, the board fits. They are different questions: a breakout's **body** is much larger than its header and overhangs it. With every module on-board the bodies collided in 7 places, and the SD breakout alone overlapped the Pico by 18 × 23 mm. Neither pad-level checks nor KiCad's courtyard DRC sees this, because the body is on F.Fab. | `checks/body_check.py`, written for this project after the first render with bodies drawn | Draw module bodies from measured/estimated outlines and check them as rectangles; move user-facing modules off-board |
| L3 | Placed the four PSRAM pull-ups one hole apart. Their bodies physically overlapped. | KiCad DRC, `courtyards_overlap` | Two holes apart |
| L4 | Put mounting-hole footprints in the corners of a **protoboard** layout. A protoboard already has holes everywhere, so this invents precision that is not there, and one of them landed inside `J_SD`'s courtyard. | KiCad DRC, `npth_inside_courtyard` | Dropped them; which holes become mounting points is an enclosure decision |
| L5 | First board size was picked before placing anything, and was a third larger than needed. | Printing the hole extent actually used, every run | Report `cols a-b, rows c-d of N` on every generate and size the board to it |
| L6 | Nearly shipped a check that named parts by nearest footprint centre, which mislabelled a body as the wrong reference in its own failure message. | Reading the failure output instead of just the exit code | Generator writes `bodies.json` with exact refs; the check reads that |

## Candidates to send back to the `pcb-design` skill

Proposed, not yet agreed with the owner. Each would help any board, not just this one.

- **L2 generalises.** A fit check that only looks at pads or courtyards will pass a layout whose
  modules physically cannot coexist. Worth a line in `reference/placement-and-routing.md`: draw
  module bodies and check them as rectangles, separately from DRC.
- **L1 generalises to any protoboard or on-grid layout.** KiCad ships no on-grid THT capacitor
  footprint; a project doing grid work needs its own library and should not assume otherwise.
- **A negative test for every check.** Three checks here were each proven by deliberately breaking
  the design and confirming the failure, which is how L6 was found. A check that has never failed
  has not been tested.
