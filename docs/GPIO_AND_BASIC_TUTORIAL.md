# Playing with BASIC and GPIO on real hardware

Self-contained walkthrough for what's on the SD card right now (2026-08-29) and how to use it —
written so it also works as-is if you paste it to ChatGPT for help writing new GPIO code.

## 1. Flashing

**Not needed this round.** The firmware (`.uf2`) already on your Pico — `boards-v5` — already has
GPIO CSR support and is what the LED test was verified against. Only the SD card changed today
(new tools, a bugfix). Just put the SD card back in and boot. If you ever *do* need to reflash:
download `pico-rv32ima-pico.uf2` from the
[`pico-rv32ima-boards-v5`](https://github.com/flyboy-byte/riscv-pico/releases/tag/pico-rv32ima-boards-v5)
release, hold **BOOTSEL**, plug in the Pico, copy the `.uf2` onto the `RPI-RP2` drive it mounts as.

Connect over USB-CDC serial (`/dev/ttyACM0` or similar) at any baud, or use VGA/PS2 if wired.
**Boot waits for a keypress** before starting (`pwr_button()` gates on `console_available()`) —
press any key once connected.

## 2. What's on the SD card

| Program | What it is |
|---|---|
| `basic` | Tiny BASIC interpreter — **GOSUB bug fixed 2026-08-29, see §5** |
| `nano` | Real GNU nano 7.2, for writing files |
| `lua` | Real Lua 5.4.7 |
| `sysinfo` | System info (replaces the old `hello` smoke test, removed 2026-08-29) |
| `gpiotest` | GPIO one-shot smoke test (set line 0 high, read back — no delay loop, not a blink demo) |
| `gpiodetect` / `gpioinfo` / `gpioget` / `gpioset` / `gpiofind` / `gpiomon` | `libgpiod` tools — added 2026-08-29 |

Run any of them by name from the shell prompt.

## 3. BASIC

`apps/basic.c` in the repo has the full interpreter source. Supported:

```
PRINT, LET, IF ... THEN, GOTO, GOSUB, RETURN, FOR ... TO ... STEP / NEXT,
INPUT, LIST, RUN, NEW, END, REM
```

26 integer variables, `A`-`Z`. Line-based only — no cursor positioning.

**Interactive use**: run `basic`, type numbered lines, then `RUN`.

```
10 FOR I = 1 TO 5
20 PRINT I
30 NEXT I
40 END
RUN
```

**Writing a program in `nano` and running it non-interactively**: `basic` reads plain lines from
stdin, so shell redirection works. Write the numbered program in `nano`, **end the file with a
`RUN` line** (without it, `basic` just loads the program and exits at EOF — no output), save it,
then:

```sh
basic < myprogram.bas
```

**Leaving the interpreter**: `basic` has no quit command of its own — `Ctrl+C` (or `Ctrl+D` on
EOF) exits back to the shell.

## 4. GPIO

Four host pins are exposed to Linux as a real `/dev/gpiochip0` — standard `GPIO_V2` chardev uAPI,
no custom protocol. **LED-verified on real hardware 2026-08-29** (physical pin 2, via `gpiotest`).

### The 4 available lines

| Line offset | RP2040 GPIO | Physical Pico pin |
|---|---|---|
| 0 | GP1 | pin 2 |
| 1 | GP9 | pin 12 |
| 2 | GP15 | pin 20 |
| 3 | GP22 | pin 29 |

Fixed in firmware (`upstream/pico-rv32ima/pico-rv32ima/hal/hal_csr.h`, `gpio_csr_pins[]`).

**Wiring an LED**: positive leg through a ~330Ω resistor → your chosen physical pin, negative leg
→ any GND pin (3, 8, 13, 18, 23, 28, 33, 38).

**Wiring a button**: one leg → your chosen physical pin, other leg → GND. No internal pull-up/down
is implemented — wire an external pull resistor.

### Using it from the shell — no compiling required

`gpioset`/`gpioget`/`gpioinfo`/`gpiodetect` are now on the card. One-shot:

```sh
gpiodetect                    # confirm gpiochip0 shows up
gpioinfo gpiochip0             # see all 4 lines and their state
gpioset gpiochip0 0=1          # drive line 0 (pin 2) high
gpioget gpiochip0 0            # read line 0 back
```

**Blinking without a compiled binary** — a plain shell script, no C needed:

```sh
while true; do
  gpioset gpiochip0 0=1
  sleep 1
  gpioset gpiochip0 0=0
  sleep 1
done
```
Caveat: `gpioset` (libgpiod v1) releases the line back to its default state each time the process
exits, so there may be a brief flicker between calls depending on driver defaults — untested on
this hardware yet. If it's ugly, the fallback is a small C program that holds the line open for
the whole loop (pattern below).

### Writing and running your own shell script

```sh
cat > blink.sh << 'EOF'
#!/bin/sh
while true; do
  gpioset gpiochip0 0=1
  sleep 1
  gpioset gpiochip0 0=0
  sleep 1
done
EOF
chmod +x blink.sh
./blink.sh          # runs in foreground, Ctrl+C to stop
./blink.sh &         # backgrounds it — shell prompt returns immediately
```

**No `ps`/`kill` on this image** (confirmed — `CONFIG_PS`/`CONFIG_KILL`/`CONFIG_KILLALL` are unset
in busybox). Once you background something with `&`, there is no built-in way to list or kill it
individually — only rebooting/power-cycling reliably stops it. Don't background anything you don't
have another way to stop. (Adding `ps`/`kill` is a one-line buildroot config change + rebuild if
you ever want that — not done.)

### The raw C API, for writing your own program (or handing to ChatGPT)

```c
#include <fcntl.h>
#include <sys/ioctl.h>
#include <linux/gpio.h>

int fd = open("/dev/gpiochip0", O_RDWR);

struct gpio_v2_line_request req = {0};
req.offsets[0] = 0;              // 0-3, see the table above
req.num_lines = 1;
req.config.flags = GPIO_V2_LINE_FLAG_OUTPUT;   // or GPIO_V2_LINE_FLAG_INPUT
strcpy(req.consumer, "myprogram");
ioctl(fd, GPIO_V2_GET_LINE_IOCTL, &req);       // req.fd is now the line handle

struct gpio_v2_line_values vals = {0};
vals.mask = 1;
vals.bits = 1;                                  // 1 = high, 0 = low
ioctl(req.fd, GPIO_V2_LINE_SET_VALUES_IOCTL, &vals);

ioctl(req.fd, GPIO_V2_LINE_GET_VALUES_IOCTL, &vals);
// vals.bits & 1 is the current level
```

No edge/interrupt detection, no bias, no debounce implemented by this driver — request/set/get is
the guaranteed surface.

### Building new programs

```sh
GCC=~/.riscv-pico-scratch/repo/buildroot/output/host/bin/riscv32-buildroot-linux-uclibc-gcc
$GCC -mabi=ilp32 -fPIE -pie -static -march=rv32ima -Os -s -Wl,-elf2flt=-r yourprogram.c -o yourprogram
```
`-fPIE -pie` are not optional — dropping them causes a runtime segfault, not a build error. Then
inject it onto the SD card (the file directly on the FAT partition when mounted on a PC, not a
loopback device — `debugfs` treats it as a plain ext2 image):
```sh
debugfs -w -R "write yourprogram usr/bin/yourprogram" /path/to/ROOTFS
debugfs -w -R "sif usr/bin/yourprogram mode 0100755" /path/to/ROOTFS
```

## 5. What changed today (2026-08-29)

- **`apps/basic.c` GOSUB bug, fixed.** `do_gosub` was pushing the `GOSUB` line's own index onto
  the return stack instead of `pc + 1`. `RETURN` landed back on the `GOSUB` statement itself, not
  the line after it, so any `FOR ... GOSUB ... NEXT` loop ran forever (never reached `NEXT`, `i`
  never incremented). One-line fix: `gosub_stack[gosub_sp++] = pc + 1;`. Rebuilt and injected onto
  the SD card.
- **`libgpiod` tools added** (`gpiodetect`/`gpioinfo`/`gpioget`/`gpioset`/`gpiofind`/`gpiomon`) —
  `BR2_PACKAGE_LIBGPIOD=y` + `BR2_PACKAGE_LIBGPIOD_TOOLS=y` in the buildroot config, full rootfs
  rebuild, tools injected onto the existing SD card ROOTFS.
- **`hello` removed** (redundant with `sysinfo`).
- **Lua and a GPIO C binding**: stock Lua 5.4 has no `ioctl()`/FFI, so it can't touch
  `/dev/gpiochip0` directly. `os.execute("gpioset gpiochip0 0=1")` works today with no further
  build. A real `gpio.output()`/`pin:set()` Lua C module is documented as an option in PLAN.md, not
  built — skip it unless it's actually needed, `os.execute` already covers scripting GPIO from Lua.

## 6. Full story, if you want it

- `PLAN.md` — living state doc, "GPIO access for the guest" and "Finishing GPIO" sections.
- `docs/HARDWARE_SCHEMATIC.md` — wiring/power situation on the breadboard.
- `buildroot-overlay/board/tiny-rv32ima/patches/linux/6.6.18/0004-gpio-driver.patch` — the kernel
  driver source, if extending it (more pins, pull-up/down, edge detection).
