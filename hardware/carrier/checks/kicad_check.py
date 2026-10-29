#!/usr/bin/env python3
"""DRC or ERC through kicad-cli (KiCad 8+; verified on 10.0.7), with a one-line result for run_all.py.

  kicad_check.py drc BOARD.kicad_pcb [--all]      error-level DRC (--all: warnings too); report in checks/out/<board>-drc.json
  kicad_check.py erc SCHEMATIC.kicad_sch [--all]  error-level ERC; report in checks/out/<schematic>-erc.json

Exit 0 clean, 1 violations, 77 when kicad-cli is not installed (run_all.py records that as SKIPPED, never PASS)."""
import collections, json, os, shutil, subprocess, sys


def main(kind, path, *flags):
    if not shutil.which('kicad-cli'):
        print('kicad-cli not installed'); return 77
    os.makedirs('checks/out', exist_ok=True)
    out = os.path.join(os.environ.get('CHECKS_REPORT_DIR', 'checks/out'), f'{os.path.splitext(os.path.basename(path))[0]}-{kind}.json')
    sev = [] if '--all' in flags else ['--severity-error']
    cmd = ['kicad-cli', 'pcb' if kind == 'drc' else 'sch', kind, *sev, '--format', 'json', '-o', out, path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        d = json.load(open(out))
    except (OSError, ValueError):
        print(f'{kind} did not run: ' + ((r.stderr or r.stdout).strip().splitlines() or ['no output'])[-1]); return 1
    items = d.get('violations', []) + d.get('unconnected_items', []) + d.get('schematic_parity', [])
    for sheet in d.get('sheets', []):
        items += sheet.get('violations', [])
    kinds = collections.Counter(x.get('type', '?') for x in items).most_common(4)
    level = 'all severities' if '--all' in flags else 'errors'
    print(f'{kind.upper()} {len(items)} {level}' + (': ' + ', '.join(f'{k} {n}' for k, n in kinds) if items else '') + f' (report {out})')
    return 1 if items else 0


if __name__ == '__main__':
    if len(sys.argv) < 3 or sys.argv[1] not in ('drc', 'erc'):
        sys.exit(__doc__)
    sys.exit(main(*sys.argv[1:]))
