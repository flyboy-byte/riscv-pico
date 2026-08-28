#include "pico/stdlib.h"
#include "hardware/clocks.h"

#include <stddef.h>
#include <stdint.h>

#include "hw_config.h"
#include "status_panel.h"

#if CONSOLE_OLED

#include "vm_config.h"
#include "ssd1306.h"
#include "emulator/emulator.h"

#define UPDATE_INTERVAL_US 500000

// Hand-rolled formatting on purpose. This is a copy_to_ram binary and the emulator's
// 160 KB PSRAM cache already dominates the RP2040's 264 KB; calling snprintf here drags
// in newlib's _svfprintf_r/_dtoa_r for about 10.6 KB, which is most of the remaining
// headroom. These two helpers cost tens of bytes and cover everything the panel needs.
//
// Both append to *pos, clamp at OLED_COLS, and always leave the buffer NUL-terminated.

static __attribute__((noinline)) void put_str(char *buf, size_t *pos, const char *s)
{
    while (*s && *pos < OLED_COLS)
        buf[(*pos)++] = *s++;
    buf[*pos] = 0;
}

// width == 0 means "no padding"; otherwise the number is right-aligned in `width`
// columns using `pad`.
static __attribute__((noinline)) void put_num(char *buf, size_t *pos, uint32_t v, int width, char pad)
{
    char tmp[11];
    int n = 0;
    do
        tmp[n++] = '0' + (v % 10);
    while (v /= 10);

    for (int i = n; i < width && *pos < OLED_COLS; i++)
        buf[(*pos)++] = pad;
    while (n-- && *pos < OLED_COLS)
        buf[(*pos)++] = tmp[n];
    buf[*pos] = 0;
}

static uint64_t last_us, last_instret;
static uint64_t next_update_us;
static uint32_t kips; // thousands of instructions/sec, from the last sample window

static const char *stage_name(uint8_t stage)
{
    switch (stage)
    {
    case VM_STAGE_INIT:
        return "init";
    case VM_STAGE_PSRAM_OK:
        return "psram ok";
    case VM_STAGE_SD_OK:
        return "sd ok";
    case VM_STAGE_LOADING:
        return "loading";
    case VM_STAGE_RUNNING:
        return "running";
    case VM_STAGE_HALTED:
        return "halted";
    default:
        return "?";
    }
}

void status_panel_init(void)
{
    if (!ssd1306_init())
        return;

    char buf[OLED_COLS + 1];
    size_t n;

    ssd1306_row(0, " riscv-pico  rv32ima", true);

    n = 0;
    put_str(buf, &n, "RAM   ");
    put_num(buf, &n, EMULATOR_RAM_MB, 0, ' ');
    put_str(buf, &n, " MB / ");
    put_num(buf, &n, PSRAM_TWO_CHIPS ? 2 : 1, 0, ' ');
    put_str(buf, &n, " chip");
    ssd1306_row(1, buf, false);

    n = 0;
    put_str(buf, &n, "PSRAM ");
    put_num(buf, &n, PSRAM_SPI_SPEED_MHZ, 0, ' ');
    put_str(buf, &n, " MHz");
    ssd1306_row(2, buf, false);

    ssd1306_row(3, "STATE booting", false);

    last_us = time_us_64();
    last_instret = 0;
    next_update_us = last_us + UPDATE_INTERVAL_US;
}

void status_panel_task(void)
{
    if (!ssd1306_present())
        return;

    // One chunk per call. The panel is at most a few hundred milliseconds behind even
    // when every row changes, and no single call blocks core 0 for more than ~2 ms.
    ssd1306_flush_step();

    uint64_t now = time_us_64();
    if (now < next_update_us)
        return;
    next_update_us = now + UPDATE_INTERVAL_US;

    uint64_t instret = vm_get_instret();
    // Deliberately narrowed to 32 bits: the window is ~0.5 s, so the deltas are ~1e6 and
    // ~5e5, and a 64-bit divide here would pull in another few hundred bytes of helper.
    uint32_t d_us = (uint32_t)(now - last_us);
    uint32_t d_instr = (uint32_t)(instret - last_instret);
    if (d_us && d_instr < 4000000u)
        kips = d_instr * 1000u / d_us;
    last_us = now;
    last_instret = instret;

    char buf[OLED_COLS + 1];
    size_t n;

    n = 0;
    put_str(buf, &n, "STATE ");
    put_str(buf, &n, stage_name(vm_get_stage()));
    ssd1306_row(3, buf, false);

    n = 0;
    put_str(buf, &n, "SPEED ");
    put_num(buf, &n, kips / 1000, 0, ' ');
    put_str(buf, &n, ".");
    put_num(buf, &n, (kips % 1000) / 10, 2, '0');
    put_str(buf, &n, " MIPS");
    ssd1306_row(4, buf, false);

    n = 0;
    put_str(buf, &n, "INSTR ");
    put_num(buf, &n, (uint32_t)(instret / 1000000u), 0, ' ');
    put_str(buf, &n, " M");
    ssd1306_row(5, buf, false);

    uint32_t up = (uint32_t)(now / 1000000u);
    n = 0;
    put_str(buf, &n, "UP    ");
    put_num(buf, &n, up / 3600, 2, '0');
    put_str(buf, &n, ":");
    put_num(buf, &n, (up / 60) % 60, 2, '0');
    put_str(buf, &n, ":");
    put_num(buf, &n, up % 60, 2, '0');
    ssd1306_row(6, buf, false);

    n = 0;
    put_str(buf, &n, "CLK   ");
    put_num(buf, &n, (uint32_t)(clock_get_hz(clk_sys) / 1000000u), 0, ' ');
    put_str(buf, &n, " MHz");
    ssd1306_row(7, buf, false);
}

#else

void status_panel_init(void) {}
void status_panel_task(void) {}

#endif
