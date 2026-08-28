#ifndef _STATUS_PANEL_H
#define _STATUS_PANEL_H

// At-a-glance stats on the SSD1306: RAM/PSRAM config, boot stage, live instructions per
// second, and uptime. Runs entirely on core 0, which otherwise does nothing but pump
// console_task(), so the emulator on core 1 pays nothing for it.
//
// Not a console. 128x64 with a 6x8 cell is a 21x8 grid, and an 80-column kernel message
// wraps to four lines of it -- about two messages visible at a time. USB-CDC (and, once
// wired, VGA) remain the console.

void status_panel_init(void);
void status_panel_task(void);

#endif
