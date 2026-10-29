#!/usr/bin/env python3
"""Measure an Edge_Cuts Gerber (arcs included) and draw it with CPL part positions to SVG.
Usage: gerber_outline.py EDGE_CUTS.gbr [CPL.csv] [out.svg]. Then render (rsvg-convert) and LOOK at it."""
import csv, math, re, sys

def outline(g):
    fs = re.search(r'%FSLAX\d(\d)Y\d\d\*%', g); s = 10 ** int(fs.group(1))
    if '%MOMM*%' not in g: sys.exit('inch Gerber: add a 25.4 factor')
    segs, x, y, mode = [], 0.0, 0.0, 'G01'
    for t in re.findall(r'(G0[123])|X(-?\d+)Y(-?\d+)(?:I(-?\d+)J(-?\d+))?D0([12])', g):
        if t[0]: mode = t[0]; continue
        nx, ny = int(t[1]) / s, int(t[2]) / s
        if t[5] == '1':
            if mode == 'G01' or not t[3]:
                segs.append([(x, y), (nx, ny)])
            else:
                cx, cy = x + int(t[3]) / s, y + int(t[4]) / s; r = math.hypot(x - cx, y - cy)
                a0, a1 = math.atan2(y - cy, x - cx), math.atan2(ny - cy, nx - cx)
                if mode == 'G03' and a1 <= a0: a1 += 2 * math.pi
                if mode == 'G02' and a1 >= a0: a1 -= 2 * math.pi
                segs.append([(cx + r * math.cos(a0 + (a1 - a0) * k / 24), cy + r * math.sin(a0 + (a1 - a0) * k / 24)) for k in range(25)])
        x, y = nx, ny
    return segs

def main(gbr, cpl=None, svg=None):
    segs = outline(open(gbr).read())
    pts = [p for sg in segs for p in sg]; X = [p[0] for p in pts]; Y = [p[1] for p in pts]
    w, h = max(X) - min(X), max(Y) - min(Y)
    print(f'outline (measured, Gerber, arcs included): {w:.2f} x {h:.2f} mm = {w/25.4:.2f} x {h/25.4:.2f} in')
    parts = [(r['Designator'], float(r['Mid X']), float(r['Mid Y'])) for r in csv.DictReader(open(cpl))] if cpl else []
    if svg:
        pad = 5; W, H = w + 2 * pad, h + 2 * pad
        o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W*4:.0f}" height="{H*4:.0f}" viewBox="{min(X)-pad} {-max(Y)-pad} {W} {H}">',
             f'<rect x="{min(X)-pad}" y="{-max(Y)-pad}" width="{W}" height="{H}" fill="white"/>']
        o += ['<polyline fill="none" stroke="black" stroke-width="0.3" points="' + ' '.join(f'{a:.3f},{-b:.3f}' for a, b in sg) + '"/>' for sg in segs]
        o += [f'<circle cx="{a}" cy="{-b}" r="0.8" fill="red"/><text x="{a+1}" y="{-b-1}" font-size="2.2" fill="red">{d}</text>' for d, a, b in parts]
        open(svg, 'w').write('\n'.join(o + ['</svg>']))

if __name__ == '__main__':
    main(*sys.argv[1:4])
