# Pico carrier board — PCB project

This is a custom PCB project set up with the `pcb-design` skill (KiCad, Freerouting, JLCPCB/LCSC).
The procedure lives in that skill; this file only says where the state lives.

## Start every session here
0. **Load the `pcb-design` skill** (Skill tool) before any work in this folder, and again whenever
   the task is part choice, schematic, placement, routing, checks, renders, fab files, audit,
   ordering or bring-up. If a file listed below is missing, run the skill's "Scaffold the project
   first" steps for the missing files only. If the skill is not installed, say so and stop.
1. Read `STATE.md` (stage, revision, decisions already made, what is open). If it lists a review page, read its
   answered questions (`ArtifactData list questions`) and file them before anything else. Then read `HANDOFF.md`
   if it exists: the last long session's run history, last raw output and next steps. It is a snapshot, so verify it.
2. Work the current stage only. A stage is done when its exit condition in `STATE.md` is met, not
   when more docs exist.
3. End the session by updating `STATE.md`. After a long session, also replace `HANDOFF.md` and write lessons (the
   skill's `WORKFLOW.md`, "The pause point").

## Rules for this project
- Facts about a built board come only from `fab/<rev>/` (the files that were ordered) or the board
  itself. Name the file in every claim. Drafts and `archive/` are never evidence.
- Revision letters are never reused; used letters are listed in `STATE.md`.
- Every number names its source (`parts_research.md`, a datasheet URL, a measured STEP, or
  "scaled" / "inferred").
- KiCad files are generated from code. The owner may open and edit them in KiCad; before regenerating run
  `checks/drift.py check` and ask before folding or overwriting any edit it lists.
- Pin assignments live only in `pinmap.csv`; run `checks/pinmap.py gen` after changing it.
- Wiring instructions use the silkscreen terminal numbers and labels, never reference designators.
- Run `checks/run_all.py` after every design change; it writes the checks table in `STATE.md`.
- Fab files reach `fab/` only through `checks/release.py` (the money gate). Nothing is called ready to order
  without a release. Record each order in `ORDERS.md` and each caught mistake in `LESSONS.md`.
- Do the work as code and commands (generator scripts, `checks/`, `kicad-cli`), never GUI clicks.
- After every placement or routing change, export a picture and look at it yourself before reporting.
- Show the owner an artifact page at the fit check, with renders before ordering, and for each
  audit; record its link in `STATE.md`.
- Physical numbers in mm and inches, each marked measured / datasheet / scaled / inferred.

## Files
| File | Role |
| --- | --- |
| `STATE.md` | Living state: stage, revision, decisions, checks, open items |
| `REQUIREMENTS.md` | The owner's answers; what the board must do and fit |
| `parts_research.md` | Per-part facts with a source URL for every value |
| `AUDIT.md` | Audit hand-off and the findings of each round |
| `fab/<rev>/` | Exactly what was uploaded for each order, committed the day it was ordered |
| `archive/` | Designs that were never built |
| `checks/` | Check scripts, `checks.json` (what `run_all.py` runs), `last_run.json` |
| `pinmap.csv` | The only place pin assignments live; generates `firmware/` headers |
| `firmware/` | Firmware for this board, tagged with the same revision |
| `ORDERS.md` | Every order: date, number, cost split, what went wrong |
| `LESSONS.md` | Mistakes caught and what caught them |
| `audit/` | Packs built for outside auditors |
| `renders/<rev>/` | Exported pictures by stage, kept for comparison |
