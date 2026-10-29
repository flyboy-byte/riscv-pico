# Findings: <reviewer> (<model or person>), <date>

Reviewed: commit `<git rev-parse --short HEAD>` on `<branch>`. Mode: <A, the pack only | B, the full repo>.
Tools I could run: <shell yes/no, KiCad yes/no, ngspice + TI model yes/no, firmware build yes/no>.

## Verdict

Would I order these files as they are? **<yes / no>**: <one sentence why>.

## Coverage (one row per task in TASKS.md; fill it in as you go, not at the end)

| Task | Status | Finding IDs | What I did (command, file, calculation) |
| --- | --- | --- | --- |
| TK1 Fab files | <OK / FINDING / PARTLY / NOT CHECKED> | | |
| TK2 <area> | | | |
| TK3 <area> | | | |
| TK4 <area> | | | |
| TK5 These docs | | | |
| TK99 Beyond the list | | | |

Status: OK = checked and found right; FINDING = see the table below; PARTLY = say what is left; NOT CHECKED = say why
(no tool, no time, no file).

## Findings

| ID | Task | Severity | Location | Evidence (numbers) | Smallest fix |
| --- | --- | --- | --- | --- | --- |
| <initials>1 | TK? | <BLOCKER / BUG / RISK / NOTE> | <file:line, or ref and x/y mm> | <measured or calculated, with source> | <one change> |

Severity: BLOCKER = don't order; BUG = wrong but workable; RISK = could bite (say when); NOTE = worth knowing.
Tag each piece of evidence: MEASURED (you ran it), CALCULATED (show the sum), DOCUMENTED (name the datasheet and page),
INFERRED (your reasoning). A finding without a number or a source is a NOTE.

### The level we want

- Useful: "`heater_control.cpp:240`: the heater voltage goes negative above the target temperature and is then
  squared into a duty. Feeding the host model a sensor at 840 C gives 100 % duty, so a hotter sensor gets more heat.
  Fix: clamp at 0 before squaring." It has a location, a run with numbers, and a one-line fix.
- Useful: "R3 100k against the MCU's 25-55k internal pull-up on the same pin gives 2.1-2.6 V, a logic high, so the
  output sits at full scale for 0.8 s at every power-up. Fix: R3 to 4.7k (0.52 V worst case)." It does the sum and
  names the condition that makes it matter.
- Not useful: "consider adding ESD protection to the output". Where, against what, and why is what's there not enough?

## Checked and found right

<short list: what you verified, so the next reviewer can skip or re-check it>

## Could not check

<what, and what you would need>

## TK5: what would have made this review faster

<missing files, unclear instructions, wrong paths>
