#!/usr/bin/env python3
"""Generate the protoboard-layout KiCad board from pinmap.csv.

This is the ONE-SIDED PROTOTYPE BOARD draft. It is not a board to order: it is a layout plan for a
hand-wired protoboard, so every part sits on a 2.54 mm (0.1 in) grid and every connection is a wire
link you solder. KiCad is used here because it gives a real netlist, a ratsnest you can look at,
and a DRC -- i.e. it proves the wiring before you cut a single wire.

Run:  python3 gen_proto.py            -> carrier_proto.kicad_pcb
      python3 gen_proto.py --report   -> also prints the build sheet

Nothing here is measured except the Pico. Every module footprint is an ESTIMATE of pin count and
pin order; see ESTIMATES below and confirm each against the real part before building.
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
# HARDWARE_SCHEMATIC.md already names as common hobbyist stock. 35 x 27 holes. The first draft used
# the 96.5 x 88.9 mm ElectroCookie and left the bottom third of the board empty, so this is the
# smaller board the layout actually needs. It is also still under JLCPCB's 100 x 100 mm cheap tier,
# so the same placement migrates to the PCB route without being redone.
BOARD_W, BOARD_H = 90.0, 70.0
ORIGIN_X, ORIGIN_Y = 3.81, 3.81  # 1.5 grid of margin before the first hole

# --- what is known vs guessed -------------------------------------------------------------------
ESTIMATES = """
Pico H                     21 x 51 mm, 2x20 @ 2.54, rows 0.7 in apart   DATASHEET  (the only one)
PSRAM on DIP-8 adapter     DIP-8 0.3 in, APS6404L SOP-8 pinout          DATASHEET pinout / GUESSED adapter
SD breakout                6 pins, order CS SCK MOSI MISO VCC GND       GUESSED -- order varies by module!
SSD1306 OLED               4 pins, order GND VCC SCL SDA                GUESSED -- some are VCC GND
BSS138 converter           2 x 6 pins, LV/LV1-4/GND and HV/HV1-4/GND    GUESSED
Serial Wombat PCB_0024 VGA 6 pins (PLAN.md says "six jumpers")           INFERRED from PLAN.md
PS/2 breakout              4 pins, DATA CLK +5V GND                     GUESSED -- size unknown
"""

# --- the schematic, as a table ------------------------------------------------------------------
# Each module: (ref, footprint, [net per pad, in pad order], silkscreen note)
# Pad order is the module's own header order, which is what ESTIMATES flags as guessed.
MODULES = {
    "J_SD": ("Connector_PinSocket_2.54mm:PinSocket_1x06_P2.54mm_Vertical",
             ["SD_CS", "SD_SCK", "SD_MOSI", "SD_MISO", "+3V3_EXT", "GND"],
             "SD  CS SCK MOSI MISO V G"),
    "J_OLED": ("Connector_PinSocket_2.54mm:PinSocket_1x04_P2.54mm_Vertical",
               ["GND", "+3V3_EXT", "OLED_SCL", "OLED_SDA"],
               "OLED  G V SCL SDA"),
    # APS6404L / LY68L6400 SOP-8: 1 CE# 2 SO(SIO1) 3 SIO2 4 VSS 5 SI(SIO0) 6 SCLK 7 SIO3 8 VCC
    "U_RAM1": ("Package_DIP:DIP-8_W7.62mm_Socket",
               ["PSRAM_CS1", "PSRAM_MISO", "RAM1_WP", "GND",
                "PSRAM_MOSI", "PSRAM_SCK", "RAM1_HOLD", "+3V3_PICO"],
               "PSRAM 1"),
    "U_RAM2": ("Package_DIP:DIP-8_W7.62mm_Socket",
               ["PSRAM_CS2", "PSRAM_MISO", "RAM2_WP", "GND",
                "PSRAM_MOSI", "PSRAM_SCK", "RAM2_HOLD", "+3V3_PICO"],
               "PSRAM 2"),
    "J_LVL_LV": ("Connector_PinSocket_2.54mm:PinSocket_1x06_P2.54mm_Vertical",
                 ["+3V3_EXT", "PS2_DATA_LV", "PS2_CK_LV", "NC_LV3", "NC_LV4", "GND"],
                 "BSS138 LV"),
    "J_LVL_HV": ("Connector_PinSocket_2.54mm:PinSocket_1x06_P2.54mm_Vertical",
                 ["+5V_EXT", "PS2_DATA_HV", "PS2_CK_HV", "NC_HV3", "NC_HV4", "GND"],
                 "BSS138 HV"),
    "J_PS2": ("Connector_PinSocket_2.54mm:PinSocket_1x04_P2.54mm_Vertical",
              ["PS2_DATA_HV", "PS2_CK_HV", "+5V_EXT", "GND"],
              "PS/2  D CLK 5V G"),
    "J_VGA": ("Connector_PinSocket_2.54mm:PinSocket_1x06_P2.54mm_Vertical",
              ["VGA_VSYNC", "VGA_HSYNC", "VGA_R", "VGA_G", "VGA_B", "GND"],
              "VGA  VS HS R G B GND"),
    "TB1": ("TerminalBlock_Phoenix:TerminalBlock_Phoenix_MPT-0,5-3-2.54_1x03_P2.54mm_Horizontal",
            ["+5V_EXT", "+3V3_EXT", "GND"],
            "PWR IN  5V 3V3 GND"),
    # Decoupling. Through-hole so it solders with an iron.
    # KiCad's own THT capacitor footprints are ALL off the 2.54 mm grid (5.00 mm pitch and the
    # like), which would put a pad between protoboard holes. carrier.pretty holds on-grid ones.
    "C1": ("carrier:C_THT_P2.54mm", ["+3V3_PICO", "GND"], "100n RAM1"),
    "C2": ("carrier:C_THT_P2.54mm", ["+3V3_PICO", "GND"], "100n RAM2"),
    "C3": ("carrier:C_THT_P5.08mm", ["+3V3_EXT", "GND"], "10u bulk"),
    # WP/HOLD pull-ups. HARDWARE_SCHEMATIC.md: pins 3 and 7 on BOTH chips need pulling to VCC.
    "R1": ("Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
           ["RAM1_WP", "+3V3_PICO"], "10k"),
    "R2": ("Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
           ["RAM1_HOLD", "+3V3_PICO"], "10k"),
    "R3": ("Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
           ["RAM2_WP", "+3V3_PICO"], "10k"),
    "R4": ("Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
           ["RAM2_HOLD", "+3V3_PICO"], "10k"),
}

# --- placement, in grid holes from the origin ---------------------------------------------------
# (col, row, rotation_deg). Tune here; everything stays on the grid by construction.
# Left half of the board carries SD + PSRAM (Pico pins 1-20); right half carries VGA, OLED, PS/2
# and power (pins 21-40). That split is not cosmetic: it is what keeps the PSRAM group away from
# the VGA group, which HARDWARE_SCHEMATIC.md asks for explicitly.
PLACE = {
    "J_PICO_L": (11, 2, 0),    # Pico pins 1..20, top to bottom
    "J_PICO_R": (18, 2, 0),    # Pico pins 40..21, top to bottom
    # Left: SD and the PSRAM group. PSRAM sits two holes from the Pico's left pin row, with the
    # DIP's SCK/MOSI side (pads 5-8) facing it, so the critical group is as short as the grid allows.
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
    # Right: power in, then OLED, PS/2 through the converter, and VGA furthest from the PSRAM group.
    "TB1":      (24, 2, 0),
    "J_OLED":   (28, 4, 0),
    "J_LVL_LV": (24, 9, 0),
    "J_LVL_HV": (27, 9, 0),
    "J_PS2":    (31, 10, 0),
    "J_VGA":    (24, 16, 0),
}

# No mounting-hole footprints on the protoboard variant: the board already has holes everywhere,
# so which ones become the mounting points is a decision for the enclosure, recorded in STATE.md.
# The PCB variant will need real MountingHole footprints in the corners.
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


def load_pinmap():
    """Pico physical pin -> net name, from pinmap.csv."""
    pins, rows = {}, []
    with open(os.path.join(HERE, "pinmap.csv")) as fh:
        for row in csv.DictReader(l for l in fh if not l.startswith("#")):
            if not row.get("signal"):
                continue
            rows.append(row)
            try:
                pins[int(row["mcu_pin"])] = row["net"]
            except (ValueError, TypeError):
                pass
    for p in PICO_GND:
        pins.setdefault(p, "GND")
    return pins, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "carrier_proto.kicad_pcb"))
    args = ap.parse_args()

    pico_nets, pinmap_rows = load_pinmap()
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
        if ref[0] in "RC":
            fp.Value().SetVisible(False)
        board.Add(fp)
        fp.SetPosition(at(col, row))
        if rot:
            fp.SetOrientationDegrees(rot)
        return fp

    # The Pico, as two 1x20 sockets 0.7 in apart -- which is how you actually build it on
    # protoboard, and makes the pin numbering unambiguous.
    unrouted = []
    for ref, pinmap, (c, r, rot) in (
        ("J_PICO_L", PICO_L, PLACE["J_PICO_L"]),
        ("J_PICO_R", PICO_R, PLACE["J_PICO_R"]),
    ):
        fp = place(ref, "Connector_PinSocket_2.54mm:PinSocket_1x20_P2.54mm_Vertical",
                   c, r, rot, "Pico " + ref[-1])
        for pico_pin, pad_no in pinmap.items():
            netname = pico_nets.get(pico_pin)
            pad = fp.FindPadByNumber(str(pad_no))
            if pad is None:
                sys.exit("%s has no pad %s" % (ref, pad_no))
            if netname:
                pad.SetNet(net(netname))
            else:
                unrouted.append("Pico pin %d" % pico_pin)

    # Everything else.
    for ref, (fpid, padnets, note) in MODULES.items():
        if ref not in PLACE:
            sys.exit("%s has no placement" % ref)
        c, r, rot = PLACE[ref]
        fp = place(ref, fpid, c, r, rot, note)
        for i, netname in enumerate(padnets, start=1):
            pad = fp.FindPadByNumber(str(i))
            if pad is None:
                sys.exit("%s has no pad %d (footprint %s)" % (ref, i, fpid))
            if not netname.startswith("NC_"):
                pad.SetNet(net(netname))

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

    # A protoboard layout is only valid if EVERY pad lands on a hole. Check it, don't assume it.
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

    cols = [pcbnew.ToMM(pad.GetPosition().x) - ORIGIN_X
            for fp in board.GetFootprints() for pad in fp.Pads()]
    rows = [pcbnew.ToMM(pad.GetPosition().y) - ORIGIN_Y
            for fp in board.GetFootprints() for pad in fp.Pads()]
    print("holes used: cols %.0f..%.0f of %d, rows %.0f..%.0f of %d"
          % (min(cols) / GRID, max(cols) / GRID, int(BOARD_W / GRID),
             min(rows) / GRID, max(rows) / GRID, int(BOARD_H / GRID)))

    pcbnew.SaveBoard(args.out, board)

    # Report.
    by_net = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname():
                by_net.setdefault(pad.GetNetname(), []).append(
                    "%s.%s" % (fp.GetReference(), pad.GetNumber()))
    links = sum(max(0, len(v) - 1) for v in by_net.values())
    print("wrote %s" % args.out)
    print("%d footprints, %d nets, %d wire links to solder"
          % (len(board.GetFootprints()), len(by_net), links))
    if unrouted:
        print("unconnected Pico pins: %s" % ", ".join(unrouted))

    if args.report:
        print("\n--- ESTIMATES (confirm before building) ---" + ESTIMATES)
        print("--- WIRE LIST (%d links) ---" % links)
        for n in sorted(by_net):
            pads = by_net[n]
            print("%-14s %s" % (n, "  ".join(sorted(pads))))


if __name__ == "__main__":
    main()
