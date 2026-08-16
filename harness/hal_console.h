#ifndef HARNESS_HAL_CONSOLE_H
#define HARNESS_HAL_CONSOLE_H

#include "console.h"

// Real hardware waits for a keypress before booting. Desktop harness: go immediately.
#define pwr_button() 1

#endif
