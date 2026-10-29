#!/usr/bin/env python3
"""Generate the protoboard-layout KiCad board from pinmap.csv + modules.csv.

This is the ONE-SIDED PROTOTYPE BOARD draft. It is not a board to order: it is a layout plan for a
hand-wired protoboard, so every part sits on a 2.54 mm (0.1 in) grid and every connection is a wire
link you solder. KiCad is used because it gives a real netlist, a ratsnest you can look at, and a
DRC -- it proves the wiring before you cut a single wire.

    python3 gen_proto.py              -> carrier_proto.kicad_pcb
    python3 gen_proto.py --report     -> also print the wire list and readiness

Where the facts come from:
    pinmap.csv   Pico pin -> net, taken from the firmware's hw_config.h and guarded by
                 checks/fw_pinmap_check.py. These are compiled into firmware; the layout routes
                 around them, never the reverse.
    modules.csv  Every physical guess: pin counts, pin order, body outlines, confidence.
                 MEASURE A MODULE -> EDIT ITS ROW -> RE-RUN. Nothing else needs touching.
    NETS below   Which net each module FUNCTION carries. This is the schematic, and it does not
                 change when you measure; only the order of the functions does.
"""

import argparse
import csv
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
FPLIB = "/usr/share/kicad/footprints"
GRID = 2.54  # mm, 0.1 in -- the protoboard hole pitch. Everything lands on this.

# Board = a standard 90 x 70 mm (3.54 x 2.76 in) protoboard -- the "7x9 cm" size that
# HARDWARE_SCHEMATIC.md already names as common hobbyist stock. 35 x 27 holes.
BOARD_W, BOARD_H = 90.0, 70.0
ORIGIN_X, ORIGIN_Y = 3.81, 3.81  # 1.5 grid of margin before the first hole

# --- the schematic: which net each module function carries --------------------------------------
# Keyed by reference, then by the function names used in modules.csv's pin_order.
NETS = {
    "J_SD":     {"CS": "SD_CS", "SCK": "SD_SCK", "MOSI": "SD_MOSI", "MISO": "SD_MISO",
                 "VCC": "+3V3_EXT", "GND": "GND"},
    "J_OLED":   {"GND": "GND", "VCC": "+3V3_EXT", "SCL": "OLED_SCL", "SDA": "OLED_SDA"},
    # APS6404L / LY68L6400 SOP-8: CE# SO(SIO1) SIO2 VSS SI(SIO0) SCLK SIO3 VCC.
    # SIO2/SIO3 are WP/HOLD and must be pulled to VCC in single-SPI mode -- R1..R4 do that.
    "U_RAM1":   {"CE": "PSRAM_CS1", "SO": "PSRAM_MISO", "SIO2": "RAM1_WP", "VSS": "GND",
                 "SI": "PSRAM_MOSI", "SCLK": "PSRAM_SCK", "SIO3": "RAM1_HOLD", "VCC": "+3V3_PICO"},
    "U_RAM2":   {"CE": "PSRAM_CS2", "SO": "PSRAM_MISO", "SIO2": "RAM2_WP", "VSS": "GND",
                 "SI": "PSRAM_MOSI", "SCLK": "PSRAM_SCK", "SIO3": "RAM2_HOLD", "VCC": "+3V3_PICO"},
    # LV reference comes from the EXTERNAL 3.3 V rail, not Pico pin 36, so pin 36 stays dedicated
    # to PSRAM VCC and its pull-ups. See STATE.md -- this is an open decision, not a settled one.
    "J_LVL_LV": {"LV": "+3V3_EXT", "LV1": "PS2_DATA_LV", "LV2": "PS2_CK_LV",
                 "LV3": None, "LV4": None, "GND": "GND"},
    "J_LVL_HV": {"HV": "+5V_EXT", "HV1": "PS2_DATA_HV", "HV2": "PS2_CK_HV",
                 "HV3": None, "HV4": None, "GND": "GND"},
    "J_PS2":    {"DATA": "PS2_DATA_HV", "CLK": "PS2_CK_HV", "5V": "+5V_EXT", "GND": "GND"},
    "J_VGA":    {"VSYNC": "VGA_VSYNC", "HSYNC": "VGA_HSYNC", "R": "VGA_R", "G": "VGA_G",
                 "B": "VGA_B", "GND": "GND"},
    "TB1":      {"5V": "+5V_EXT", "3V3": "+3V3_EXT", "GND": "GND"},
}

# Parts that are not module headers: passives, chosen for the grid rather than measured.
PASSIVES = {
    # KiCad's own THT capacitor footprints are ALL off the 2.54 mm grid (5.00 mm pitch and the
    # like), which puts a pad between protoboard holes. carrier.pretty holds on-grid ones.
    "C1": ("carrier:C_THT_P2.54mm", ["+3V3_PICO", "GND"], "100n RAM1"),
    "C2": ("carrier:C_THT_P2.54mm", ["+3V3_PICO", "GND"], "100n RAM2"),
    "C3": ("carrier:C_THT_P5.08mm", ["+3V3_EXT", "GND"], "10u bulk"),
    "R1": ("Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
           ["RAM1_WP", "+3V3_PICO"], "10k"),
    "R2": ("Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
           ["RAM1_HOLD", "+3V3_PICO"], "10k"),
    "R3": ("Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
           ["RAM2_WP", "+3V3_PICO"], "10k"),
    "R4": ("Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
           ["RAM2_HOLD", "+3V3_PICO"], "10k"),
}

# Footprint per module where it is not just a 1xN pin socket. Pin count is cross-checked.
FOOTPRINT = {
    "U_RAM1": ("Package_DIP:DIP-8_W7.62mm_Socket", 8),
    "U_RAM2": ("Package_DIP:DIP-8_W7.62mm_Socket", 8),
    "TB1": ("TerminalBlock_Phoenix:TerminalBlock_Phoenix_MPT-0,5-3-2.54_1x03_P2.54mm_Horizontal", 3),
}

# --- placement, in grid holes from the origin ---------------------------------------------------
# (col, row, rotation_deg). Tune here; everything stays on the grid by construction.
# Left half: SD and the PSRAM group, each DIP two holes from the Pico's left pin row with the
# DIP's SCK/MOSI side facing it. Right half: power in, OLED, PS/2 through the converter, and VGA
# furthest from the PSRAM group. That split is the separation HARDWARE_SCHEMATIC.md asks for.
PLACE = {
    "J_PICO_L": (11, 2, 0),    # Pico pins 1..20, top to bottom
    "J_PICO_R": (18, 2, 0),    # Pico pins 40..21, top to bottom
    "J_SD":     (2, 2, 0),
    "C3":       (2, 9, 0),
    "C1":       (3, 13, 0),
    "U_RAM1":   (6, 13, 0),
    "R1":       (1, 15, 0),
    "R2":       (1, 17, 0),
    "C2":       (3, 19, 0),
    "U_RAM2":   (6, 19, 0),
    "R3":       (1, 21, 0),
    "R4":       (1, 23, 0),
    "TB1":      (24, 2, 0),
    "J_OLED":   (28, 4, 0),
    "J_LVL_LV": (24, 9, 0),
    "J_LVL_HV": (27, 9, 0),
    "J_PS2":    (31, 10, 0),
    "J_VGA":    (24, 16, 0),
}

# No mounting-hole footprints on the protoboard variant: the board already has holes everywhere,
# so which ones become mounting points is an enclosure decision, recorded in STATE.md.
MOUNT = []

# Pico physical pin -> socket pad. Pins 1-20 down the left; 21-40 UP the right, so the right
# socket's pad n (counting from the top) is Pico pin 41-n.
PICO_L = {p: p for p in range(1, 21)}
PICO_R = {41 - n: n for n in range(1, 21)}
PICO_GND = [3, 8, 13, 18, 23, 28, 33, 38]


def mm(v):
    return pcbnew.FromMM(v)


def at(col, row):
    return pcbnew.VECTOR2I(mm(ORIGIN_X + col * GRID), mm(ORIGIN_Y + row * GRID))


def read_csv(name):
    with open(os.path.join(HERE, name)) as fh:
        return list(csv.DictReader(l for l in fh if not l.startswith("#")))


def load_pinmap():
    """Pico physical pin -> net name."""
    pins = {}
    for row in read_csv("pinmap.csv"):
        if not row.get("signal"):
            continue
        try:
            pins[int(row["mcu_pin"])] = row["net"]
        except (ValueError, TypeError):
            pass
    for p in PICO_GND:
        pins.setdefault(p, "GND")
    return pins


def load_modules():
    mods = {}
    for row in read_csv("modules.csv"):
        ref = (row.get("ref") or "").strip()
        if not ref:
            continue
        order = [f.strip() for f in row["pin_order"].split("|") if f.strip()]
        pins = int(row["pins"])
        if len(order) != pins:
            sys.exit("%s: pins=%d but pin_order lists %d functions" % (ref, pins, len(order)))
        if ref not in NETS:
            sys.exit("%s: no NETS entry in gen_proto.py" % ref)
        unknown = [f for f in order if f not in NETS[ref]]
        if unknown:
            sys.exit("%s: pin_order names unknown function(s) %s. Known: %s"
                     % (ref, ", ".join(unknown), ", ".join(sorted(NETS[ref]))))
        mods[ref] = dict(row, order=order, pins=pins)
    return mods


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "carrier_proto.kicad_pcb"))
    args = ap.parse_args()

    pico_nets = load_pinmap()
    mods = load_modules()
    board = pcbnew.BOARD()
    nets = {}

    def net(name):
        if name not in nets:
            n = pcbnew.NETINFO_ITEM(board, name)
            board.Add(n)
            nets[name] = n
        return nets[name]

    def place(ref, fpid, col, row, rot, value=""):
        lib, name = fpid.split(":")
        libdir = (os.path.join(HERE, "carrier.pretty") if lib == "carrier"
                  else os.path.join(FPLIB, lib + ".pretty"))
        fp = pcbnew.FootprintLoad(libdir, name)
        if fp is None:
            sys.exit("could not load footprint %s" % fpid)
        fp.SetReference(ref)
        fp.SetValue(value or ref)
        # Reference only on the silkscreen. Part names collide badly at this density and they are
        # already in modules.csv and BUILD_SHEET.md, keyed by the same reference.
        fp.Value().SetVisible(False)
        board.Add(fp)
        fp.SetPosition(at(col, row))
        if rot:
            fp.SetOrientationDegrees(rot)
        return fp

    def set_pad(fp, ref, pad_no, netname):
        pad = fp.FindPadByNumber(str(pad_no))
        if pad is None:
            sys.exit("%s has no pad %s" % (ref, pad_no))
        if netname:
            pad.SetNet(net(netname))

    # The Pico, as two 1x20 sockets 0.7 in apart -- which is how you actually build it on
    # protoboard, and makes the pin numbering unambiguous.
    unused = []
    for ref, pinmap in (("J_PICO_L", PICO_L), ("J_PICO_R", PICO_R)):
        c, r, rot = PLACE[ref]
        fp = place(ref, "Connector_PinSocket_2.54mm:PinSocket_1x20_P2.54mm_Vertical",
                   c, r, rot, "Pico " + ref[-1])
        for pico_pin, pad_no in pinmap.items():
            netname = pico_nets.get(pico_pin)
            set_pad(fp, ref, pad_no, netname)
            if not netname:
                unused.append(pico_pin)

    # Modules, from modules.csv.
    bodies, offboard = {}, []
    for ref in sorted(mods):
        m = mods[ref]
        if ref not in PLACE:
            sys.exit("%s has no placement in PLACE" % ref)
        c, r, rot = PLACE[ref]
        if ref in FOOTPRINT:
            fpid, want_pins = FOOTPRINT[ref]
            if m["pins"] != want_pins:
                sys.exit("%s: modules.csv says %d pins but its footprint has %d"
                         % (ref, m["pins"], want_pins))
        else:
            fpid = ("Connector_PinSocket_2.54mm:PinSocket_1x%02d_P2.54mm_Vertical" % m["pins"])
        fp = place(ref, fpid, c, r, rot, m["part"][:28])
        for i, func in enumerate(m["order"], start=1):
            set_pad(fp, ref, i, NETS[ref][func])

        # Draw the module's estimated body on F.Fab, so overhang and collisions are visible.
        # body_on_board=no means only the header is here and the module mounts to the enclosure
        # wall on a short cable, so there is no body to fit.
        bw, bh = float(m["body_w"] or 0), float(m["body_h"] or 0)
        if m["body_on_board"].strip().lower() == "no":
            offboard.append(ref)
            bw = bh = 0
        if bw > 0 and bh > 0:
            ox, oy = float(m["body_off_x"] or 0), float(m["body_off_y"] or 0)
            x0 = ORIGIN_X + c * GRID + ox
            y0 = ORIGIN_Y + r * GRID + oy
            body = pcbnew.PCB_SHAPE(board)
            body.SetShape(pcbnew.SHAPE_T_RECT)
            body.SetStart(pcbnew.VECTOR2I(mm(x0), mm(y0)))
            body.SetEnd(pcbnew.VECTOR2I(mm(x0 + bw), mm(y0 + bh)))
            body.SetLayer(pcbnew.F_Fab)
            body.SetWidth(mm(0.12))
            board.Add(body)
            bodies[ref] = [round(x0, 3), round(y0, 3), round(x0 + bw, 3), round(y0 + bh, 3)]

    # The Pico's own outline: 21 x 51 mm (datasheet), centred on its two pin rows.
    pl_c, pl_r, _ = PLACE["J_PICO_L"]
    pico_x = ORIGIN_X + pl_c * GRID + (17.78 - 21.0) / 2.0
    pico_y = ORIGIN_Y + pl_r * GRID - 1.6
    pico_body = pcbnew.PCB_SHAPE(board)
    pico_body.SetShape(pcbnew.SHAPE_T_RECT)
    pico_body.SetStart(pcbnew.VECTOR2I(mm(pico_x), mm(pico_y)))
    pico_body.SetEnd(pcbnew.VECTOR2I(mm(pico_x + 21.0), mm(pico_y + 51.0)))
    pico_body.SetLayer(pcbnew.F_Fab)
    pico_body.SetWidth(mm(0.12))
    board.Add(pico_body)
    bodies["PICO"] = [round(pico_x, 3), round(pico_y, 3),
                      round(pico_x + 21.0, 3), round(pico_y + 51.0, 3)]

    for ref, (fpid, padnets, note) in PASSIVES.items():
        c, r, rot = PLACE[ref]
        fp = place(ref, fpid, c, r, rot, note)
        for i, netname in enumerate(padnets, start=1):
            set_pad(fp, ref, i, netname)

    for i, (c, r) in enumerate(MOUNT, start=1):
        place("H%d" % i, "MountingHole:MountingHole_3.2mm_M3_DIN965", c, r, 0, "M3")

    # Board outline.
    rect = pcbnew.PCB_SHAPE(board)
    rect.SetShape(pcbnew.SHAPE_T_RECT)
    rect.SetStart(pcbnew.VECTOR2I(0, 0))
    rect.SetEnd(pcbnew.VECTOR2I(mm(BOARD_W), mm(BOARD_H)))
    rect.SetLayer(pcbnew.Edge_Cuts)
    rect.SetWidth(mm(0.15))
    board.Add(rect)

    # A protoboard layout is only valid if EVERY pad lands on a hole.
    offgrid = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            px = pcbnew.ToMM(pad.GetPosition().x) - ORIGIN_X
            py = pcbnew.ToMM(pad.GetPosition().y) - ORIGIN_Y
            if any(abs((v / GRID) - round(v / GRID)) > 1e-6 for v in (px, py)):
                offgrid.append("%s.%s at (%.3f, %.3f) mm from the first hole"
                               % (fp.GetReference(), pad.GetNumber(), px, py))
    if offgrid:
        print("OFF-GRID PADS -- these do not land on protoboard holes:")
        for o in offgrid:
            print("  " + o)
        sys.exit(1)

    cols = [pcbnew.ToMM(p.GetPosition().x) - ORIGIN_X
            for f in board.GetFootprints() for p in f.Pads()]
    rows = [pcbnew.ToMM(p.GetPosition().y) - ORIGIN_Y
            for f in board.GetFootprints() for p in f.Pads()]

    import json
    with open(os.path.join(HERE, "bodies.json"), "w") as fh:
        json.dump({"board": [0, 0, BOARD_W, BOARD_H], "bodies": bodies}, fh, indent=2, sort_keys=True)

    pcbnew.SaveBoard(args.out, board)

    by_net = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname():
                by_net.setdefault(pad.GetNetname(), []).append(
                    "%s.%s" % (fp.GetReference(), pad.GetNumber()))
    links = sum(max(0, len(v) - 1) for v in by_net.values())

    print("wrote %s" % args.out)
    print("board %.0f x %.0f mm (%.2f x %.2f in), %d x %d holes; uses cols %.0f-%.0f, rows %.0f-%.0f"
          % (BOARD_W, BOARD_H, BOARD_W / 25.4, BOARD_H / 25.4,
             int(BOARD_W / GRID), int(BOARD_H / GRID),
             min(cols) / GRID, max(cols) / GRID, min(rows) / GRID, max(rows) / GRID))
    print("%d footprints, %d nets, %d wire links to solder"
          % (len(board.GetFootprints()), len(by_net), links))

    if offboard:
        print("off-board (header only, module mounts to the enclosure wall): %s"
              % ", ".join(sorted(offboard)))
    guessed = sorted(r["ref"].strip() for r in mods.values()
                     if r["confidence"].strip() == "GUESSED")
    if guessed:
        print("NOT READY TO BUILD: %d of %d modules still GUESSED in modules.csv (%s)"
              % (len(guessed), len(mods), ", ".join(guessed)))
    else:
        print("all %d modules measured or from datasheet" % len(mods))

    if args.report:
        print("\n--- MODULE CONFIDENCE (measure a row, edit modules.csv, re-run) ---")
        for ref in sorted(mods):
            m = mods[ref]
            print("%-10s %-9s %-36s %s"
                  % (ref, m["confidence"].strip(), m["part"], m["notes"]))
        print("\n--- UNUSED PICO PINS (deliberate) ---")
        print("  " + ", ".join("pin %d" % p for p in sorted(unused)))
        print("\n--- WIRE LIST (%d links) ---" % links)
        for n in sorted(by_net):
            print("%-14s %s" % (n, "  ".join(sorted(by_net[n]))))


if __name__ == "__main__":
    main()
