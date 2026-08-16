#include "hardware/gpio.h"
#include "hardware/spi.h"
#include "hw_config.h"

// psram.c passes the *full* (multi-chip) address so this header owns picking the CS pin.
// psram.c is responsible for turning that same address into a chip-local address for the
// command bytes it sends — this file only ever asserts/deasserts a pin.
#if PSRAM_TWO_CHIPS
#define psram_chip_cs(addr) (((addr) < PSRAM_CHIP_SIZE_BYTES) ? PSRAM_SPI_PIN_S1 : PSRAM_SPI_PIN_S2)
#else
#define psram_chip_cs(addr) PSRAM_SPI_PIN_S1
#endif

#define psram_select(addr) gpio_put(psram_chip_cs(addr), false)
#define psram_deselect(addr) gpio_put(psram_chip_cs(addr), true)

#define psram_spi_write(buf, sz) spi_write_blocking(PSRAM_SPI_INST, buf, sz)
#define psram_spi_read(buf, sz) spi_read_blocking(PSRAM_SPI_INST, 0, buf, sz)
