#ifndef HARNESS_HAL_CSR_H
#define HARNESS_HAL_CSR_H

#include <stdint.h>
#include <stdio.h>

#include "netchan.h"

// 0x141/0x142: second HVC console channel (putc/getc), same shape as the primary
// channel's 0x139/0x140 but bridged to a host PTY instead of stdio - see netchan.c.
// Anything else: real hardware bit-bangs a second SPI bus for a project-specific
// peripheral here. Nothing on the desktop side needs it.
//
// 0x1a0-0x1a3: GPIO (see pico-rv32ima/hal/hal_csr.h for the real version). There's
// no real pin to drive on a desktop, so this is a loopback simulation only, logged
// to stderr - enough to smoke-test the kernel driver's CSR sequencing (select then
// dir/out/in) before ever touching hardware, not a hardware behavior model.
static uint8_t gpio_sim_dir[4] = {0, 0, 0, 0};
static uint8_t gpio_sim_out[4] = {0, 0, 0, 0};
static uint8_t gpio_sim_sel = 0;

static inline void custom_csr_write(uint16_t csrno, uint32_t value)
{
    if (csrno == 0x141)
        netchan_putc((char)value);
    else if (csrno == 0x1a0)
    {
        gpio_sim_sel = value & 3;
    }
    else if (csrno == 0x1a1)
    {
        gpio_sim_dir[gpio_sim_sel] = value ? 1 : 0;
        fprintf(stderr, "[gpio sim] pin %d dir=%s\n", gpio_sim_sel,
                gpio_sim_dir[gpio_sim_sel] ? "out" : "in");
    }
    else if (csrno == 0x1a2)
    {
        gpio_sim_out[gpio_sim_sel] = value ? 1 : 0;
        fprintf(stderr, "[gpio sim] pin %d out=%d\n", gpio_sim_sel, gpio_sim_out[gpio_sim_sel]);
    }
}

static inline uint32_t custom_csr_read(uint16_t csrno)
{
    if (csrno == 0x142)
        return netchan_available() ? (uint8_t)netchan_read() : (uint32_t)-1;
    if (csrno == 0x1a3)
        return gpio_sim_out[gpio_sim_sel]; // loopback: reads back what was written
    return 0;
}

#endif
