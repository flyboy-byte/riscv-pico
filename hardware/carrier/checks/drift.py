#!/usr/bin/env python3
"""Notice when someone changed a generated KiCad file by hand (e.g. the owner in the KiCad GUI).

  drift.py record FILE...   after a generator writes FILEs: snapshot them to checks/.snapshots/ and store hashes
  drift.py check            exit 1 if any recorded file changed since; for .kicad_pcb, list footprints that moved,
                            rotated, appeared or disappeared, and nets added or removed

On drift: show the owner the list and ask whether to fold the change into the generator before regenerating.
Never regenerate over a drifted file without that answer."""
import hashlib, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kicadtext import footprints, nets

DB, SNAP = 'checks/generated.json', 'checks/.snapshots'


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def record(files):
    db = json.load(open(DB)) if os.path.exists(DB) else {}
    for f in files:
        db[f] = sha(f)
        dst = os.path.join(SNAP, f)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(f, dst)
    json.dump(db, open(DB, 'w'), indent=1)
    print(f'recorded {len(files)} generated file(s)')
    return 0


def pcb_diff(old, new):
    a, b = footprints(old), footprints(new)
    out = [f'  {r}: added' for r in sorted(b.keys() - a.keys())] + [f'  {r}: removed' for r in sorted(a.keys() - b.keys())]
    for r in sorted(a.keys() & b.keys()):
        (x0, y0, r0, l0), (x1, y1, r1, l1) = a[r], b[r]
        if abs(x0 - x1) > 0.001 or abs(y0 - y1) > 0.001:
            out.append(f'  {r}: moved ({x0}, {y0}) -> ({x1}, {y1}) mm')
        if (r0 - r1) % 360:
            out.append(f'  {r}: rotated {r0} -> {r1}')
        if l0 != l1:
            out.append(f'  {r}: footprint {l0} -> {l1}')
    na, nb = nets(old), nets(new)
    out += [f'  net added: {n}' for n in sorted(nb - na)] + [f'  net removed: {n}' for n in sorted(na - nb)]
    return out or ['  (text changed; no footprint or net difference found: tracks, zones or graphics)']


def check():
    if not os.path.exists(DB):
        print('no generated files recorded'); return 0
    drifted = 0
    for f, h in json.load(open(DB)).items():
        if not os.path.exists(f):
            print(f'{f}: missing'); drifted += 1; continue
        if sha(f) == h:
            continue
        drifted += 1
        print(f'{f}: changed since generated')
        if f.endswith('.kicad_pcb'):
            print('\n'.join(pcb_diff(open(os.path.join(SNAP, f)).read(), open(f).read())))
    print(f'{drifted} drifted file(s)' if drifted else 'no drift')
    return 1 if drifted else 0


if __name__ == '__main__':
    if sys.argv[1:2] == ['record']:
        sys.exit(record(sys.argv[2:]))
    sys.exit(check())
