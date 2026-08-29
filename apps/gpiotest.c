// Smoke test for the tinyrv32-gpio driver (CSRs 0x1a0-0x1a3, /dev/gpiochip0).
// Requests line 0 as an output, sets it high, then reads it back on line 0 itself
// (same line, not a real loopback wire) to prove the request/set/get ioctl path and
// the driver's select-then-act CSR sequencing work end to end. On the desktop
// harness this exercises the stderr-logged simulation in harness/hal_csr.h; on real
// hardware it drives the actual pin (GPIO 1 in the current 4-pin map).
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <linux/gpio.h>

int main(void)
{
    int fd = open("/dev/gpiochip0", O_RDWR);
    if (fd < 0)
    {
        perror("open /dev/gpiochip0");
        return 1;
    }

    struct gpiochip_info info;
    if (ioctl(fd, GPIO_GET_CHIPINFO_IOCTL, &info) < 0)
    {
        perror("GPIO_GET_CHIPINFO_IOCTL");
        return 1;
    }
    printf("chip: %s label: %s lines: %u\n", info.name, info.label, info.lines);

    struct gpio_v2_line_request req;
    memset(&req, 0, sizeof(req));
    req.offsets[0] = 0;
    req.num_lines = 1;
    req.config.flags = GPIO_V2_LINE_FLAG_OUTPUT;
    strncpy(req.consumer, "gpiotest", sizeof(req.consumer) - 1);

    if (ioctl(fd, GPIO_V2_GET_LINE_IOCTL, &req) < 0)
    {
        perror("GPIO_V2_GET_LINE_IOCTL (output)");
        return 1;
    }

    struct gpio_v2_line_values vals;
    memset(&vals, 0, sizeof(vals));
    vals.mask = 1;
    vals.bits = 1; // drive line 0 high

    if (ioctl(req.fd, GPIO_V2_LINE_SET_VALUES_IOCTL, &vals) < 0)
    {
        perror("GPIO_V2_LINE_SET_VALUES_IOCTL");
        return 1;
    }
    printf("set line 0 high\n");

    vals.bits = 0;
    if (ioctl(req.fd, GPIO_V2_LINE_GET_VALUES_IOCTL, &vals) < 0)
    {
        perror("GPIO_V2_LINE_GET_VALUES_IOCTL");
        return 1;
    }
    printf("read back line 0: %llu\n", (unsigned long long)(vals.bits & 1));

    close(req.fd);
    close(fd);
    return 0;
}
