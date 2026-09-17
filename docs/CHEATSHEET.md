# Cheat sheet — what's on the machine and how to use it

Everything here runs **on the Pico**, typed at its own shell. A shorter copy, sized for the 53-column
screen, lives on the card: `nano -v /root/help.txt` pages through it (Ctrl+V next page, Ctrl+X quit).

Line 0 of the GPIO chip is **Pico GP1, physical pin 2**. The four guest-usable lines are:

| Line | Pico GPIO | Physical pin | sysfs name |
| --- | --- | --- | --- |
| 0 | GP1 | 2 | `gpio512` |
| 1 | GP9 | 12 | `gpio513` |
| 2 | GP15 | 20 | `gpio514` |
| 3 | GP22 | 29 | `gpio515` |

---

## GPIO

Two interfaces, both real Linux. Only one can hold a line at a time, so if `gpioget` says the line
is busy, something exported it through sysfs first. Release it with:

```sh
echo 512 > /sys/class/gpio/unexport   # 513, 514, 515 for the other lines
```

`blink.lua` and `gpio_toggle.c` release the line when they finish. `gpio_set.c` leaves it exported
so the pin holds its level.

`export` and `unexport` are write-only, so `cat /sys/class/gpio/export` says "Permission denied".
That's normal. `ls /sys/class/gpio` shows what exists; `gpio512` only appears once exported.

```sh
# the modern chardev interface
gpioinfo gpiochip0              # list the four lines and who holds them
gpioset gpiochip0 0=1           # line 0 high
gpioget gpiochip0 0             # read line 0

# the sysfs interface — what shell scripts use
echo 512 > /sys/class/gpio/export
echo out > /sys/class/gpio/gpio512/direction
echo 1   > /sys/class/gpio/gpio512/value
cat        /sys/class/gpio/gpio512/value
```

`gpiotest` is a one-shot smoke test: it claims line 0, sets it high, reads it back, exits.

---

## Lua

Stock Lua 5.4.7 plus a `sys` library built into the binary, because stock Lua can't sleep and can't
read single keypresses.

```sh
lua /root/blink.lua             # blink line 0 ten times
lua /root/blink.lua 3           # or three times
lua                             # interactive
```

| Call | What it does |
| --- | --- |
| `sys.sleep(seconds)` | Blocks without burning CPU. Fractions fine: `sys.sleep(0.2)` |
| `sys.ms()` | Milliseconds since boot, as an integer, for timing |
| `sys.raw(true)` / `sys.raw(false)` | Key-at-a-time input and back. Returns false if there's no terminal |

Writing a pin from Lua is just file I/O:

```lua
local f = io.open("/sys/class/gpio/gpio512/value", "w")
f:write("1")
f:close()
```

**`os.execute` and `io.popen` do not work here.** They need `fork()`, which a no-MMU machine
doesn't have. Do the work in Lua instead of shelling out.

---

## c4 — a C compiler that runs on the Pico

Compiles C to its own bytecode and runs it immediately. No linker, no object files.

```sh
c4 /root/hello.c                # hello world
c4 /root/gpio_set.c 1           # set line 0 high, or 0 for low
c4 /root/gpio_toggle.c          # toggle line 0 with a for loop
c4 /root/c4.c /root/hello.c     # c4 compiling itself, then running hello
c4 -s /root/hello.c             # show the bytecode it generated
```

Write your own with nano, then run it. The language is a C subset:

| Has | Doesn't have |
| --- | --- |
| `char`, `int`, pointers, arrays | structs, `switch`, `break`, `continue` |
| `if`, `else`, `while`, `for`, `return` | floating point, the preprocessor |
| `open read write close printf malloc free memset memcmp exit` | everything else from libc |

Declarations go at the top of a function. `printf` takes at most six arguments. `for` and `write`
were added by this project; `write` is what lets a c4 program set a GPIO pin.

---

## Tiny BASIC

```sh
basic
```

```basic
10 FOR I = 1 TO 5
20 PRINT "hello ", I
30 NEXT I
RUN
LIST
BYE
```

`BYE` leaves BASIC and returns to the shell. `EXIT`, `QUIT` and `SYSTEM` do the same thing. Also
supported: `LET`, `IF ... THEN`, `GOTO`, `GOSUB` / `RETURN`, `INPUT`, `NEW`, `END`, `REM`.

---

## Minesweeper

```sh
lua /root/mines.lua             # 16 x 12 with 25 mines
lua /root/mines.lua 20 14 40    # width, height, mines
```

| Key | Does |
| --- | --- |
| arrows | move the cursor |
| space | dig |
| `f` | flag or unflag |
| `r` | restart |
| `q` | quit |

The first dig is never a mine. Flagged cells can't be dug by accident.

---

## The machine itself

```sh
sysinfo                         # what this thing is, at a glance
free                            # memory
uptime
dmesg | tail                    # boot messages... except `tail` isn't installed, so just `dmesg`
nano notes.txt                  # real GNU nano
sync                            # ALWAYS before pulling power
halt                            # cleaner still
```

**Pull the power without `sync` or `halt` and the root filesystem can be damaged.** That already
happened once and left a broken directory entry behind.

### Commands that are not installed

`head`, `tail`, `grep`, `sed`, `awk`, `wc`, `cp`, `mv`, `chmod`, `ps`, `kill`, `date`, `stty`, `vi`,
`df`. Busybox was trimmed to save space. Adding some back means rebuilding the rootfs.

### nano and the 53×30 screen

Needs firmware `pico-rv32ima-boards-v6` or later and card `sdcard-v2` or later. On v5 firmware,
nano over VGA is unusable.

The card sets the console to 53 columns by 30 rows at boot, so nano fits. This nano build can't
soft-wrap, so a long line scrolls sideways when the cursor is on it; a `>` at the right edge means
the line goes on past the screen.

| Key | In nano |
| --- | --- |
| Ctrl+O / Ctrl+X | save / quit |
| Ctrl+K / Ctrl+U | cut line / paste |
| Ctrl+W | search |
| Ctrl+V / Ctrl+Y, or Page Down / Page Up | next / previous page |
| Home / End, Delete | start / end of line, delete forward |

```sh
ttysize                         # prints "30 53"
ttysize 24 80                   # over USB serial with a normal-sized terminal window
nano -x notes.txt               # hide the two help lines for two more rows of text
```

If a full-screen program ever leaves the screen in a mess, `clear` blanks it.

---

## Away from the Pico

```sh
# serial console, when a PC is attached over USB
screen /dev/ttyACM0 115200      # the device number changes after each reflash

# power it with no PC: breadboard supply 5 V rail into VSYS, pin 39
# never feed 3.3 V into pin 36 — that's the regulator's output, not an input
```

Card layout is three files at the root of a FAT32 card: `IMAGE`, `DTB`, `ROOTFS`. Firmware is a
`.uf2` copied while holding BOOTSEL. Both come from the
[releases page](https://github.com/flyboy-byte/riscv-pico/releases).
