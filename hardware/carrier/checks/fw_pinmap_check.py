#!/usr/bin/env python3
"""pinmap.csv must agree with the firmware's hw_config.h.

Every pin on this board is compiled into firmware. If someone edits hw_config.h and the board is
already built, the board is wrong and nothing else in this project will notice -- the layout, the
build sheet and the wire list would all still be self-consistent. So this check reads the firmware
header directly and compares it against pinmap.csv's fw_pin column.

One result line, exit 0/1.
"""

import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
HW_CONFIG = os.path.normpath(os.path.join(
    PROJ, "..", "..", "upstream", "pico-rv32ima", "pico-rv32ima", "hw_config.h"))

# firmware #define -> the signal name pinmap.csv uses
EXPECT = {
    "SD_SPI_PIN_CS": "SD_CS",
    "SD_SPI_PIN_CK": "SD_SCK",
    "SD_SPI_PIN_TX": "SD_MOSI",
    "SD_SPI_PIN_RX": "SD_MISO",
    "PSRAM_SPI_PIN_CK": "PSRAM_SCK",
    "PSRAM_SPI_PIN_TX": "PSRAM_MOSI",
    "PSRAM_SPI_PIN_RX": "PSRAM_MISO",
    "PSRAM_SPI_PIN_S1": "PSRAM_CS1",
    "PSRAM_SPI_PIN_S2": "PSRAM_CS2",
    "VGA_VSYNC_PIN": "VGA_VSYNC",
    "VGA_HSYNC_PIN": "VGA_HSYNC",
    "VGA_R_PIN": "VGA_R",
    "PS2_PIN_DATA": "PS2_DATA",
    "PS2_PIN_CK": "PS2_CK",
    "OLED_I2C_PIN_SDA": "OLED_SDA",
    "OLED_I2C_PIN_SCL": "OLED_SCL",
}
# VGA green and blue are not #defined: the PIO program takes them as VGA_R_PIN + 1 and + 2.
DERIVED = {"VGA_G": ("VGA_R_PIN", 1), "VGA_B": ("VGA_R_PIN", 2)}


def main():
    if not os.path.exists(HW_CONFIG):
        print("SKIPPED firmware pinmap: %s not found" % HW_CONFIG)
        return 0

    text = open(HW_CONFIG).read()
    fw = {}
    for name in list(EXPECT) + ["VGA_R_PIN"]:
        m = re.search(r"^#define\s+%s\s+(\d+)" % re.escape(name), text, re.M)
        if m:
            fw[name] = int(m.group(1))

    want = {}
    for define, signal in EXPECT.items():
        if define in fw:
            want[signal] = fw[define]
    for signal, (base, offset) in DERIVED.items():
        if base in fw:
            want[signal] = fw[base] + offset

    have = {}
    with open(os.path.join(PROJ, "pinmap.csv")) as fh:
        for row in csv.DictReader(l for l in fh if not l.startswith("#")):
            sig, fwpin = row.get("signal"), (row.get("fw_pin") or "").strip()
            if sig and fwpin.startswith("GP"):
                have[sig] = int(fwpin[2:])

    problems = []
    for signal, gpio in sorted(want.items()):
        if signal not in have:
            problems.append("%s is GP%d in hw_config.h but missing from pinmap.csv" % (signal, gpio))
        elif have[signal] != gpio:
            problems.append("%s is GP%d in hw_config.h but GP%d in pinmap.csv"
                            % (signal, gpio, have[signal]))
    for signal, gpio in sorted(have.items()):
        if signal not in want and signal in EXPECT.values():
            problems.append("%s is in pinmap.csv but no longer #defined in hw_config.h" % signal)

    if problems:
        print("FAIL firmware pinmap: %d disagreement(s) with hw_config.h" % len(problems))
        for p in problems:
            print("  " + p)
        return 1
    print("PASS firmware pinmap: %d signals match hw_config.h" % len(want))
    return 0


if __name__ == "__main__":
    sys.exit(main())
