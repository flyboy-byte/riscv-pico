# Carrier board: exploration notes (2026-10-28)

Status: **exploration only. Nothing is built, ordered or wired.** This folder holds a rough
fit tool and the notes needed to pick the work up later, next to the real files and hardware.

## Goal

Move the working breadboard circuit onto one soldered board, either a protoboard or a
single-layer custom PCB. The open questions are which board, and whether the parts can be routed on
one layer with short enough traces. `PLAN.md` names a perfboard build as the next direction.

## What is already settled (from the existing docs)

Pins are compiled into firmware, so the layout has to route around them. The tables are in
[HARDWARE_SCHEMATIC.md](../HARDWARE_SCHEMATIC.md) and the README's Wiring section.

| Group | Pico pins | What matters for layout |
| --- | --- | --- |
| SD card (SPI0) | GP0, GP2, GP3, GP4 | MOSI and CLK cross over on the module's header |
| PSRAM x2 (SPI1) | GP10 to GP14 | Most timing-sensitive bus, 20 MHz. On the Pico 3V3 with local decoupling |
| VGA | GP16 to GP20, GND pin 23 | Ground only, no power. Fast PIO pixel clock |
| PS/2 | GP26, GP27 | 5 V bus, through a BSS138 converter. Low side on Pico 3V3, high side on 5 V |
| OLED (I2C0) | GP28, GP21 | Two separate jumpers, no adjacent pair is free |

Power is the lesson from 2026-08-29: SD and OLED run from a separate 3.3 V supply, PSRAM stays on
the Pico's 3V3, and all grounds meet at one point. Sharing one 3V3 node crashed boot.

## Board sizes looked at

- ElectroCookie snappable board: 3.8 x 3.5 in (about 96.5 x 88.9 mm), 0.1 in pitch, snaps into four
  boards. From a retailer listing, so confirm on the part. Power rails are not confirmed there.
- Eurocard, 160 x 100 mm.
- The full ElectroCookie board and the Eurocard fit everything in the fit tool. The half and quarter
  board do not.

## The fit tool

[`fit.html`](fit.html) is a single file. Open it in a browser. It draws the Pico and the other
modules to scale, lets you drag and rotate them, draws every connection from the pinout above, and
counts crossings and trace length per group. "Optimize routing" rearranges the parts to reduce both.

Limits, so nobody over-trusts it:

- Only the Pico's size and pin positions are exact. Sizes and pin positions for the SD, OLED, VGA,
  converter and PSRAM adapters are estimates. The size of the PS/2 screw-terminal breakout is
  unknown.
- Connections are straight lines. A real trace has width and must pass between pins, so zero
  crossings is necessary but not proof.
- The optimizer is a random search. Results from one run vary (roughly 2 to 14 crossings on the full
  board), so press it a few times and keep the best.
- Ground and the separate SD/OLED supply are not drawn.

Real sizes go in the `parts` array near the top of the script, and real pin positions in
`localPin()`.

## Next steps

1. Measure the actual modules (SD, OLED, PSRAM adapters, converter, PS/2 jack or breakout) and put the
   numbers into `fit.html`.
2. Decide protoboard or custom board. On a protoboard there is no router: parts sit on a 0.1 in grid
   and connections are wire or solder bridges. For a custom board, the
   [pcb-design skill in flyboy-byte/toolbox](https://github.com/flyboy-byte/toolbox/tree/master/skills/pcb-design)
   covers generating a KiCad project from code, single-layer autorouting with Freerouting, and a
   design-rule check that reports real crossings and lengths. That would replace the rough numbers here.
3. Whichever route, keep the power split above and put the PSRAM bus as short and tight as the layout allows.
