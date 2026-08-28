#ifndef _SSD1306_H
#define _SSD1306_H

// Minimal SSD1306 (128x64, I2C) driver for the status panel.
//
// Deliberately not a console and not a general graphics library: the only drawing
// primitive is "replace one whole text row". Rows map 1:1 onto the SSD1306's 8-pixel
// pages, and the 5x8 font already in this tree (console/vga/font.h) is stored
// column-major with bit 0 at the top -- which is exactly the SSD1306's page layout, so
// rendering a character is a 5-byte copy with no bit twiddling.
//
// Flushing is incremental (ssd1306_flush_step) because core 0 also runs console_task(),
// and a full 1KB frame at 400 kHz would block it for ~23 ms. One step pushes 64 bytes,
// about 1.6 ms, and only pages whose contents actually changed are pushed at all.

#include <stdbool.h>
#include <stdint.h>

#define OLED_W 128
#define OLED_H 64
#define OLED_PAGES (OLED_H / 8)
#define OLED_CELL_W 6              // 5px glyph + 1px gap
#define OLED_COLS (OLED_W / OLED_CELL_W) // 21 characters per row

// Probes the display. Returns false (and leaves the driver permanently disabled) if
// nothing ACKs, so the firmware behaves identically with no OLED attached.
bool ssd1306_init(void);
bool ssd1306_present(void);

// Replaces the full width of one text row. Clears to the background first, so there is
// no need to pad strings to blank out what was there before. No-op if the rendered row
// is byte-identical to what is already queued, which keeps the flush queue empty when
// nothing changed.
void ssd1306_row(uint8_t row, const char *s, bool inverse);

// Pushes at most one chunk of one dirty page. Cheap and safe to call unconditionally.
void ssd1306_flush_step(void);

#endif
