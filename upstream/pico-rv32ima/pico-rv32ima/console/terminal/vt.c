// VT102-style terminal emulator for the VGA text screen. See vt.h.
//
// The screen is termBuf/fgColBuf/bgColBuf from vga.c, TERM_WIDTH x TERM_HEIGHT cells. Output
// bytes are fed in one at a time through a small state machine, so a sequence split across
// calls is fine and nothing ever blocks waiting for the rest of one.

#ifndef VT_HOST
#include "hw_config.h"
#endif
#if defined(VT_HOST) || CONSOLE_VGA

#include "vt.h"

#define W TERM_WIDTH
#define H TERM_HEIGHT
#define MAX_PARAMS 16

enum
{
    ST_GROUND,
    ST_ESC,
    ST_ESC_SKIP, // ESC ( B and friends: one more byte to swallow
    ST_CSI,
    ST_STRING, // OSC/DCS/PM/APC: ignored until BEL or ESC \ .
    ST_STRING_ESC,
};

static struct
{
    int state;
    uint params[MAX_PARAMS];
    int nparams;
    bool have_digit;
    bool private_mode; // CSI ? ...
    bool other_prefix; // CSI > ... or CSI = ... : parsed and ignored

    bool wrap_pending; // the last write filled the last column; wrap on the next printable byte
    int top, bot;      // scroll region, inclusive rows
    uint8_t fg, bg;    // SGR colours
    bool reverse;
    bool insert_mode;
    bool autowrap;
    bool origin_mode;
    bool app_cursor;
    bool cursor_visible;

    uint save_x, save_y;
    uint8_t save_fg, save_bg;
    bool save_reverse, save_origin;

    vt_reply_fn reply;
} vt;

static uint8_t cur_fg(void) { return vt.reverse ? vt.bg : vt.fg; }
static uint8_t cur_bg(void) { return vt.reverse ? vt.fg : vt.bg; }

static void clear_cells(int y, int x0, int x1)
{
    for (int x = x0; x < x1; x++)
    {
        termBuf[y][x] = ' ';
        fgColBuf[y][x] = vt.fg;
        bgColBuf[y][x] = vt.bg;
    }
}

static void copy_row(int to, int from)
{
    memcpy((void *)termBuf[to], (void *)termBuf[from], W);
    memcpy((void *)fgColBuf[to], (void *)fgColBuf[from], W);
    memcpy((void *)bgColBuf[to], (void *)bgColBuf[from], W);
}

// Move rows top..bot up by n, blanking the bottom n. Rows outside the region don't move.
static void scroll_up(int top, int bot, int n)
{
    if (n > bot - top + 1)
        n = bot - top + 1;
    for (int y = top; y <= bot - n; y++)
        copy_row(y, y + n);
    for (int y = bot - n + 1; y <= bot; y++)
        clear_cells(y, 0, W);
}

static void scroll_down(int top, int bot, int n)
{
    if (n > bot - top + 1)
        n = bot - top + 1;
    for (int y = bot; y >= top + n; y--)
        copy_row(y, y - n);
    for (int y = top; y < top + n; y++)
        clear_cells(y, 0, W);
}

static void set_cursor(int x, int y)
{
    int minY = 0, maxY = H - 1;
    if (vt.origin_mode)
    {
        y += vt.top;
        minY = vt.top;
        maxY = vt.bot;
    }
    if (x < 0)
        x = 0;
    if (x > W - 1)
        x = W - 1;
    if (y < minY)
        y = minY;
    if (y > maxY)
        y = maxY;
    cr_x = x;
    cr_y = y;
    vt.wrap_pending = false;
}

static void linefeed(void)
{
    if ((int)cr_y == vt.bot)
        scroll_up(vt.top, vt.bot, 1);
    else if (cr_y < H - 1)
        cr_y++;
}

static void reverse_index(void)
{
    if ((int)cr_y == vt.top)
        scroll_down(vt.top, vt.bot, 1);
    else if (cr_y > 0)
        cr_y--;
}

static void put_glyph(unsigned char c)
{
    if (vt.wrap_pending && vt.autowrap)
    {
        cr_x = 0;
        linefeed();
    }
    vt.wrap_pending = false;

    if (vt.insert_mode)
        for (int x = W - 1; x > (int)cr_x; x--)
        {
            termBuf[cr_y][x] = termBuf[cr_y][x - 1];
            fgColBuf[cr_y][x] = fgColBuf[cr_y][x - 1];
            bgColBuf[cr_y][x] = bgColBuf[cr_y][x - 1];
        }

    termBuf[cr_y][cr_x] = c;
    fgColBuf[cr_y][cr_x] = cur_fg();
    bgColBuf[cr_y][cr_x] = cur_bg();

    if (cr_x < W - 1)
        cr_x++;
    else if (vt.autowrap)
        vt.wrap_pending = true;
}

static void save_cursor(void)
{
    vt.save_x = cr_x;
    vt.save_y = cr_y;
    vt.save_fg = vt.fg;
    vt.save_bg = vt.bg;
    vt.save_reverse = vt.reverse;
    vt.save_origin = vt.origin_mode;
}

static void restore_cursor(void)
{
    cr_x = vt.save_x;
    cr_y = vt.save_y;
    vt.fg = vt.save_fg;
    vt.bg = vt.save_bg;
    vt.reverse = vt.save_reverse;
    vt.origin_mode = vt.save_origin;
    vt.wrap_pending = false;
}

static void full_reset(void)
{
    vt.fg = WHITE;
    vt.bg = BLACK;
    vt.reverse = false;
    vt.insert_mode = false;
    vt.autowrap = true;
    vt.origin_mode = false;
    vt.app_cursor = false;
    vt.cursor_visible = true;
    vt.top = 0;
    vt.bot = H - 1;
    vt.wrap_pending = false;
    save_cursor();
}

// Parameter i, with 0 or missing meaning `def`.
static int param(int i, int def)
{
    if (i >= vt.nparams || vt.params[i] == 0)
        return def;
    return vt.params[i];
}

static void sgr(void)
{
    if (vt.nparams == 0)
        vt.nparams = 1, vt.params[0] = 0;
    for (int i = 0; i < vt.nparams; i++)
    {
        uint p = vt.params[i];
        if (p == 0)
        {
            vt.fg = WHITE;
            vt.bg = BLACK;
            vt.reverse = false;
        }
        else if (p == 7)
            vt.reverse = true;
        else if (p == 27)
            vt.reverse = false;
        else if (p >= 30 && p <= 37)
            vt.fg = p - 30;
        else if (p == 39)
            vt.fg = WHITE;
        else if (p >= 40 && p <= 47)
            vt.bg = p - 40;
        else if (p == 49)
            vt.bg = BLACK;
        else if (p >= 90 && p <= 97) // bright colours: only eight exist here
            vt.fg = p - 90;
        else if (p >= 100 && p <= 107)
            vt.bg = p - 100;
        else if (p == 38 || p == 48) // 256-colour and RGB: skip their arguments
        {
            if (i + 1 < vt.nparams && vt.params[i + 1] == 5)
                i += 2;
            else if (i + 1 < vt.nparams && vt.params[i + 1] == 2)
                i += 4;
        }
        // bold, dim, underline, blink: no way to show them in this font, so ignored
    }
}

static void set_mode(bool on)
{
    for (int i = 0; i < vt.nparams; i++)
    {
        uint p = vt.params[i];
        if (vt.private_mode)
        {
            if (p == 1)
                vt.app_cursor = on;
            else if (p == 6)
            {
                vt.origin_mode = on;
                set_cursor(0, 0);
            }
            else if (p == 7)
                vt.autowrap = on;
            else if (p == 25)
                vt.cursor_visible = on;
        }
        else if (p == 4)
            vt.insert_mode = on;
    }
}

// Appends n in decimal. snprintf would pull the SDK's floating-point printf into RAM.
static char *put_uint(char *p, uint n)
{
    char tmp[10];
    int len = 0;
    do
        tmp[len++] = '0' + n % 10;
    while ((n /= 10) != 0);
    while (len)
        *p++ = tmp[--len];
    return p;
}

static void reply(const char *s)
{
    if (vt.reply)
        vt.reply(s);
}

static void run_csi(unsigned char final)
{
    int n = param(0, 1);
    int y = cr_y, x = cr_x;
    char buf[24];

    if (vt.other_prefix)
        return;

    switch (final)
    {
    case 'A': // cursor up, stopping at the top margin if inside the region
    {
        int limit = (y >= vt.top) ? vt.top : 0;
        y -= n;
        if (y < limit)
            y = limit;
        cr_y = y;
        vt.wrap_pending = false;
        break;
    }
    case 'B':
    case 'e':
    {
        int limit = (y <= vt.bot) ? vt.bot : H - 1;
        y += n;
        if (y > limit)
            y = limit;
        cr_y = y;
        vt.wrap_pending = false;
        break;
    }
    case 'C':
    case 'a':
        x += n;
        cr_x = x > W - 1 ? W - 1 : x;
        vt.wrap_pending = false;
        break;
    case 'D':
        x -= n;
        cr_x = x < 0 ? 0 : x;
        vt.wrap_pending = false;
        break;
    case 'E':
        cr_x = 0;
        run_csi('B');
        break;
    case 'F':
        cr_x = 0;
        run_csi('A');
        break;
    case 'G':
    case '`':
        cr_x = n - 1 > W - 1 ? W - 1 : n - 1;
        vt.wrap_pending = false;
        break;
    case 'd':
        set_cursor(cr_x, n - 1);
        break;
    case 'H':
    case 'f':
        set_cursor(param(1, 1) - 1, param(0, 1) - 1);
        break;
    case 'J':
        switch (param(0, 0))
        {
        case 0:
            clear_cells(y, x, W);
            for (int r = y + 1; r < H; r++)
                clear_cells(r, 0, W);
            break;
        case 1:
            for (int r = 0; r < y; r++)
                clear_cells(r, 0, W);
            clear_cells(y, 0, x + 1);
            break;
        case 2:
        case 3:
            for (int r = 0; r < H; r++)
                clear_cells(r, 0, W);
            break;
        }
        vt.wrap_pending = false;
        break;
    case 'K':
        switch (param(0, 0))
        {
        case 0:
            clear_cells(y, x, W);
            break;
        case 1:
            clear_cells(y, 0, x + 1);
            break;
        case 2:
            clear_cells(y, 0, W);
            break;
        }
        vt.wrap_pending = false;
        break;
    case 'L': // insert lines: only inside the scroll region
        if (y >= vt.top && y <= vt.bot)
        {
            scroll_down(y, vt.bot, n);
            cr_x = 0;
        }
        vt.wrap_pending = false;
        break;
    case 'M':
        if (y >= vt.top && y <= vt.bot)
        {
            scroll_up(y, vt.bot, n);
            cr_x = 0;
        }
        vt.wrap_pending = false;
        break;
    case 'P': // delete characters, pulling the rest of the line left
        if (n > W - x)
            n = W - x;
        for (int i = x; i < W - n; i++)
        {
            termBuf[y][i] = termBuf[y][i + n];
            fgColBuf[y][i] = fgColBuf[y][i + n];
            bgColBuf[y][i] = bgColBuf[y][i + n];
        }
        clear_cells(y, W - n, W);
        vt.wrap_pending = false;
        break;
    case '@':
        if (n > W - x)
            n = W - x;
        for (int i = W - 1; i >= x + n; i--)
        {
            termBuf[y][i] = termBuf[y][i - n];
            fgColBuf[y][i] = fgColBuf[y][i - n];
            bgColBuf[y][i] = bgColBuf[y][i - n];
        }
        clear_cells(y, x, x + n);
        vt.wrap_pending = false;
        break;
    case 'X':
        clear_cells(y, x, x + n > W ? W : x + n);
        vt.wrap_pending = false;
        break;
    case 'S':
        scroll_up(vt.top, vt.bot, n);
        break;
    case 'T':
        scroll_down(vt.top, vt.bot, n);
        break;
    case 'r':
    {
        int t = param(0, 1) - 1;
        int b = param(1, H) - 1;
        if (b > H - 1)
            b = H - 1;
        if (t < b)
        {
            vt.top = t;
            vt.bot = b;
            set_cursor(0, 0);
        }
        break;
    }
    case 'm':
        sgr();
        break;
    case 'h':
        set_mode(true);
        break;
    case 'l':
        set_mode(false);
        break;
    case 's':
        save_cursor();
        break;
    case 'u':
        restore_cursor();
        break;
    case 'n':
        if (vt.private_mode)
            break;
        if (param(0, 0) == 5)
            reply("\x1b[0n");
        else if (param(0, 0) == 6)
        {
            int ry = cr_y + 1 - (vt.origin_mode ? vt.top : 0);
            char *p = buf;
            *p++ = 0x1b;
            *p++ = '[';
            p = put_uint(p, ry);
            *p++ = ';';
            p = put_uint(p, cr_x + 1);
            *p++ = 'R';
            *p = 0;
            reply(buf);
        }
        break;
    case 'c':
        if (!vt.private_mode && param(0, 0) == 0)
            reply("\x1b[?6c");
        break;
    default:
        break; // tab stops, printer control and the rest: ignored, and never printed
    }
}

static void esc_final(unsigned char c)
{
    vt.state = ST_GROUND;
    switch (c)
    {
    case '[':
        vt.state = ST_CSI;
        vt.nparams = 0;
        vt.have_digit = false;
        vt.private_mode = false;
        vt.other_prefix = false;
        memset(vt.params, 0, sizeof(vt.params));
        break;
    case ']':
    case 'P':
    case 'X':
    case '^':
    case '_':
        vt.state = ST_STRING;
        break;
    case '(':
    case ')':
    case '*':
    case '+':
    case '#':
    case '%':
        vt.state = ST_ESC_SKIP;
        break;
    case '7':
        save_cursor();
        break;
    case '8':
        restore_cursor();
        break;
    case 'D':
        linefeed();
        break;
    case 'E':
        cr_x = 0;
        linefeed();
        break;
    case 'M':
        reverse_index();
        vt.wrap_pending = false;
        break;
    case 'c':
        full_reset();
        for (int r = 0; r < H; r++)
            clear_cells(r, 0, W);
        set_cursor(0, 0);
        break;
    case 'Z':
        reply("\x1b[?6c");
        break;
    default:
        break; // ESC = , ESC > (keypad modes), ESC H (tab set): nothing to do
    }
}

void vt_putc(unsigned char c)
{
    // CAN and SUB abort a sequence; ESC starts a new one from anywhere
    if (c == 0x18 || c == 0x1a)
    {
        vt.state = ST_GROUND;
        return;
    }
    if (c == 0x1b)
    {
        vt.state = (vt.state == ST_STRING) ? ST_STRING_ESC : ST_ESC;
        return;
    }

    switch (vt.state)
    {
    case ST_STRING:
        if (c == 0x07)
            vt.state = ST_GROUND;
        return;
    case ST_STRING_ESC:
        vt.state = (c == '\\') ? ST_GROUND : ST_STRING;
        return;
    case ST_ESC:
        esc_final(c);
        return;
    case ST_ESC_SKIP:
        vt.state = ST_GROUND;
        return;
    default:
        break;
    }

    // C0 controls act immediately, even in the middle of a CSI sequence
    if (c < 0x20 || c == 0x7f)
    {
        switch (c)
        {
        case '\r':
            cr_x = 0;
            vt.wrap_pending = false;
            break;
        case '\n':
        case 0x0b:
        case 0x0c:
            linefeed();
            break;
        case '\b':
            if (cr_x > 0)
                cr_x--;
            vt.wrap_pending = false;
            break;
        case '\t':
            cr_x = (cr_x / 8 + 1) * 8;
            if (cr_x > W - 1)
                cr_x = W - 1;
            break;
        default:
            break; // BEL, SO/SI (charset switching) and DEL
        }
        return;
    }

    if (vt.state == ST_CSI)
    {
        if (c >= '0' && c <= '9')
        {
            if (vt.nparams == 0)
                vt.nparams = 1;
            if (vt.nparams <= MAX_PARAMS)
                vt.params[vt.nparams - 1] = vt.params[vt.nparams - 1] * 10 + (c - '0');
        }
        else if (c == ';' || c == ':')
        {
            if (vt.nparams == 0)
                vt.nparams = 1;
            if (vt.nparams < MAX_PARAMS)
                vt.nparams++;
        }
        else if (c == '?')
            vt.private_mode = true;
        else if (c == '>' || c == '=' || c == '<')
            vt.other_prefix = true;
        else if (c >= 0x20 && c <= 0x2f)
            vt.other_prefix = true; // intermediate bytes (CSI ! p and similar): not supported
        else if (c >= 0x40 && c <= 0x7e)
        {
            if (vt.nparams > MAX_PARAMS)
                vt.nparams = MAX_PARAMS;
            vt.state = ST_GROUND;
            run_csi(c);
        }
        else
            vt.state = ST_GROUND; // malformed: drop it rather than print it
        return;
    }

    // Printable. The font covers 0x20-0x7e; anything above is UTF-8 or Latin-1 that can't be drawn.
    // Continuation bytes are dropped so one wide character shows as one '?'.
    if (c >= 0x80 && c < 0xc0)
        return;
    if (c >= 0x80)
        c = '?';
    put_glyph(c);
}

void vt_init(vt_reply_fn reply_fn)
{
    memset(&vt, 0, sizeof(vt));
    vt.reply = reply_fn;
    full_reset();
}

bool vt_cursor_visible(void) { return vt.cursor_visible; }
bool vt_app_cursor_keys(void) { return vt.app_cursor; }

#endif
