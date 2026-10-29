#!/usr/bin/env python3
"""Module bodies must not overlap each other or hang off the board.

A module's header is small; its BODY is usually much bigger and overhangs. A layout can have every
pad perfectly placed and still be unbuildable because two breakouts occupy the same air. Pad-level
checks and KiCad's courtyard DRC both miss this, because the body is drawn on F.Fab.

Reads the F.Fab rectangles that gen_proto.py draws from modules.csv, plus the Pico's own outline.
One result line, exit 0/1.
"""

import os
import sys

MARGIN = 0.5  # mm of air required between two bodies


def load_bodies(path):
    """Exact ref -> rectangle, written by gen_proto.py. No guessing by proximity."""
    import json
    with open(path) as fh:
        d = json.load(fh)
    return d["board"], d["bodies"]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, os.pardir, "bodies.json")
    if not os.path.exists(path):
        print("SKIPPED bodies: %s does not exist (run gen_proto.py first)" % path)
        return 0

    (bx0, by0, bx1, by1), rects = load_bodies(path)
    if not rects:
        print("SKIPPED bodies: no module bodies recorded")
        return 0
    named = sorted(rects.items())

    problems = []
    for i, (ref_a, a) in enumerate(named):
        if a[0] < bx0 - 1e-6 or a[1] < by0 - 1e-6 or a[2] > bx1 + 1e-6 or a[3] > by1 + 1e-6:
            problems.append("%s body runs off the board: %.1f,%.1f to %.1f,%.1f mm (board is "
                            "%.1f,%.1f to %.1f,%.1f)"
                            % (ref_a, a[0], a[1], a[2], a[3], bx0, by0, bx1, by1))
        for ref_b, b in named[i + 1:]:
            ox = min(a[2], b[2]) - max(a[0], b[0])
            oy = min(a[3], b[3]) - max(a[1], b[1])
            if ox > -MARGIN and oy > -MARGIN:
                problems.append("%s and %s bodies overlap by %.1f x %.1f mm"
                                % (ref_a, ref_b, max(ox, 0), max(oy, 0)))

    if problems:
        print("FAIL bodies: %d physical collision(s) among %d on-board bodies"
              % (len(problems), len(rects)))
        for p in problems:
            print("  " + p)
        return 1
    print("PASS bodies: %d on-board bodies (%s), none overlapping, all on the board"
          % (len(rects), ", ".join(sorted(rects))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
