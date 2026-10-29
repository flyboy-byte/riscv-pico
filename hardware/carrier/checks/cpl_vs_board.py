#!/usr/bin/env python3
"""Compare a fab CPL with the footprints in a .kicad_pcb (position, rotation). Exit 1 on any mismatch.
Usage: cpl_vs_board.py BOARD.kicad_pcb CPL.csv   (CPL Y is negated, as KiCad exports it for JLC)"""
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kicadtext import footprints


def main(board, cpl):
    fps = footprints(open(board).read())
    bad = rows = 0
    for r in csv.DictReader(open(cpl)):
        rows += 1
        d = r['Designator']; f = fps.get(d)
        if not f:
            print(f'{d}: in CPL, not on board'); bad += 1; continue
        if abs(f[0] - float(r['Mid X'])) > 0.01 or abs(-f[1] - float(r['Mid Y'])) > 0.01 or (f[2] - float(r['Rotation'])) % 360:
            print(f'{d}: board ({f[0]}, {-f[1]}, {f[2]}) vs CPL ({r["Mid X"]}, {r["Mid Y"]}, {r["Rotation"]})'); bad += 1
    print(f'{rows} CPL rows, {len(fps)} board footprints, {bad} mismatches')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:3]))
