#!/usr/bin/env python3
"""pinmap.csv is the one source for which MCU pin does what. Columns:
  signal, mcu_pin, fw_pin, net, terminal, label, direction, level, notes
mcu_pin = the pin as the module/datasheet names it (D4, PA3); fw_pin = the number the firmware uses (GPIO6 -> 6).
They often differ (XIAO RP2040 D4 is GPIO6), so fw_pin is never guessed from mcu_pin; look it up and cite it in notes.
terminal/label = what is printed on the silkscreen; level e.g. 3V3, 5V; direction in/out/io/pwr

  pinmap.py gen               write firmware/include/pins.h and firmware/pins.py from pinmap.csv
  pinmap.py check [BOARD]     exit 1 if the firmware headers are stale, a signal is duplicated, an MCU pin is used
                              twice, or (with BOARD.kicad_pcb) a pinmap net is missing from the board
The schematic generator reads pinmap.csv too, so board and firmware can't disagree."""
import csv, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kicadtext import nets

SRC, H, PY = 'pinmap.csv', 'firmware/include/pins.h', 'firmware/pins.py'


def rows():
    return [r for r in csv.DictReader(open(SRC)) if r.get('signal', '').strip() and not r['signal'].startswith('#')]


def ident(s):
    return re.sub(r'\W', '_', s.strip()).upper()


def num(r):
    v = (r.get('fw_pin') or '').strip()
    return v if v.isdigit() else None


def render(rs):
    h = ['// Generated from pinmap.csv by pinmap.py. Do not edit; edit pinmap.csv and run `pinmap.py gen`.', '#pragma once']
    p = ['# Generated from pinmap.csv by pinmap.py. Do not edit; edit pinmap.csv and run `pinmap.py gen`.']
    for r in rs:
        n, c = ident(r['signal']), f"{r['mcu_pin'].strip()} net {r['net'].strip()} terminal {r['terminal'].strip()} {r['label'].strip()} {r['direction'].strip()} {r['level'].strip()}".strip()
        if num(r):
            h.append(f'#define PIN_{n} {num(r)}  // {c}')
            p.append(f'PIN_{n} = {num(r)}  # {c}')
        else:
            h.append(f'// {n}: {c} (no firmware pin number)')
            p.append(f'# {n}: {c} (no firmware pin number)')
    return '\n'.join(h) + '\n', '\n'.join(p) + '\n'


def gen():
    h, p = render(rows())
    for path, text in ((H, h), (PY, p)):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'w').write(text)
    print(f'wrote {H} and {PY}')
    return 0


def check(board=None):
    rs, bad = rows(), []
    bad += [f'{r["signal"]}: fw_pin missing (look it up; never guess it from mcu_pin)' for r in rs if r['mcu_pin'].strip() not in ('', '-') and not num(r)]
    for key in ('signal', 'mcu_pin', 'fw_pin'):
        seen = {}
        for r in rs:
            v = r[key].strip()
            if v and v != '-' and v in seen:
                bad.append(f'{key} {v} used twice ({seen[v]} and {r["signal"]})')
            seen[v] = r['signal']
    h, p = render(rs)
    for path, text in ((H, h), (PY, p)):
        if not os.path.exists(path) or open(path).read() != text:
            bad.append(f'{path} is stale: run pinmap.py gen')
    if board:
        have = nets(open(board).read())
        bad += [f'net {r["net"]} ({r["signal"]}) not on the board' for r in rs if r['net'].strip() and r['net'].strip() not in have]
    for b in bad:
        print(b)
    print(f'{len(rs)} pins, {len(bad)} problem(s)')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(gen() if sys.argv[1:2] == ['gen'] else check(*sys.argv[2:3]))
