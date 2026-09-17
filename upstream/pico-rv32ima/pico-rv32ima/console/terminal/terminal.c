#include "hw_config.h"
#if CONSOLE_VGA

#include "pico/stdlib.h"
#include <stdlib.h>

#include <string.h>

#include "console.h"
#include "../vga/vga.h"
#include "../ps2/ps2.h"
#include "vt.h"

// Bytes of guest output handled per terminal_task() call, so a big redraw can't starve the
// keyboard and the other console tasks on core 0.
#define TERM_BYTES_PER_TASK 256

queue_t term_screen_queue;

static void send_keys(const char *s)
{
    while (*s)
        queue_try_add(&kb_queue, s++);
}

void terminal_init(void)
{
    PS2_init(PS2_PIN_DATA, PS2_PIN_CK);
    VGA_initDisplay(VGA_VSYNC_PIN, VGA_HSYNC_PIN, VGA_R_PIN);
    VGA_puts("\n\rpico-rv32ima, compiled ");
    VGA_puts(__DATE__);
    VGA_puts("\n\r");
    vt_init(send_keys);
    queue_init(&term_screen_queue, sizeof(char), IO_QUEUE_LEN);
}

// The cursor is drawn by recolouring its cell, so it is taken off before the emulator touches
// the screen and put back afterwards. That way a cell never keeps the cursor's colours.
static struct
{
    bool shown;
    uint x, y;
    uint8_t fg, bg;
} cursor;

static void cursor_hide(void)
{
    if (!cursor.shown)
        return;
    fgColBuf[cursor.y][cursor.x] = cursor.fg;
    bgColBuf[cursor.y][cursor.x] = cursor.bg;
    cursor.shown = false;
}

static void cursor_show(void)
{
    if (cursor.shown || !vt_cursor_visible())
        return;
    cursor.x = cr_x;
    cursor.y = cr_y;
    cursor.fg = fgColBuf[cr_y][cr_x];
    cursor.bg = bgColBuf[cr_y][cr_x];
    fgColBuf[cr_y][cr_x] = BLACK;
    bgColBuf[cr_y][cr_x] = GREEN;
    cursor.shown = true;
}

static void send_arrow(char a)
{
    char seq[4] = {0x1b, vt_app_cursor_keys() ? 'O' : '[', a, 0};
    send_keys(seq);
}

static void handlePs2Keyboard(void)
{
    while (PS2_keyAvailable())
    {
        uint16_t key = PS2_readKey();
        bool ctrl = key & 0x100;
        uint8_t c = key & 0xFF;

        switch (c)
        {
        case PS2_UPARROW:
            send_arrow('A');
            break;
        case PS2_DOWNARROW:
            send_arrow('B');
            break;
        case PS2_RIGHTARROW:
            send_arrow('C');
            break;
        case PS2_LEFTARROW:
            send_arrow('D');
            break;
        case PS2_HOME:
            send_keys("\x1b[1~");
            break;
        case PS2_INSERT:
            send_keys("\x1b[2~");
            break;
        case PS2_DELETE:
            send_keys("\x1b[3~");
            break;
        case PS2_END:
            send_keys("\x1b[4~");
            break;
        case PS2_PAGEUP:
            send_keys("\x1b[5~");
            break;
        case PS2_PAGEDOWN:
            send_keys("\x1b[6~");
            break;
        case PS2_SHIFT_TAB:
            send_keys("\x1b[Z");
            break;
        case 0:
            break;
        default:
            if (ctrl)
            {
                // Ctrl+letter and Ctrl+[ \ ] ^ _ are the control codes 1-31
                if (c >= 'a' && c <= 'z')
                    c -= 'a' - 1;
                else if (c >= '@' && c <= '_')
                    c -= '@';
                else if (c == ' ')
                    c = 0;
            }
            queue_try_add(&kb_queue, &c);
            break;
        }
    }
}

void terminal_task(void)
{
    static uint32_t blink_ms = 0;
    static bool blink_on = true;
    char c;

    if (!queue_is_empty(&term_screen_queue))
    {
        cursor_hide();
        for (int i = 0; i < TERM_BYTES_PER_TASK && queue_try_remove(&term_screen_queue, &c); i++)
            vt_putc((unsigned char)c);
        blink_on = true; // keep the cursor solid while output is arriving
        blink_ms = to_ms_since_boot(get_absolute_time());
        cursor_show();
    }

    handlePs2Keyboard();

    uint32_t now = to_ms_since_boot(get_absolute_time());
    if (now - blink_ms > 400)
    {
        blink_ms = now;
        blink_on = !blink_on;
        if (blink_on)
            cursor_show();
        else
            cursor_hide();
    }
}

#endif
