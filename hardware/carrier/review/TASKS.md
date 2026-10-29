# Review tasks: round <N> (<what changed since the last round>)

Written <date>. The work list for an outside reviewer. Each task has a question to answer, the files that answer it,
how to check it with a shell and without one, and what "done" means. They are in order of value: if you run short
on time or credits, the top ones matter most. Record every task in `FINDINGS.md`, even one you skipped, so we can see
what was covered.

File names are the review pack's (`INDEX.md` maps each to its repo path).

**How to work:**
- Start at TK1 and keep going without waiting for a reply. Nobody is watching live; the owner reads the result
  later. Ask nothing you can decide yourself; write the assumption in the finding instead.
- After each task, add its row to `FINDINGS.md`. With git, commit it on your review branch, and push if you are allowed to.
  A half-finished review that is written down is worth far more than a finished one that isn't.
- When about a quarter of your budget is left, stop starting tasks. Finish the verdict and the coverage table, commit and push.
- Run the checks with `python3 checks/run_all.py --report <your folder>`, which leaves the designer's files alone.
- Going past this list is welcome. Put it under TK99.

| ID | Area | Question (answer it yes or no, with numbers) | Effort |
| --- | --- | --- | --- |
| TK1 | Fab files | Would the assembler place every part right: position, rotation, part number, not-fitted list? | M |
| TK2 | <the new circuit> | <one question with a yes/no answer> | M |
| TK3 | Power | <the supply path's worst case: surge, reverse, short> | S |
| TK4 | Firmware | <what changed, and what it must never do> | M |
| TK5 | These docs | What was missing or unclear here, and what would have saved you time? | S |

Effort: S under 15 min, M 15-45 min, L longer (with a shell; reading-only takes about twice as long).

---

### TK1. Fab files against the board

- **Why:** a part placed rotated or swapped is the most common way a first assembled order fails.
- **Files:** `<board>-cpl.csv`, `<board>-bom.csv`, `<board>-not-fitted.csv`, `<board>-parts.txt`, `<board>-nets.txt`,
  the `.kicad_pcb`.
- **Shell:** `python3 checks/cpl_vs_board.py ...`, the project's rotation check. Then pick the five parts most likely to be
  wrong (polarised, multi-pin, tab parts) and check them yourself.
- **Files only:** for each CPL line, find the part in `<board>-parts.txt` and its pads in `<board>-nets.txt`.
- **Done:** every BOM line and CPL line marked right or wrong, with the check you used.

### TK2. <the new circuit>

- **Why:** <what it does and what goes wrong if it's wrong>
- **Files:** <schematic, nets, sim decks, the doc that claims it works>
- **Shell:** <the sim or check to run>
- **Questions:** <the specific numbers you want checked: gain, full scale, stability into the load, fault current>
- **Done:** <the number or yes/no that closes it>

### TK5. These review docs

Tell us what was missing, wrong or slow here. The next reviewer gets the fix.
