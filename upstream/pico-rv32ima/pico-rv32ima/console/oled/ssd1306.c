#include "pico/stdlib.h"

#include <string.h>

#include "hw_config.h"
#include "ssd1306.h"

#if CONSOLE_OLED

#include "hardware/i2c.h"
#include "vga/font.h" // 5x8 column-major glyphs, already in the tree for the VGA console

#define CHUNK 64 // bytes of framebuffer pushed per flush step
#define CHUNKS_PER_PAGE (OLED_W / CHUNK)

// Give up on the display after this many consecutive I2C failures rather than paying the
// timeout on every console_task() forever. A single glitch is not fatal; a yanked wire is.
#define OLED_MAX_ERRS 16

// Long enough for the 65-byte data write at 400 kHz (~1.5 ms) with generous margin, but
// short enough that a missing display costs one brief stall at init and nothing after.
#define OLED_I2C_TIMEOUT_US 8000

static uint8_t fb[OLED_PAGES][OLED_W];
static uint8_t dirty;     // one bit per page
static uint8_t chunk_idx; // which chunk of the current dirty page is next
static bool present;
static uint8_t err_count;

static bool oled_write(const uint8_t *buf, size_t len)
{
    if (!present)
        return false;

    int r = i2c_write_timeout_us(OLED_I2C_INST, OLED_I2C_ADDR, buf, len, false,
                                 OLED_I2C_TIMEOUT_US);
    if (r == (int)len)
    {
        err_count = 0;
        return true;
    }

    if (++err_count >= OLED_MAX_ERRS)
        present = false;
    return false;
}

// Control byte 0x00 marks the rest of the transfer as commands, 0x40 as display data.
static bool oled_cmds(const uint8_t *c, size_t n)
{
    uint8_t buf[32];
    if (n + 1 > sizeof(buf))
        return false;
    buf[0] = 0x00;
    memcpy(buf + 1, c, n);
    return oled_write(buf, n + 1);
}

bool ssd1306_present(void) { return present; }

bool ssd1306_init(void)
{
    static const uint8_t init_seq[] = {
        0xAE,       // display off
        0xD5, 0x80, // clock divide / oscillator frequency
        0xA8, 0x3F, // multiplex ratio = 63 (64 rows)
        0xD3, 0x00, // display offset
        0x40,       // start line 0
        0x8D, 0x14, // charge pump on (module has no external Vcc)
        0x20, 0x00, // horizontal addressing mode
        0xA1,       // segment remap
        0xC8,       // COM scan direction reversed
        0xDA, 0x12, // COM pin config, alternative
        0x81, 0x7F, // contrast
        0xD9, 0xF1, // pre-charge period
        0xDB, 0x40, // VCOMH deselect
        0xA4,       // resume from RAM
        0xA6,       // normal (not inverted)
        0x2E,       // scrolling off
        0xAF,       // display on
    };

    i2c_init(OLED_I2C_INST, OLED_I2C_SPEED_KHZ * 1000);
    gpio_set_function(OLED_I2C_PIN_SDA, GPIO_FUNC_I2C);
    gpio_set_function(OLED_I2C_PIN_SCL, GPIO_FUNC_I2C);
    // Most SSD1306 breakouts carry their own 4.7k pull-ups; the RP2040's internal ones
    // (~50k) are only a fallback for a bare panel and are marginal at 400 kHz.
    gpio_pull_up(OLED_I2C_PIN_SDA);
    gpio_pull_up(OLED_I2C_PIN_SCL);

    present = true;
    err_count = 0;

    if (!oled_cmds(init_seq, sizeof(init_seq)))
    {
        present = false;
        return false;
    }

    memset(fb, 0, sizeof(fb));
    dirty = (1u << OLED_PAGES) - 1; // blank the panel's power-on garbage
    chunk_idx = 0;
    return true;
}

void ssd1306_row(uint8_t row, const char *s, bool inverse)
{
    if (row >= OLED_PAGES)
        return;

    uint8_t line[OLED_W];
    memset(line, inverse ? 0xFF : 0x00, sizeof(line));

    for (uint8_t x = 0; *s && x + OLED_CELL_W <= OLED_W; s++, x += OLED_CELL_W)
    {
        const unsigned char *g = &font[(unsigned char)(*s) * 5];
        for (int i = 0; i < 5; i++)
            line[x + i] = inverse ? (uint8_t)~g[i] : g[i];
    }

    if (memcmp(fb[row], line, sizeof(line)) == 0)
        return; // unchanged, don't queue an I2C transfer for nothing

    memcpy(fb[row], line, sizeof(line));
    dirty |= 1u << row;
}

void ssd1306_flush_step(void)
{
    if (!present || !dirty)
        return;

    int page = __builtin_ctz(dirty);
    uint8_t c0 = chunk_idx * CHUNK;

    const uint8_t window[] = {
        0x21, c0, (uint8_t)(c0 + CHUNK - 1), // column range
        0x22, (uint8_t)page, (uint8_t)page,  // page range
    };
    if (!oled_cmds(window, sizeof(window)))
        return;

    uint8_t buf[1 + CHUNK];
    buf[0] = 0x40;
    memcpy(buf + 1, &fb[page][c0], CHUNK);
    if (!oled_write(buf, sizeof(buf)))
        return;

    if (++chunk_idx >= CHUNKS_PER_PAGE)
    {
        chunk_idx = 0;
        dirty &= ~(1u << page);
    }
}

#else

bool ssd1306_init(void) { return false; }
bool ssd1306_present(void) { return false; }
void ssd1306_row(uint8_t row, const char *s, bool inverse) { (void)row; (void)s; (void)inverse; }
void ssd1306_flush_step(void) {}

#endif
