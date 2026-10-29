# Independent review of a PCB before it is ordered: {rev} at commit {head}

You are reviewing a circuit board (and its firmware, if any) before it is ordered. You did not design it.
The design and its documents were written by <who>; you are the outside check.
Treat every conclusion in our documents as a claim to test against the files and first principles, not as fact.

**What it is:** <two lines: what the board does, what is new on it, what has been built so far>

**Read, in this order:**
1. `TASKS.md`: the work list (TK1, TK2, ...), in order of value, with how to check each task with and without a shell.
2. `HANDOFF.md`: what changed since the last rounds, what is still open, and what is **known and accepted** (don't
   re-report those).
3. `INDEX.md`: every file here and where it came from. If you were given one zip, unzip it first.
4. `FINDINGS-TEMPLATE.md`: copy it to `FINDINGS.md` and fill it in.

**How to work:**
- Start now with TK1 and carry on through the list without waiting for replies. The owner reads your report later.
  Where you would ask a question, make the assumption, say so in the finding, and keep going.
- Fill in `FINDINGS.md` after every task, not at the end. If you have git, commit after each task. If you are
  in a chat, put the coverage table and the findings so far in each reply. A finding that isn't written down
  is lost if you run out of budget.
- When about a quarter of your budget is left, stop starting tasks and write the verdict and coverage.
- Evidence is numbers: a run you made, a sum you show, or a datasheet page you name. Without one, it's a NOTE.
- Don't edit design files (schematic, board, generators, firmware behaviour). Propose the smallest fix instead.
  You may write your own tests, sims and scripts in your own folder.
- Going beyond the list is welcome, especially circuit theory. Put it under TK99.

**The deliverable** is your `FINDINGS.md` (plus any scripts and raw output), starting with: "Would I order these
files as they are? yes / no", and one sentence why.
