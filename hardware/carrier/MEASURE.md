# Measure the modules — the one thing blocking this board

**This is where you pick the project up.** Everything else is done and checked. Six modules are still
guessed, and a guess is why `gen_proto.py` prints `NOT READY TO BUILD`.

You need calipers (or a steel rule and patience) and about an hour. For each module below, fill in
its row in [`modules.csv`](modules.csv), change its `confidence` to `MEASURED`, then:

```sh
cd hardware/carrier
python3 gen_proto.py --report     # rebuilds the layout and the wire list
python3 checks/run_all.py         # grid, bodies, firmware pinmap, DRC
```

If a body now collides, `checks/body_check.py` fails and names the two parts and by how much. That
is the system working — fix the placement in `gen_proto.py`'s `PLACE` table and re-run.

---

## What to measure, per module

Five numbers and one list. The list matters most.

| Field in `modules.csv` | What it is | How to get it |
| --- | --- | --- |
| `pin_order` | **The functions in header order, pin 1 first.** | Read the silkscreen. This is the one that makes a board scrap if it's wrong. |
| `pins` | How many pins on the header | Count them |
| `body_w`, `body_h` | The module's outline in mm | Calipers across the PCB, not the header |
| `body_off_x`, `body_off_y` | Where the body's top-left corner sits relative to header pin 1, in mm | Negative means the body starts left of / above pin 1 |
| `body_on_board` | `yes` if the module sits on the board, `no` if only its header is here | See the note below |

**Finding pin 1.** On a breakout it is usually the end marked with a square pad, a dot, a `1`, or
the first label on the silkscreen. Write down which physical end you called pin 1, because
`pin_order` is meaningless without it.

---

## The six that need measuring

### `J_SD` — microSD SPI breakout — **highest risk**
Currently guessed as `CS|SCK|MOSI|MISO|VCC|GND`. **Pin order on these varies wildly between
modules** — plenty are the exact reverse, `GND|VCC|MISO|MOSI|SCK|CS`. Get this wrong and you wire
MOSI to CS. Read the silkscreen and copy it left to right from your pin 1.

Also check whether yours is a 6-pin or 8-pin module, and whether its `VCC` wants 5 V or 3.3 V —
some have an onboard regulator and want 5 V, others are bare 3.3 V. The draft assumes **3.3 V**
from the external rail.

### `J_VGA` — Serial Wombat PCB_0024
Pin count is inferred from PLAN.md's phrase "six jumpers from its…", not from a datasheet. Confirm
there are six, and confirm the order. The series resistors (3 × 270 Ω, 2 × 68 Ω) **stay on this
breakout** — do not move them to the carrier.

### `J_PS2` — PS/2 socket breakout — **size completely unknown**
The 30 × 30 mm in `modules.csv` is a placeholder, not an estimate. Measure the real thing.

### `J_OLED` — SSD1306 128×64
Guessed as `GND|VCC|SCL|SDA`. Many of these are `VCC|GND|SCL|SDA` instead, which would short your
3.3 V rail to ground on first power-up. Worth being certain about.

### `J_LVL_LV` / `J_LVL_HV` — BSS138 4-channel converter
Two 6-pin headers, guessed as `LV|LV1..LV4|GND` and `HV|HV1..HV4|GND`. Confirm the order and which
side is which. The body is recorded once, on the `J_LVL_LV` row, because it spans both headers.

### Already fine, don't re-measure
`U_RAM1` / `U_RAM2` (SOP-8 pinout is from the APS6404L datasheet) and `TB1` (standard on-grid
terminal footprint). The Pico is from its datasheet: 21 × 51 mm, 0.7 in between pin rows.

---

## While you have it apart, two decisions to make

**1. Which modules actually sit on the board?** The draft says SD, VGA, PS/2 and the OLED are
`body_on_board = no`: only their headers are on the carrier, and the modules themselves mount to the
enclosure wall on a short cable. The reasoning is that all four are things you touch or look at — a
card slot, two panel connectors and a display — so they belong on a wall, and `checks/body_check.py`
proved the point: with all four on-board, the bodies collide in 7 places and the SD breakout alone
overlaps the Pico by 18 × 23 mm.

That is a default I picked, not something you agreed to. Flip any row to `yes` and re-run to see
what it costs.

**2. Where does the BSS138's LV reference come from?** The draft takes it from the external 3.3 V
rail, so that Pico pin 36 stays dedicated to PSRAM VCC and its pull-ups. But a level converter's LV
reference should really match the logic it is translating, which is the Pico's own I/O rail, and the
converter draws microamps so it would not meaningfully load pin 36. I took the conservative reading
of the "pin 36 is PSRAM only" rule. You may want the other one.

---

## Then what

Once every row says `MEASURED` or `DATASHEET` and all checks pass, the protoboard is buildable:
`BUILD_SHEET.md` has the wire list, 61 links. The PCB route stays available from the same
`pinmap.csv` and `modules.csv` if you ever want the ordered 2-layer board with a real ground plane —
see `STATE.md` for why that is the one with the better electrical argument.
