#ifndef _VT_H
#define _VT_H

// A VT102-style terminal emulator for the VGA text screen: enough of what the kernel's TERM=vt102
// terminfo entry uses for full-screen programs like nano to draw correctly. It has no hardware
// dependencies, so the same file builds on a desktop for testing (define VT_HOST).

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#ifdef VT_HOST
#define TERM_WIDTH 53
#define TERM_HEIGHT 30
#define BLACK 0
#define WHITE 7
typedef unsigned int uint;
extern unsigned char termBuf[TERM_HEIGHT][TERM_WIDTH];
extern uint8_t fgColBuf[TERM_HEIGHT][TERM_WIDTH];
extern uint8_t bgColBuf[TERM_HEIGHT][TERM_WIDTH];
extern uint cr_x, cr_y;
#else
#include "pico/types.h"
#include "../vga/vga.h"
extern volatile uint8_t fgColBuf[TERM_HEIGHT][TERM_WIDTH];
#endif

// Called with bytes the terminal must send back to the program (cursor position reports).
typedef void (*vt_reply_fn)(const char *s);

void vt_init(vt_reply_fn reply);
void vt_putc(unsigned char c);

bool vt_cursor_visible(void);
bool vt_app_cursor_keys(void); // DECCKM: arrows should be sent as ESC O x instead of ESC [ x

#endif
