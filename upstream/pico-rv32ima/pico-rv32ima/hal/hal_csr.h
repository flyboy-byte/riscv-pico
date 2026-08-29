#include <stdint.h>
#include "hardware/gpio.h"
#include "hw_config.h"

uint8_t spi_tx_data, spi_rx_data;

static inline uint8_t bb_spi_xfer_byte(uint8_t tx_data)
{
    uint8_t rx_data = 0;

    for (int i = 0; i < 8; i++)
    {
        // set MOSI
        gpio_put(BB_SPI_MOSI, tx_data & 0x80);

        tx_data = tx_data << 1;

        gpio_put(BB_SPI_SCK, false);
        sleep_us(BB_SPI_DELAY);

        rx_data = rx_data << 1;
        if (gpio_get(BB_SPI_MISO))
            rx_data |= 1;

        gpio_put(BB_SPI_SCK, true);
        sleep_us(BB_SPI_DELAY);
    }

    return rx_data;
}

// Four host pins exposed to the guest as generic GPIO, CSRs 0x1a0-0x1a3. Whichever
// two of these are also claimed by the OLED (21, 28) when it's disabled become free
// too, but the kernel driver only knows about a fixed 4 (see PLAN.md's GPIO scoping
// note) -- keep this array in sync with that if the pin set ever changes.
static const uint8_t gpio_csr_pins[4] = {1, 9, 15, 22};
static uint8_t gpio_csr_sel = 0;
static bool gpio_csr_inited[4] = {false, false, false, false};

static inline void custom_csr_write(uint16_t csrno, uint32_t value)
{
    // 0x180 : chip select register
    if (csrno == 0x180)
    {
        gpio_put(BB_SPI_CS, !value);
        sleep_us(BB_SPI_DELAY);
    }

    // 0x181 : initiate SPI transfer
    else if (csrno == 0x181)
    {
        // do transfer here
        spi_rx_data = bb_spi_xfer_byte(spi_tx_data);
    }

    // 0x182 : tx data register
    else if (csrno == 0x182)
    {
        spi_tx_data = value;
    }

    // 0x1a0 : GPIO select register -- picks which of the 4 pins the 0x1a1/0x1a2
    // writes and the 0x1a3 read below apply to
    else if (csrno == 0x1a0)
    {
        gpio_csr_sel = value & 3;
        if (!gpio_csr_inited[gpio_csr_sel])
        {
            gpio_init(gpio_csr_pins[gpio_csr_sel]);
            gpio_csr_inited[gpio_csr_sel] = true;
        }
    }

    // 0x1a1 : GPIO direction for the selected pin (0 = input, 1 = output)
    else if (csrno == 0x1a1)
    {
        gpio_set_dir(gpio_csr_pins[gpio_csr_sel], value ? GPIO_OUT : GPIO_IN);
    }

    // 0x1a2 : GPIO output level for the selected pin (only meaningful if it's an
    // output -- writing this on an input pin has no effect on the real hardware)
    else if (csrno == 0x1a2)
    {
        gpio_put(gpio_csr_pins[gpio_csr_sel], value);
    }
}

static inline uint32_t custom_csr_read(uint16_t csrno)
{
    // 0x182 : tx data register
    if (csrno == 0x183)
        return spi_rx_data;

    // 0x1a3 : GPIO input level for the selected pin -- valid whether that pin is
    // currently configured as input or output, same as a real gpio_get()
    if (csrno == 0x1a3)
        return gpio_get(gpio_csr_pins[gpio_csr_sel]);

    return 0;
}