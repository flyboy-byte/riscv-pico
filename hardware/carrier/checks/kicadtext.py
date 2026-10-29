"""Read a .kicad_pcb as text (no KiCad needed): footprints with position and rotation, and net names."""
import re

_FP = re.compile(r'\((?:footprint|module) "?([^"\s]+)"?(.*?)(?=\n  \((?:footprint|module) |\n  \((?:gr_|segment|via|zone|net |group)|\n\)\s*\Z|\Z)', re.S)


def footprints(text):
    """{reference: (x, y, rotation, library_id)} for every footprint with a reference."""
    out = {}
    for m in _FP.finditer(text):
        body = m.group(2)
        at = re.search(r'\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', body)
        ref = re.search(r'(?:\(property "Reference" "|\(fp_text reference "?)([^"\s)]+)', body)
        if at and ref:
            out[ref.group(1)] = (float(at.group(1)), float(at.group(2)), float(at.group(3) or 0), m.group(1))
    return out


def nets(text):
    """Set of net names declared in the board (KiCad 6-8 `(net N "name")`, and names on pads for KiCad 9+)."""
    return {n for n in re.findall(r'\(net \d+ "([^"]*)"\)', text) if n} | {n for n in re.findall(r'\(net "([^"]+)"\)', text)}
