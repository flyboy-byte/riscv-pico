#!/usr/bin/env python3
"""Vias whose drill lands in an SMD pad (solder wicks down them during assembly; DRC doesn't flag it).

    python3 checks/via_in_pad.py BOARD.kicad_pcb [BASELINE]

BASELINE (a .kicad_pcb or `git:<ref>:<path>`) marks vias the original board already had, such as thermal vias in a
regulator tab: they are listed but don't fail the check. Exit 0 when no other via is in a pad. Needs KiCad's pcbnew
Python module. `[reported: wideband carrier, 2026-10-23]`
"""
import os, subprocess, sys, tempfile

import pcbnew

T = pcbnew.ToMM


def vias(board):
    return [v for v in board.GetTracks() if v.Type() == pcbnew.PCB_VIA_T]


def baseline_vias(board_path, baseline):
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, 'base.kicad_pcb')
        if baseline.startswith('git:'):
            ref, path = baseline[4:].split(':', 1)
            top = subprocess.run(['git', '-C', os.path.dirname(os.path.abspath(board_path)), 'rev-parse',
                                  '--show-toplevel'], capture_output=True, text=True, check=True).stdout.strip()
            open(base, 'w').write(subprocess.run(['git', '-C', top, 'show', f'{ref}:{path}'], capture_output=True,
                                                 text=True, check=True).stdout)
        else:
            open(base, 'w').write(open(baseline).read())
        subprocess.run(['kicad-cli', 'pcb', 'upgrade', base], capture_output=True)
        return [(T(v.GetPosition().x), T(v.GetPosition().y)) for v in vias(pcbnew.LoadBoard(base))]


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    up = baseline_vias(sys.argv[1], sys.argv[2]) if len(sys.argv) == 3 else []
    board = pcbnew.LoadBoard(sys.argv[1])
    pads = [(f.GetReference(), p) for f in board.GetFootprints() for p in f.Pads()
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and p.IsOnCopperLayer()]
    new, old = [], []
    for v in vias(board):
        x, y = T(v.GetPosition().x), T(v.GetPosition().y)
        for ref, p in pads:
            if p.HitTest(v.GetPosition(), v.GetDrillValue() // 2):
                is_up = any(abs(x - a) < 0.01 and abs(y - b) < 0.01 for a, b in up)
                (old if is_up else new).append(f'{ref}-{p.GetNumber()} {v.GetNetname()} @{x:.2f},{y:.2f}')
    print(f'via in pad: {len(new)} new, {len(old)} baseline' + (f' ({"; ".join(new)})' if new else ''))
    sys.exit(1 if new else 0)


if __name__ == '__main__':
    main()
