#ifndef HARNESS_HAL_TIMING_H
#define HARNESS_HAL_TIMING_H

#include <stdint.h>
#include <time.h>
#include <unistd.h>

#define timing_delay_ms(n) usleep((useconds_t)(n) * 1000)
#define timing_delay_us(n) usleep((useconds_t)(n))

static inline uint64_t timing_micros(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000ULL + (uint64_t)ts.tv_nsec / 1000ULL;
}

#endif
