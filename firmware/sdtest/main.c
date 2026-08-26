// Standalone SD-SPI bring-up probe. Not part of the real pico-rv32ima firmware — this
// exists purely to isolate the SD-SPI link (Pico as master, no PSRAM/emulator/console
// framework involved) so its raw byte traffic can be compared directly against whatever
// is (or isn't) arriving on the other end, without the real firmware's silent panic
// hiding what actually happened on the wire.
//
// Runs the exact init handshake from tiny-rv32ima/pff/mmcbbp.c's disk_initialize() —
// CMD0 -> CMD8 -> ACMD41 (poll) -> CMD58 — with verbose per-step logging, instead of
// just repeating CMD0 in isolation.
//
// Same pins as pico-rv32ima/hw_config.h's SD config: CK=GP2, MOSI=GP3, MISO=GP4, CS=GP0.

#include "pico/stdlib.h"
#include "hardware/spi.h"
#include <stdio.h>
#include <stdbool.h>

#define SD_SPI_INST spi0
#define SD_SPI_PIN_CK 2
#define SD_SPI_PIN_TX 3
#define SD_SPI_PIN_RX 4
#define SD_SPI_PIN_CS 0

#define SD_SPI_SPEED_HZ (20 * 1000) // slow, to give a jittery bit-bang slave more margin

#define CMD0 (0x40 + 0)
#define CMD8 (0x40 + 8)
#define CMD55 (0x40 + 55)
#define CMD41 (0x40 + 41)
#define CMD58 (0x40 + 58)
#define CMD17 (0x40 + 17)

static inline void cs_low(void) { gpio_put(SD_SPI_PIN_CS, 0); }
static inline void cs_high(void) { gpio_put(SD_SPI_PIN_CS, 1); }

static uint8_t xfer(uint8_t out)
{
    uint8_t in = 0;
    spi_write_read_blocking(SD_SPI_INST, &out, &in, 1);
    return in;
}

// Standard SD data-block CRC16-CCITT (poly 0x1021, init 0x0000) -- same algorithm real
// SD cards use to protect each 512-byte data block. mmcbbp.c doesn't check this (it just
// discards the two trailing CRC bytes), but nothing stops us from checking it ourselves
// as a real integrity gate before accepting a sector's contents.
static uint16_t crc16_ccitt(const uint8_t *buf, int len)
{
    uint16_t crc = 0x0000;
    for (int i = 0; i < len; i++)
    {
        crc ^= (uint16_t)buf[i] << 8;
        for (int b = 0; b < 8; b++)
            crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : (crc << 1);
    }
    return crc;
}

static void print_bytes(const char *label, uint8_t *buf, int n)
{
    printf("%s:", label);
    for (int i = 0; i < n; i++)
        printf(" %02x", buf[i]);
    printf("\r\n");
}

// Mirrors mmcbbp.c's send_cmd() exactly: CS toggle dance, command+arg+crc frame,
// then clocks up to 10 bytes waiting for a response with the high bit clear.
static uint8_t send_cmd(uint8_t cmd, uint32_t arg, const char *label)
{
    cs_high();
    xfer(0xFF);
    cs_low();
    xfer(0xFF);

    uint8_t crc = 0x01;
    if (cmd == CMD0)
        crc = 0x95;
    if (cmd == CMD8)
        crc = 0x87;

    uint8_t frame[6] = {cmd, (uint8_t)(arg >> 24), (uint8_t)(arg >> 16),
                         (uint8_t)(arg >> 8), (uint8_t)arg, crc};
    printf("%s tx:", label);
    for (int i = 0; i < 6; i++)
    {
        printf(" %02x", frame[i]);
        xfer(frame[i]);
    }
    printf("\r\n");

    uint8_t res = 0xFF;
    for (int n = 10; n > 0; n--)
    {
        res = xfer(0xFF);
        if (!(res & 0x80))
            break;
    }
    printf("%s response: 0x%02x\r\n", label, res);
    return res;
}

int main()
{
    stdio_init_all();
    sleep_ms(2000); // let USB-CDC actually enumerate/connect before the first print

    gpio_init(SD_SPI_PIN_CS);
    gpio_set_dir(SD_SPI_PIN_CS, GPIO_OUT);
    cs_high();

    spi_init(SD_SPI_INST, SD_SPI_SPEED_HZ);
    gpio_set_function(SD_SPI_PIN_CK, GPIO_FUNC_SPI);
    gpio_set_function(SD_SPI_PIN_TX, GPIO_FUNC_SPI);
    gpio_set_function(SD_SPI_PIN_RX, GPIO_FUNC_SPI);

    printf("\r\nsdtest: SD-SPI init-handshake probe (CK=GP%d TX=GP%d RX=GP%d CS=GP%d, %d Hz)\r\n",
           SD_SPI_PIN_CK, SD_SPI_PIN_TX, SD_SPI_PIN_RX, SD_SPI_PIN_CS, SD_SPI_SPEED_HZ);

    while (true)
    {
        printf("\r\n=== init attempt ===\r\n");

        cs_high();
        for (int i = 0; i < 10; i++)
            xfer(0xFF);
        printf("sent 10 dummy bytes (CS high)\r\n");

        uint8_t r = send_cmd(CMD0, 0, "CMD0");
        if (r != 0x01)
        {
            printf("CMD0 didn't return idle-state (0x01) -- stopping this attempt here\r\n");
            cs_high();
            xfer(0xFF);
            sleep_ms(3000);
            continue;
        }
        printf("CMD0 OK (idle state)\r\n");

        r = send_cmd(CMD8, 0x1AA, "CMD8");
        if (r == 0x01)
        {
            uint8_t r7[4];
            for (int i = 0; i < 4; i++)
                r7[i] = xfer(0xFF);
            print_bytes("CMD8 R7 tail", r7, 4);
            if (r7[2] == 0x01 && r7[3] == 0xAA)
                printf("CMD8 OK (SDv2, voltage/check-pattern echoed correctly)\r\n");
            else
                printf("CMD8 R7 tail didn't match expected 01 AA -- garbled?\r\n");
        }
        else
        {
            printf("CMD8 didn't return 0x01 -- stopping this attempt here\r\n");
            cs_high();
            xfer(0xFF);
            sleep_ms(3000);
            continue;
        }

        bool acmd41_ok = false;
        for (int tries = 0; tries < 20; tries++)
        {
            uint8_t r1_55 = send_cmd(CMD55, 0, "CMD55");
            if (r1_55 > 1)
            {
                printf("CMD55 returned unexpected 0x%02x, retrying\r\n", r1_55);
                sleep_ms(50);
                continue;
            }
            // CMD55 already sent above (that's what makes this an "A"CMD) -- the command
            // byte itself is just plain CMD41, no separate flag bit to set.
            uint8_t r1_41 = send_cmd(CMD41, 1UL << 30, "ACMD41");
            if (r1_41 == 0x00)
            {
                acmd41_ok = true;
                break;
            }
            sleep_ms(50);
        }

        if (!acmd41_ok)
        {
            printf("ACMD41 never left idle state after 20 tries -- stopping this attempt here\r\n");
            cs_high();
            xfer(0xFF);
            sleep_ms(3000);
            continue;
        }
        printf("ACMD41 OK (left idle state)\r\n");

        r = send_cmd(CMD58, 0, "CMD58");
        if (r == 0x00)
        {
            uint8_t ocr[4];
            for (int i = 0; i < 4; i++)
                ocr[i] = xfer(0xFF);
            print_bytes("CMD58 OCR", ocr, 4);
            printf("=== FULL INIT HANDSHAKE SUCCEEDED ===\r\n");

            // Real sector read with real error detection: CRC16-CCITT over the 512 data
            // bytes, checked against the block's actual trailing CRC bytes (the Pi now
            // sends a genuine CRC, not dummy bytes). On mismatch, re-issue CMD17 for the
            // SAME sector rather than accepting corrupted data -- this is the retry logic
            // mmcbbp.c itself doesn't have, added here to see whether it closes the gap.
            static uint8_t sector[512];
            bool sector_ok = false;
            for (int attempt = 1; attempt <= 8 && !sector_ok; attempt++)
            {
                char label[16];
                snprintf(label, sizeof label, "CMD17 #%d", attempt);
                r = send_cmd(CMD17, 0, label);
                if (r != 0x00)
                {
                    printf("CMD17 didn't return 0x00, retrying\r\n");
                    continue;
                }

                uint8_t tok = 0xFF;
                for (int tries = 20000; tries > 0; tries--)
                {
                    tok = xfer(0xFF);
                    if (tok != 0xFF)
                        break;
                }
                if (tok != 0xFE)
                {
                    printf("never got data token (0xFE), last byte: 0x%02x -- retrying\r\n", tok);
                    continue;
                }

                for (int i = 0; i < 512; i++)
                    sector[i] = xfer(0xFF);
                uint8_t crc_rx_hi = xfer(0xFF);
                uint8_t crc_rx_lo = xfer(0xFF);
                uint16_t crc_rx = ((uint16_t)crc_rx_hi << 8) | crc_rx_lo;
                uint16_t crc_calc = crc16_ccitt(sector, 512);

                if (crc_rx != crc_calc)
                {
                    printf("CRC MISMATCH: got %04x, computed %04x -- discarding, retrying\r\n",
                           crc_rx, crc_calc);
                    continue;
                }

                print_bytes("sector[0..15]", sector, 16);
                printf("sector[510..511] (FAT boot sig, want 55 aa): %02x %02x\r\n",
                       sector[510], sector[511]);
                printf("CRC16 OK (%04x) -- data verified, not just assumed\r\n", crc_rx);
                sector_ok = (sector[510] == 0x55 && sector[511] == 0xAA);
                if (sector_ok)
                    printf("=== SECTOR READ SUCCEEDED (attempt %d), CRC-VERIFIED + VALID SIGNATURE ===\r\n", attempt);
                else
                    printf("CRC matched but FAT signature didn't -- shouldn't happen if CRC is real\r\n");
            }
            if (!sector_ok)
                printf("=== SECTOR READ FAILED after 8 attempts ===\r\n");
        }
        else
        {
            printf("CMD58 didn't return 0x00\r\n");
        }

        cs_high();
        xfer(0xFF);

        sleep_ms(3000);
    }
}
