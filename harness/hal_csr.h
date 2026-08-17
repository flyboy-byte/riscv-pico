#ifndef HARNESS_HAL_CSR_H
#define HARNESS_HAL_CSR_H

#include <stdint.h>

#include "netchan.h"

// 0x141/0x142: second HVC console channel (putc/getc), same shape as the primary
// channel's 0x139/0x140 but bridged to a host PTY instead of stdio - see netchan.c.
// Anything else: real hardware bit-bangs a second SPI bus for a project-specific
// peripheral here. Nothing on the desktop side needs it.
static inline void custom_csr_write(uint16_t csrno, uint32_t value)
{
    if (csrno == 0x141)
        netchan_putc((char)value);
}

static inline uint32_t custom_csr_read(uint16_t csrno)
{
    if (csrno == 0x142)
        return netchan_available() ? (uint8_t)netchan_read() : (uint32_t)-1;
    return 0;
}

#endif
