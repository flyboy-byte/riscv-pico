# c4 for riscv-pico

A C compiler that runs on the Pico itself. You write a `.c` file in nano on the machine and run it
with `c4 file.c`. It compiles C to its own small bytecode and interprets it, rather than producing
RISC-V machine code.

## Where it came from

- **Original:** Robert Swierczek's [c4](https://github.com/rswier/c4), "C in four functions".
- **Fork used:** [tvlad1234/c4](https://github.com/tvlad1234/c4) at `30b22b7`. Its only change is
  `long` instead of `long long`, so it builds for 32-bit RISC-V.
- **License:** GPL-2.0, in `LICENSE`. This folder is licensed separately from the rest of the repo.

## What this copy adds (2026-09-14)

| Change | Why |
| --- | --- |
| `for (init; cond; step)` | Stock c4 only has `while`. Any of the three parts can be empty, so `for (;;)` works |
| `write(fd, buf, n)` built-in | Stock c4 can read files but not write them, so it couldn't set a GPIO pin |

`int` is 32-bit on this target. The new parser code doesn't use `for` itself, but the interpreter
now calls `write()`. Build this file with a normal C compiler or with this c4, not with stock c4,
which stops at the `write` call.

## Examples

| File | What it does |
| --- | --- |
| `hello.c` | Prints hello, world |
| `gpio_set.c` | `c4 gpio_set.c 1` or `0` sets guest GPIO line 0, Pico GP1, physical pin 2 |
| `gpio_toggle.c` | Toggles line 0 three times with a `for` loop. There's no sleep yet, so it's too fast to see |
| `t_for.c` | Checks nested, counting-down and empty `for` loops, plus `write` |

GPIO goes through the sysfs files, the same ones a shell script or Lua uses. Line 0 is
`/sys/class/gpio/gpio512`. Open a file for writing with flag `1`.

## What c4 doesn't have

No structs, no `switch`, no `break` or `continue`, no floating point, no preprocessor, and no sleep.
Declarations go at the top of a function. The built-in calls are `open`, `read`, `write`, `close`,
`printf`, `malloc`, `free`, `memset`, `memcmp` and `exit`. `printf` takes at most six arguments.

Output from `write` is unbuffered and `printf` output is buffered, so when output goes to a pipe,
`write` text can appear before earlier `printf` text. On the console it shows in order.

## Build for the Pico

Same flags as the other apps, run under bash:

```sh
GCC=~/.riscv-pico-scratch/repo/buildroot/output/host/bin/riscv32-buildroot-linux-uclibc-gcc
$GCC -mabi=ilp32 -fPIE -pie -static -march=rv32ima -Os -s -Wl,-elf2flt=-r -w c4.c -o c4
```

About 116 KB. For quick checks on a PC, `gcc -w -o c4 c4.c` builds a native copy.

## Verified

In the desktop harness on the no-network kernel and a copy of the real SD card: every example above
runs correctly, including GPIO writes seen by the simulated pin, and `c4 c4.c hello.c` compiles c4
with itself on the emulated CPU. Natively, c4 also compiles itself twice over and still runs hello.
Not yet run on the physical Pico.
