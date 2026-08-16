#ifndef HARNESS_HAL_PSRAM_H
#define HARNESS_HAL_PSRAM_H

// Desktop stand-in for a real SPI PSRAM chip. Only psram.c includes this header, so the state
// below is safely file-static — one instance, no multi-TU clash.
//
// psram.c always drives these four calls in one of two shapes:
//   select(); write(cmd+addr, 4|5 bytes); write(payload) or read(payload); deselect();
// The first write after select() is always the command+24-bit-address prefix — everything after
// that is payload. That's the whole protocol worth modeling; no real SPI/timing needed.

#include <stdint.h>
#include <string.h>

#include "vm_config.h"

#define PSRAM_HARNESS_SIZE ((uint32_t)EMULATOR_RAM_MB * 1024u * 1024u)
#define PSRAM_CMD_READ_ID_HARNESS 0x9F

static uint8_t psram_mem[PSRAM_HARNESS_SIZE];
static uint8_t psram_cur_cmd;
static uint32_t psram_cur_addr;
static int psram_have_cmd;

static inline void psram_select(void)
{
    psram_have_cmd = 0;
}

static inline void psram_deselect(void)
{
    psram_have_cmd = 0;
}

static inline void psram_spi_write(const void *buf, unsigned int sz)
{
    const uint8_t *b = (const uint8_t *)buf;

    if (!psram_have_cmd)
    {
        psram_cur_cmd = b[0];
        if (sz >= 4)
            psram_cur_addr = ((uint32_t)b[1] << 16) | ((uint32_t)b[2] << 8) | (uint32_t)b[3];
        psram_have_cmd = 1;
        return;
    }

    memcpy(&psram_mem[psram_cur_addr % PSRAM_HARNESS_SIZE], b, sz);
    psram_cur_addr += sz;
}

static inline void psram_spi_read(void *buf, unsigned int sz)
{
    uint8_t *b = (uint8_t *)buf;

    if (psram_cur_cmd == PSRAM_CMD_READ_ID_HARNESS)
    {
        // Real chip returns a 6-byte JEDEC ID; psram_read_kgd() only checks byte 1 == 0x5D.
        memset(b, 0, sz);
        if (sz > 1)
            b[1] = 0x5D;
        return;
    }

    memcpy(b, &psram_mem[psram_cur_addr % PSRAM_HARNESS_SIZE], sz);
    psram_cur_addr += sz;
}

#endif
