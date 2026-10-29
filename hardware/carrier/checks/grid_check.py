#!/usr/bin/env python3
"""Every pad must land on a protoboard hole.

The protoboard route is only buildable if each pad sits on the 2.54 mm grid. KiCad's own THT
passive footprints are mostly 5.00 mm pitch, so this is easy to get wrong by picking a stock
footprint, and the result is a part whose leads fall between holes. One result line, exit 0/1.
"""

import os
import sys

GRID = 2.54
TOL = 1e-6


def main():
    board_path = sys.argv[1] if len(sys.argv) > 1 else "carrier_proto.kicad_pcb"
    if not os.path.exists(board_path):
        print("SKIPPED grid: %s does not exist" % board_path)
        return 0
    try:
        import pcbnew
    except ImportError:
        print("SKIPPED grid: pcbnew not importable")
        return 0

    board = pcbnew.LoadBoard(board_path)

    # The grid's origin is the first pad, not the board corner: a protoboard's hole field has its
    # own offset from the edge, so what matters is that pads are commensurate with each other.
    pads = [(fp.GetReference(), pad.GetNumber(), pad.GetPosition())
            for fp in board.GetFootprints() for pad in fp.Pads()]
    if not pads:
        print("FAIL grid: board has no pads")
        return 1

    ox = min(p[2].x for p in pads)
    oy = min(p[2].y for p in pads)
    bad = []
    for ref, num, pos in pads:
        dx = pcbnew.ToMM(pos.x - ox) / GRID
        dy = pcbnew.ToMM(pos.y - oy) / GRID
        if abs(dx - round(dx)) > TOL or abs(dy - round(dy)) > TOL:
            bad.append("%s.%s off by (%.3f, %.3f) holes" % (ref, num, dx - round(dx), dy - round(dy)))

    if bad:
        print("FAIL grid: %d of %d pads are not on the 2.54 mm grid" % (len(bad), len(pads)))
        for b in bad[:12]:
            print("  " + b)
        return 1
    print("PASS grid: all %d pads on the 2.54 mm grid" % len(pads))
    return 0


if __name__ == "__main__":
    sys.exit(main())
