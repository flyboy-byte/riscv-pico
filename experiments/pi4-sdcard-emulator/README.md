# Pi 4 as a fake SD card

**Status: a working proof of concept, not a path to booting Linux. Read "The honest
ceiling" before assuming this can replace a real SD card.** (2026-08-26)

## What this is

While waiting on a real SD-card SPI breakout module to arrive for `riscv-pico`'s hardware
bring-up, we tried using a spare Raspberry Pi 4B as a stand-in "fake SD card" — wiring it
directly to the Pico and making it answer the exact SD-over-SPI protocol
`upstream/pico-rv32ima/tiny-rv32ima/pff/mmcbbp.c` speaks. Built jointly with another Claude
session ("pi-05") physically connected to the Pi over a private wired link, working from the
`riscv-pico` side.

**It worked**, further than the one directly comparable precedent we could find online (a
forum thread where someone else tried the same Pi4-as-SPI-slave idea and never got
bidirectional communication working at all). We got: the full 5-command SD init handshake
succeeding reliably, a real 512-byte sector read landing byte-perfect with a working CRC16
integrity check and automatic retry on corruption. Nice result for an afternoon of curiosity.

## The honest ceiling

Individual commands and individual sector reads work well most of the time. But actually
booting Linux needs roughly **126,000 sequential sector reads** (a ~3.2MB kernel image plus a
~60MB rootfs, at 512 bytes/sector) with **zero tolerance for a single uncaught bad read** —
`mmcbbp.c`/`pff.c` have no retry logic of their own at that layer. Even at a genuinely good
per-sector success rate, the odds of all ~126,000 landing clean in one boot attempt are
essentially zero. This is a real architectural limit of bit-banging an SPI *slave* in
software on stock (non-RTOS) Linux — not something more tuning fixes. Don't expect this to
ever actually boot the full rootfs. It's a working demonstration, not a replacement for real
hardware.

## What we ruled out first: BSC hardware slave mode

The Pi 4's BCM2711 has a real *hardware* SPI-slave capability (the BSC peripheral,
accessible via `pigpio`'s `bsc_xfer`) — not a hack, genuine silicon support with mainline
Linux driver precedent. We tried this first (`sdcard_emu.py`'s own `main()` still runs this
path standalone). **It never worked**: total silence, confirmed via `edge_probe.py` that real
electrical signals *were* reaching the Pi's pins correctly, so it wasn't wiring — the BSC
peripheral itself just wasn't engaging with an external master. This matches known community
reports (a well-known `pigpio` contributor: *"I could never get the BSC to work in SPI slave
mode"*) and BSC hardware slave mode has separately been reported buggy/removed on the Pi's
official forums for this exact use case. **Don't retry the BSC-hardware path** — it's a
confirmed dead end on this hardware, not something we gave up on prematurely. The working
path is the C bit-bang transport described below.

## Wiring

Pico is SPI master, Pi is slave/"card". Both sides are 3.3V logic — no level shifting needed.

| Signal | Pico (physical pin, GPIO) | Pi 4B (physical pin, GPIO) |
| --- | --- | --- |
| Clock | pin 4, GP2 | → pin 35, GPIO19 (SCLK) |
| Master→Slave | pin 5, GP3 | → pin 38, GPIO20 (MOSI) |
| Slave→Master | pin 6, GP4 | ← pin 12, GPIO18 (MISO) |
| Chip select | pin 1, GP0 | → pin 40, GPIO21 (CE) |
| GND | pin 3 | — pin 39 |

## Files

- `sdcard_emu.py` — the protocol state machine (`SDEmulator`), transport-agnostic. Reused
  unchanged by both the (dead-end) BSC path and the (working) bit-bang path. Also runnable
  standalone against BSC if anyone wants to re-attempt that route on different hardware.
- `bitbang_slave.c` — the actual working transport. Links `libpigpio` **directly** (not the
  `pigpiod` daemon — daemon IPC latency alone exceeds a bit period at any usable clock rate).
  A tight busy-poll loop reacting to real GPIO edges in real time; only handles bit-level
  timing, nothing protocol-aware.
  Includes `SCHED_FIFO` + `mlockall` hardening (helps some, doesn't eliminate jitter — this
  is still stock Linux, not an RTOS) and a fix for a real bug found along the way: stale
  unread response bytes left in the pipe from an aborted/retried transaction getting
  misread as the response to a later, unrelated command — now flushed on every fresh CE
  assertion.
- `bitbang_bridge.py` — glues `bitbang_slave`'s byte stream to `SDEmulator`, run this one.
- `test_sdcard_emu.py` — pure-software bench test, no hardware/pigpio needed. Caught a real
  bug on first run (write handler slicing the wrong byte range). CRC16 is cross-checked
  against Python's independent stdlib implementation (`binascii.crc_hqx`), not tested against
  itself.
- `edge_probe.py` — cheap diagnostic used to confirm real electrical activity was reaching
  the Pi's pins (ruling wiring in/out) before committing to the bigger bit-bang rewrite.

The Pico-side test client used to exercise all of this lives in the main repo at
`firmware/sdtest/` — a standalone diagnostic firmware (not the real `pico-rv32ima` build)
that runs the SD init handshake and a CRC-checked, retrying `CMD17` sector read, with verbose
logging over USB-CDC serial.

## Running it

One-time setup on the Pi (the `pigpio` **C library** isn't packaged for this Debian image —
only the Python bindings are; the library itself has to be built from source):

```sh
git clone --depth 1 https://github.com/joan2937/pigpio && cd pigpio && make -j4 && sudo make install
```

Build:

```sh
gcc -O2 -Wall -o bitbang_slave bitbang_slave.c -lpigpio -lrt -pthread
```

Build the FAT-formatted disk image it serves (needs `mtools`; same recipe as the main repo's
README quickstart):

```sh
dd if=/dev/zero of=disk.img bs=1M count=80
mformat -F -i disk.img ::
mcopy -i disk.img Image        ::IMAGE
mcopy -i disk.img dtb          ::DTB
mcopy -i disk.img rootfs.ext2  ::ROOTFS
```

Run (every time — `pigpiod` must be stopped first, `gpioInitialise()` needs exclusive
hardware access, and `bitbang_bridge.py` needs root for GPIO register access):

```sh
sudo killall pigpiod 2>/dev/null
sudo python3 bitbang_bridge.py disk.img
```

Set `BB_DEBUG=1` in the environment for verbose per-byte tracing (very high volume — only
useful for debugging the transport itself).
