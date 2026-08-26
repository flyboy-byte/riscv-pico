/*
 * Real-time bit-banged SPI SLAVE for the SD-over-SPI link to the Pico.
 * Links libpigpio directly in-process (NOT the pigpiod daemon -- must stop
 * pigpiod first, gpioInitialise() needs exclusive hardware access).
 *
 * This program handles ONLY the timing-critical bit-level work: sampling
 * MOSI on SCLK edges and driving MISO on the opposite edge. Protocol/FSM
 * logic (mmcbbp.c command parsing, already built+tested in sdcard_emu.py)
 * stays in a separate Python process -- complete bytes are handed off via
 * stdout, response bytes read back via stdin. Keeps the hot loop minimal.
 *
 * Assumes SPI Mode 0 (CPOL=0, CPHA=0) -- confirmed as the RP2040 SDK's
 * spi_write_read_blocking() default (hal_sd.h), not verified via an
 * explicit spi_set_format() call (wasn't found in the fetched source), but
 * Mode 0 is the standard default and the near-universal SD-over-SPI
 * convention.
 *   - Master presents each bit before/at the rising edge -> we SAMPLE MOSI
 *     on the rising edge.
 *   - We must have our bit ready before the master samples MISO on the
 *     next rising edge -> we PRESENT the next MISO bit on the falling edge.
 *
 * Wiring (Pi is slave/"card"):
 *   SCLK = GPIO19 (input)
 *   MOSI = GPIO20 (input)
 *   MISO = GPIO18 (output)
 *   CE   = GPIO21 (input, active low)
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sched.h>
#include <sys/mman.h>
#include <pigpio.h>

#define SCLK 19
#define MOSI 20
#define MISO 18
#define CE   21

static void harden_realtime(void) {
    /* Reduce (not eliminate -- this is still stock Linux, not an RTOS)
       how often the kernel preempts this process mid-loop: real-time FIFO
       scheduling priority + lock all memory to avoid page-fault stalls. */
    struct sched_param sp = { .sched_priority = sched_get_priority_max(SCHED_FIFO) };
    if (sched_setscheduler(0, SCHED_FIFO, &sp) != 0) {
        fprintf(stderr, "warning: sched_setscheduler(SCHED_FIFO) failed (%m) -- "
                         "continuing at normal priority\n");
    }
    if (mlockall(MCL_CURRENT | MCL_FUTURE) != 0) {
        fprintf(stderr, "warning: mlockall failed (%m) -- continuing without it\n");
    }
}

int main(void) {
    if (gpioInitialise() < 0) {
        fprintf(stderr, "gpioInitialise failed -- is pigpiod stopped? "
                         "(gpioInitialise needs exclusive hardware access)\n");
        return 1;
    }
    harden_realtime();

    gpioSetMode(SCLK, PI_INPUT);
    gpioSetMode(MOSI, PI_INPUT);
    gpioSetMode(CE, PI_INPUT);
    gpioSetMode(MISO, PI_OUTPUT);
    gpioWrite(MISO, 1);

    /* stdin non-blocking so we can poll it without stalling the hot loop */
    int flags = fcntl(STDIN_FILENO, F_GETFL, 0);
    fcntl(STDIN_FILENO, F_SETFL, flags | O_NONBLOCK);

    fprintf(stderr, "bitbang_slave: watching SCLK=%d MOSI=%d MISO=%d CE=%d\n",
            SCLK, MOSI, MISO, CE);

    int last_sclk = gpioRead(SCLK);
    int last_ce = gpioRead(CE);
    unsigned char rx_byte = 0;
    int rx_bits = 0;
    unsigned char tx_byte = 0xFF;
    int tx_bits_sent = 0; /* bits presented from tx_byte since it was loaded */

    for (;;) {
        int ce = gpioRead(CE);
        if (ce != last_ce) {
            if (ce == 0) {
                /* Freshly selected: reset bit alignment AND discard any
                   stale unread bytes left in stdin from a PREVIOUS
                   transaction the master aborted early (e.g. its
                   retry-on-CRC-failure logic bailing out mid-transfer
                   without clocking out everything we'd already queued).
                   Without this, leftover real response bytes -- including
                   whole sector payloads -- get silently consumed as the
                   response to a later, unrelated command. */
                rx_bits = 0;
                tx_bits_sent = 0;
                tx_byte = 0xFF;
                int flushed = 0;
                unsigned char discard;
                while (read(STDIN_FILENO, &discard, 1) == 1) flushed++;
                if (flushed && getenv("BB_DEBUG")) {
                    fprintf(stderr, "  [CE low] flushed %d stale stdin byte(s)\n", flushed);
                    fflush(stderr);
                }
            }
            last_ce = ce;
        }

        int sclk = gpioRead(SCLK);
        if (sclk != last_sclk) {
            if (sclk == 1) {
                /* rising edge: sample MOSI */
                int bit = gpioRead(MOSI);
                rx_byte = (unsigned char)((rx_byte << 1) | bit);
                rx_bits++;
                if (rx_bits == 8) {
                    ssize_t w = write(STDOUT_FILENO, &rx_byte, 1);
                    (void)w;
                    rx_bits = 0;
                }
            } else {
                /* falling edge: present next MISO bit */
                if (tx_bits_sent == 0) {
                    /* starting a fresh byte -- pull one from stdin if we
                       owe a response, else keep sending 0xFF filler */
                    unsigned char next;
                    ssize_t r = read(STDIN_FILENO, &next, 1);
                    tx_byte = (r == 1) ? next : 0xFF;
                    if (getenv("BB_DEBUG")) {
                        fprintf(stderr, "  [tx byte-boundary] read()=%zd -> tx_byte=0x%02x (ce=%d)\n",
                                r, tx_byte, ce);
                        fflush(stderr);
                    }
                }
                gpioWrite(MISO, (tx_byte >> 7) & 1);
                tx_byte <<= 1;
                tx_bits_sent++;
                if (tx_bits_sent == 8) tx_bits_sent = 0;
            }
            last_sclk = sclk;
        }
    }

    gpioTerminate();
    return 0;
}
