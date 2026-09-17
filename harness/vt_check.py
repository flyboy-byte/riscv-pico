#!/usr/bin/env python3
"""Check the VGA terminal emulator against pyte, on real captured console output.

usage: vt_check.py CAPTURE...

Builds vt_host from the firmware's vt.c, feeds each capture (raw bytes a program wrote to the
console) to both, and diffs the final 53x30 screens: characters, reverse video, and the cursor.
pyte is the reference; it's the same library desktop_terminal.py uses.
"""
import os, subprocess, sys
import pyte

HERE = os.path.dirname(os.path.abspath(__file__))
TERM_DIR = os.path.join(HERE, "../upstream/pico-rv32ima/pico-rv32ima/console/terminal")
BIN = os.path.join(HERE, "vt_host")
COLS, ROWS = 53, 30


class Screen(pyte.Screen):
    """pyte, with one fix: ESC 8 restores the saved position exactly, as a real VT102 and xterm
    do. pyte clamps it into the scroll region, and nano relies on the real behaviour."""

    def restore_cursor(self):
        origin = bool(self.savepoints) and self.savepoints[-1].origin
        super().restore_cursor()
        if not origin and self.saved_y is not None:
            self.cursor.y = self.saved_y

    def save_cursor(self):
        super().save_cursor()
        self.saved_y = self.cursor.y

    saved_y = None

subprocess.run(["gcc", "-O1", "-Wall", "-DVT_HOST", "-I", TERM_DIR,
                os.path.join(HERE, "vt_host.c"), os.path.join(TERM_DIR, "vt.c"), "-o", BIN],
               check=True)

bad = 0
for path in sys.argv[1:]:
    data = open(path, "rb").read()
    out = subprocess.run([BIN], input=data, capture_output=True, check=True).stdout.decode("latin1")
    lines = out.split("\n")
    ours_text, ours_rev = lines[:ROWS], lines[ROWS:2 * ROWS]
    ours_cursor = tuple(int(v) for v in lines[2 * ROWS].split()[1:])

    screen = Screen(COLS, ROWS)
    stream = pyte.ByteStream(screen)
    stream.feed(data)
    ref_text, ref_rev = [], []
    for y in range(ROWS):
        row = screen.buffer[y]
        ref_text.append("".join(row[x].data if row[x].data.isprintable() and ord(row[x].data) < 128
                                else ("?" if row[x].data.strip() else " ") for x in range(COLS)))
        ref_rev.append("".join("#" if row[x].reverse else "." for x in range(COLS)))
    ref_cursor = (screen.cursor.y, screen.cursor.x)

    diffs = []
    for y in range(ROWS):
        if ours_text[y] != ref_text[y]:
            diffs.append(f"row {y:2} text\n  ours |{ours_text[y]}|\n  pyte |{ref_text[y]}|")
        if ours_rev[y] != ref_rev[y]:
            diffs.append(f"row {y:2} reverse\n  ours |{ours_rev[y]}|\n  pyte |{ref_rev[y]}|")
    # pyte parks the cursor one past the last column where a real VT holds it with a pending wrap
    if ours_cursor != ref_cursor and not (ours_cursor[0] == ref_cursor[0] and ref_cursor[1] == COLS):
        diffs.append(f"cursor ours {ours_cursor} pyte {ref_cursor}")

    name = os.path.basename(path)
    if diffs:
        bad += 1
        print(f"FAIL {name}")
        print("\n".join(diffs))
    else:
        print(f"ok   {name}")
    if os.environ.get("SHOW"):
        print("\n".join("|" + t + "|" for t in ours_text))
sys.exit(1 if bad else 0)
