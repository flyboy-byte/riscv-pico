# riscv-pico

A workbench for running 32-bit RISC-V Linux on a Raspberry Pi Pico, by emulating a RISC-V CPU on
the RP2040 with SPI PSRAM as system memory and an SD card holding the kernel and rootfs.

**Status: staging.** Both upstream projects are vendored here, intact and buildable. Nothing has
been merged, ported, or modified yet. That's deliberate — this repo exists so the two can be
compared and hacked on side by side before any of it gets mashed together.

## What's in here

| Path | Upstream | Notes |
| --- | --- | --- |
| `upstream/pico-rv32ima/` | [tvlad1234/pico-rv32ima](https://github.com/tvlad1234/pico-rv32ima) | Actively maintained. RP2040 **and** RP2350, VGA console, snapshot support. |
| `upstream/pico-rv32ima/tiny-rv32ima/` | [tvlad1234/tiny-rv32ima](https://github.com/tvlad1234/tiny-rv32ima) | The emulator core, extracted into a library by upstream's 2025 refactor. |
| `upstream/pico-linux/` | [ElectroBoy404NotFound/pico-linux](https://github.com/ElectroBoy404NotFound/pico-linux) | A 2023 fork that went its own way. ST7735 LCD console, 2–4 PSRAM chips, SDIO. Last touched Feb 2024. |

All three are `git subtree`s with full upstream history, so `git log -- upstream/<x>` works and
upstream changes can still be pulled. See [CLAUDE.md](CLAUDE.md) for the exact commands.

Everything ultimately descends from [CNLohr's mini-rv32ima](https://github.com/cnlohr/mini-rv32ima).

## Building

Needs the Pico SDK. A shallow clone with just the tinyusb submodule is ~65 MB:

```sh
git clone -b 2.1.1 --depth 1 https://github.com/raspberrypi/pico-sdk.git ~/pico-sdk
git -C ~/pico-sdk submodule update --init --depth 1 lib/tinyusb
```

Then, from either project's directory:

```sh
cmake -B build -DPICO_SDK_PATH=$HOME/pico-sdk -DPICO_BOARD=pico   # pico2 for RP2350
cmake --build build -j$(nproc)
```

Output is `build/pico-rv32ima/pico-rv32ima.uf2` (~140 KB) in both. Flash by holding BOOTSEL while
plugging in the Pico — it mounts as a USB drive called `RPI-RP2` — then copy the `.uf2` onto it.

Verified building clean with GCC 16.1 / SDK 2.1.1, 2026-08-15.

## Kernel images

`pico-rv32ima` wants three files in the root of a FAT16/FAT32 SD card — `IMAGE`, `DTB`, `ROOTFS` —
from the [buildroot-tiny-rv32ima](https://github.com/tvlad1234/buildroot-tiny-rv32ima) releases:

```sh
gh release download v1.0 --repo tvlad1234/buildroot-tiny-rv32ima --pattern images.zip
```

`pico-linux` instead wants a single `Image` file, and already ships one at
`upstream/pico-linux/linux/Image`.

**These images do not boot under stock desktop `mini-rv32ima`** — see [CLAUDE.md](CLAUDE.md) for
why, and what to do about it.

## Licenses

Upstream code retains its original licensing — MIT / Apache-2.0 / BSD-3, see the `LICENSE` file in
each subtree. Credit to tvlad1234, ElectroBoy404NotFound, CNLohr, and xhackerustc.
