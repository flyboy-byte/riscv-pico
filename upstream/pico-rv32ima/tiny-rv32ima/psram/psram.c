#include "psram.h"
#include "hal_psram.h"
#include "hal_timing.h"

#ifndef PSRAM_TWO_CHIPS
#define PSRAM_TWO_CHIPS 0
#endif
#ifndef PSRAM_CHIP_SIZE_BYTES
#define PSRAM_CHIP_SIZE_BYTES (8UL * 1024 * 1024)
#endif

#define PSRAM_CMD_RES_EN 0x66
#define PSRAM_CMD_RESET 0x99
#define PSRAM_CMD_READ_ID 0x9F
#define PSRAM_CMD_READ 0x03
#define PSRAM_CMD_READ_FAST 0x0B
#define PSRAM_CMD_WRITE 0x02
#define PSRAM_KGD 0x5D

// addr is a chip-select address (any address within the target chip's range) — not a payload
// offset. Only psram_access() below deals with payload addresses.
static void psram_cmd_at(uint8_t cmd, uint32_t addr)
{
    psram_select(addr);
    psram_spi_write(&cmd, 1);
    psram_deselect(addr);
}

void psram_cmd(uint8_t cmd)
{
    psram_cmd_at(cmd, 0);
}

static uint8_t psram_read_kgd_at(uint32_t addr)
{
    uint8_t buf[6] = {0};
    buf[0] = PSRAM_CMD_READ_ID;
    psram_select(addr);
    psram_spi_write(buf, 4);
    psram_spi_read(buf, 6);
    psram_deselect(addr);

    return buf[1] == PSRAM_KGD;
}

uint8_t psram_read_kgd(void)
{
    return psram_read_kgd_at(0);
}

uint8_t psram_init(void)
{
    int num_chips = PSRAM_TWO_CHIPS ? 2 : 1;
    uint8_t ok = 1;

    for (int i = 0; i < num_chips; i++)
    {
        uint32_t chip_addr = (uint32_t)i * PSRAM_CHIP_SIZE_BYTES;
        psram_cmd_at(PSRAM_CMD_RES_EN, chip_addr);
        psram_cmd_at(PSRAM_CMD_RESET, chip_addr);
        timing_delay_ms(10);
        ok = ok && psram_read_kgd_at(chip_addr);
    }
    return ok;
}

void psram_access(uint32_t addr, unsigned int size, bool write, void *bufP)
{
    uint8_t cmdAddr[5];
    unsigned int cmdSize = 4;

    if (write)
        cmdAddr[0] = PSRAM_CMD_WRITE;
    else
    {
        cmdAddr[0] = PSRAM_CMD_READ_FAST;
        cmdSize++;
    }

    // hal_psram.h picks the chip from the full address; the command bytes we send that chip
    // need to be its own chip-local address.
    uint32_t local_addr = PSRAM_TWO_CHIPS ? (addr % PSRAM_CHIP_SIZE_BYTES) : addr;

    cmdAddr[1] = local_addr >> 16;
    cmdAddr[2] = local_addr >> 8;
    cmdAddr[3] = local_addr;

    psram_select(addr);
    psram_spi_write(cmdAddr, cmdSize);

    if (write)
        psram_spi_write(bufP, size);
    else
        psram_spi_read(bufP, size);
    psram_deselect(addr);
}

void psram_load_data(void *buf, uint32_t addr, unsigned int size)
{
    while (size >= 1024)
    {
        psram_access(addr, 1024, true, buf);
        addr += 1024;
        buf += 1024;
        size -= 1024;
    }

    if (size)
        psram_access(addr, size, true, buf);
}
