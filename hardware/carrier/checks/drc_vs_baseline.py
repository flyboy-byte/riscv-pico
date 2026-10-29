#!/usr/bin/env python3
"""DRC of a board minus a baseline board's own violations, plus every unconnected item.

    python3 checks/drc_vs_baseline.py BOARD.kicad_pcb BASELINE [-v]

BASELINE is a .kicad_pcb file or `git:<ref>:<path>` (e.g. `git:master:hardware/board.kicad_pcb`, read from the repo the
board is in). Use it when extending an existing board: the original's own errors are subtracted by (type, sorted item
descriptions), so only what your changes added shows. Both boards are upgraded to the installed KiCad first. Exit 0
only with no new violations and nothing unconnected. Needs kicad-cli. `[reported: wideband carrier, 2026-10-23]`
"""
import json, os, subprocess, sys, tempfile


def drc(path, parity, out):
    cmd = ['kicad-cli', 'pcb', 'drc', '--severity-error', '--format', 'json', '-o', out, path]
    if parity:
        cmd.insert(3, '--schematic-parity')
    subprocess.run(cmd, capture_output=True)
    return json.load(open(out))


def key(v):
    return (v['type'], tuple(sorted(i['description'] for i in v['items'])))


def main():
    args = [a for a in sys.argv[1:] if a != '-v']
    if len(args) != 2:
        sys.exit(__doc__)
    board, baseline = os.path.abspath(args[0]), args[1]
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, 'base.kicad_pcb')
        if baseline.startswith('git:'):
            ref, path = baseline[4:].split(':', 1)
            top = subprocess.run(['git', '-C', os.path.dirname(board), 'rev-parse', '--show-toplevel'],
                                 capture_output=True, text=True, check=True).stdout.strip()
            open(base, 'w').write(subprocess.run(['git', '-C', top, 'show', f'{ref}:{path}'], capture_output=True,
                                                 text=True, check=True).stdout)
        else:
            open(base, 'w').write(open(baseline).read())
        subprocess.run(['kicad-cli', 'pcb', 'upgrade', base], capture_output=True)
        b = [key(v) for v in drc(base, False, os.path.join(td, 'b.json'))['violations']]
        cur = drc(board, True, os.path.join(td, 'c.json'))
    new = []
    for v in cur['violations']:
        k = key(v)
        if k in b:
            b.remove(k)
        else:
            new.append(k)
    un = cur.get('unconnected_items', [])
    print(f'DRC vs baseline: {len(new)} new violations, {len(un)} unconnected')
    if '-v' in sys.argv:
        for k in new:
            print('  new:', k[0], '|', ' / '.join(k[1]))
        for u in un:
            print('  open:', ' / '.join(f"{i['description']} @{i['pos']['x']:.2f},{i['pos']['y']:.2f}" for i in u['items']))
    sys.exit(0 if not new and not un else 1)


if __name__ == '__main__':
    main()
