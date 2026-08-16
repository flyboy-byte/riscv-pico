#ifndef HARNESS_HAL_CSR_H
#define HARNESS_HAL_CSR_H

#include <stdint.h>

// Real hardware bit-bangs a second SPI bus for a project-specific peripheral here.
// Nothing on the desktop side needs it.
static inline void custom_csr_write(uint16_t csrno, uint32_t value)
{
    (void)csrno;
    (void)value;
}

static inline uint32_t custom_csr_read(uint16_t csrno)
{
    (void)csrno;
    return 0;
}

#endif
