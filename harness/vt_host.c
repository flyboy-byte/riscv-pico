/* vt_host: run the VGA terminal emulator (console/terminal/vt.c) on the desktop.
 * Reads raw console output on stdin, prints the final 53x30 screen: one line of characters per row,
 * then one line per row marking reverse-video cells (fg/bg swapped from white on black) with '#'.
 * vt_check.py compares this against pyte. Build: see vt_check.py. */
#include <stdio.h>
#include "vt.h"

unsigned char termBuf[TERM_HEIGHT][TERM_WIDTH];
uint8_t fgColBuf[TERM_HEIGHT][TERM_WIDTH];
uint8_t bgColBuf[TERM_HEIGHT][TERM_WIDTH];
uint cr_x, cr_y;

static void reply(const char *s) { fprintf(stderr, "reply %s\n", s + 1); }

int main(void)
{
    int c;
    memset(termBuf, ' ', sizeof(termBuf));
    memset(fgColBuf, WHITE, sizeof(fgColBuf));
    vt_init(reply);
    while ((c = getchar()) != EOF)
        vt_putc((unsigned char)c);
    for (int y = 0; y < TERM_HEIGHT; y++)
    {
        fwrite(termBuf[y], 1, TERM_WIDTH, stdout);
        putchar('\n');
    }
    for (int y = 0; y < TERM_HEIGHT; y++)
    {
        for (int x = 0; x < TERM_WIDTH; x++)
            putchar(bgColBuf[y][x] != BLACK ? '#' : '.');
        putchar('\n');
    }
    printf("cursor %u %u\n", cr_y, cr_x);
    return 0;
}
