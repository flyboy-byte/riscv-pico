# Playing with BASIC and GPIO on real hardware

Self-contained walkthrough for what's on the SD card right now (2026-08-29) and how to use it —
written so it also works as-is if you paste it to ChatGPT for help writing new GPIO code.

## 1. Flash the firmware

Download `pico-rv32ima-pico.uf2` from the
[`pico-rv32ima-boards-v5`](https://github.com/flyboy-byte/riscv-pico/releases/tag/pico-rv32ima-boards-v5)
release (use `pico2.uf2`/`pico_w.uf2`/`pico2_w.uf2` if you're on a different board variant).

Hold **BOOTSEL**, plug in the Pico, it mounts as a USB drive (`RPI-RP2`). Copy the `.uf2` onto it,
it reboots automatically running the new firmware. The SD card with the kernel and rootfs already
has everything below on it — no separate step needed there.

Connect over USB-CDC serial (shows up as `/dev/ttyACM0` or similar) at any baud rate, or use the
VGA/PS2 console if that's wired up. **Boot waits for a keypress before starting** — this is
intentional (`pwr_button()` gates on `console_available()`), not a hang. Press any key once
connected and it'll boot.

## 2. What's on the SD card

| Program | What it is |
|---|---|
| `hello` | Minimal smoke test |
| `basic` | Tiny BASIC interpreter |
| `nano` | Real GNU nano 7.2, for writing files |
| `lua` | Real Lua 5.4.7 |
| `gpiotest` | GPIO smoke test / reference for the chardev API below |

Run any of them by name from the shell prompt, e.g. `basic`.

## 3. BASIC

`apps/basic.c` in the repo has the full interpreter source if you want to read it. Supported:

```
PRINT, LET, IF ... THEN, GOTO, GOSUB, RETURN, FOR ... TO ... STEP / NEXT,
INPUT, LIST, RUN, NEW, END, REM
```

26 integer variables, `A`-`Z`. Line-based only — no cursor positioning, matches what the console
renders.

**Interactive use**: just run `basic` and type numbered lines, then `RUN`.

```
10 FOR I = 1 TO 5
20 PRINT I
30 NEXT I
40 END
RUN
```

**Writing a program in `nano` and running it non-interactively**: `basic` has no file-loading
command of its own, but it reads its input as plain lines from stdin — so shell redirection does
the job. Write the numbered program in `nano`, end the file with a `RUN` line, save it, then:

```sh
basic < myprogram.bas
```

This runs to completion and drops you back at the shell (it doesn't stay in an interactive BASIC
session afterward, since it exits at end-of-input).

## 4. GPIO

Four host pins are exposed to Linux as a real `gpiochip` — standard Linux GPIO chardev API, no
custom protocol. This is genuinely `/dev/gpiochip0` behaving like GPIO does on any other embedded
Linux board; any general GPIO chardev tutorial or ChatGPT answer about the Linux `GPIO_V2` uAPI
applies directly.

### The 4 available lines

| Line offset (what you request) | RP2040 GPIO | Physical Pico pin |
|---|---|---|
| 0 | GP1 | pin 2 |
| 1 | GP9 | pin 12 |
| 2 | GP15 | pin 20 |
| 3 | GP22 | pin 29 |

Check with:
```sh
cat /sys/kernel/debug/gpio 2>/dev/null   # may not be mounted; not required
```
or just trust the table above — it's fixed in firmware
(`upstream/pico-rv32ima/pico-rv32ima/hal/hal_csr.h`, `gpio_csr_pins[]`).

**Wiring an LED**: pin (positive leg through a ~330Ω resistor) → your chosen physical pin above,
LED negative leg → any GND pin (pins 3, 8, 13, 18, 23, 28, 33, 38).

**Wiring a button**: one leg → your chosen physical pin, other leg → GND. No internal pull-up/down
is implemented by this driver — wire an external pull-down (or pull-up) resistor, or a
button+resistor module, don't rely on requesting a bias flag to do anything.

### Reading/writing from the shell — no tooling installed for this yet

This rootfs doesn't have `libgpiod`'s `gpioset`/`gpioget` command-line tools built in. Two options:

1. **Use/adapt `gpiotest`** (already on the card) — it's a ~70-line C program that requests line 0
   as an output, sets it high, and reads it back. Source is `apps/gpiotest.c` in the repo. Copy and
   modify it for whatever pin/behavior you want, then cross-compile (see "Building new programs"
   below).
2. **Ask for `libgpiod`'s `gpioset`/`gpioget` to be buildroot-packaged** — a config change
   (`BR2_PACKAGE_LIBGPIOD=y`) plus a rootfs rebuild, not done yet.

### The raw API, for writing your own program (or handing to ChatGPT)

```c
#include <fcntl.h>
#include <sys/ioctl.h>
#include <linux/gpio.h>

int fd = open("/dev/gpiochip0", O_RDWR);

// Request a line as output
struct gpio_v2_line_request req = {0};
req.offsets[0] = 0;              // 0-3, see the table above
req.num_lines = 1;
req.config.flags = GPIO_V2_LINE_FLAG_OUTPUT;   // or GPIO_V2_LINE_FLAG_INPUT
strcpy(req.consumer, "myprogram");
ioctl(fd, GPIO_V2_GET_LINE_IOCTL, &req);       // req.fd is now the line handle

// Set it high
struct gpio_v2_line_values vals = {0};
vals.mask = 1;
vals.bits = 1;                                  // 1 = high, 0 = low
ioctl(req.fd, GPIO_V2_LINE_SET_VALUES_IOCTL, &vals);

// Read it back
ioctl(req.fd, GPIO_V2_LINE_GET_VALUES_IOCTL, &vals);
// vals.bits & 1 is the current level
```

That's the entire API surface this driver supports: request, set, get. No edge/interrupt detection,
no pull-up/down bias, no debounce — all real `GPIO_V2` uAPI features that exist in the kernel but
this particular driver doesn't implement. If you (or ChatGPT) write code assuming those work, it'll
either silently no-op or fail the ioctl — the request/set/get path above is what's guaranteed.

### Building new programs

```sh
GCC=~/.riscv-pico-scratch/repo/buildroot/output/host/bin/riscv32-buildroot-linux-uclibc-gcc
$GCC -mabi=ilp32 -fPIE -pie -static -march=rv32ima -Os -s -Wl,-elf2flt=-r yourprogram.c -o yourprogram
```
`-fPIE -pie` are not optional — dropping them causes a runtime segfault, not a build error (this
bit a real program during development, see PLAN.md). Then inject it onto the SD card:
```sh
debugfs -w -R "write yourprogram usr/bin/yourprogram" /path/to/ROOTFS
debugfs -w -R "sif usr/bin/yourprogram mode 0100755" /path/to/ROOTFS
```
(`/path/to/ROOTFS` is the file directly on the SD card's FAT partition when you mount it on a PC —
not a loopback device, it's a plain file debugfs treats as an ext2 image.)

## 5. What's underneath, if you want the full story

- `PLAN.md` in the repo — the living state doc, has the complete history of what was built, why,
  and what broke along the way (the "GPIO access for the guest" and "PSRAM bus" sections are the
  relevant ones from this session).
- `docs/HARDWARE_SCHEMATIC.md` — the wiring/power situation on the breadboard, if you're adding
  more hardware.
- `buildroot-overlay/board/tiny-rv32ima/patches/linux/6.6.18/0004-gpio-driver.patch` — the actual
  kernel driver source, if you or ChatGPT want to extend it (add more pins, add pull-up/down
  support, add edge detection).
