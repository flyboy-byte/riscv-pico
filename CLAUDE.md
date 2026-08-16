# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

**Status: staging (2026-08-15).** Both upstreams are vendored and buildable, and a desktop harness
(`harness/`) boots the real `tiny-rv32ima` emulator to a Linux shell with no hardware. Nothing
merged, ported, or flashed to hardware yet. See [PLAN.md](PLAN.md) for current state and what's
next — that's the living document, this one is orientation.

## What this repo is

A workbench for getting RISC-V Linux onto a Raspberry Pi Pico. Two upstream projects solving the
same problem are vendored side by side so they can be compared, hacked, and eventually combined.
The intended direction (see PLAN.md) is **fork `pico-rv32ima`, port `pico-linux`'s features into
it** — not a 50/50 merge.

Hardware this is actually being built for: **Pico (RP2040)**, **ST7735 128×160 LCD**, a couple of
hand-soldered **SPI PSRAM chips on DIP adapters** of uncertain condition, and an SD card.

## Layout

Everything under `upstream/` is a `git subtree` with full upstream history. `pico-linux` is still
pristine. `pico-rv32ima` and its `tiny-rv32ima` subtree are not — the multi-chip PSRAM port (see
PLAN.md) edits them directly; that was a deliberate D-003 exception, not scope creep. Future
`git subtree pull`s on `pico-rv32ima`/`tiny-rv32ima` will need real merges from here on.

```
upstream/pico-rv32ima/                 tvlad1234/pico-rv32ima      (maintained; RP2040+RP2350, VGA)
upstream/pico-rv32ima/tiny-rv32ima/    tvlad1234/tiny-rv32ima      (emulator core library)
upstream/pico-linux/                   ElectroBoy404NotFound/...   (2023 fork; LCD, multi-chip PSRAM)
```

Pulling upstream changes later:

```sh
git subtree pull --prefix=upstream/pico-rv32ima https://github.com/tvlad1234/pico-rv32ima main
git subtree pull --prefix=upstream/pico-rv32ima/tiny-rv32ima https://github.com/tvlad1234/tiny-rv32ima main
git subtree pull --prefix=upstream/pico-linux https://github.com/ElectroBoy404NotFound/pico-linux main
```

**`tiny-rv32ima` is a subtree, not a submodule.** Upstream has it as a submodule; the pointer was
removed (commit "Drop tiny-rv32ima submodule pointer") and replaced with a real subtree at the same
path, so `pico-rv32ima`'s CMake reference `../tiny-rv32ima/...` still resolves. Don't re-add
`.gitmodules` or run `git submodule update` here — there are no submodules.

## Commands

```sh
# SDK (once) — ~65 MB shallow
git clone -b 2.1.1 --depth 1 https://github.com/raspberrypi/pico-sdk.git ~/pico-sdk
git -C ~/pico-sdk submodule update --init --depth 1 lib/tinyusb

# build either project, from its own directory
cmake -B build -DPICO_SDK_PATH=$HOME/pico-sdk -DPICO_BOARD=pico
cmake --build build -j$(nproc)
```

Verified 2026-08-15: `upstream/pico-rv32ima` builds clean on GCC 16.1 / SDK 2.1.1 → 140 KB `.uf2`.
There are no tests; verification is flashing and reading the console boot log.

## How the two differ

Assumptions do not transfer between them.

| | `pico-rv32ima` | `pico-linux` |
| --- | --- | --- |
| Config | `pico-rv32ima/hw_config.h` + `vm_config.h` | `pico-rv32ima/config/rv32_config.h` |
| Emulator core | `tiny-rv32ima/` subtree | vendored in `pico-rv32ima/emulator/` |
| PSRAM | 1 chip, 8 MB | 2 chips, 16 MB (supports 3–4) |
| SD | Petit FatFs, SPI only | full FatFS, SPI **or** SDIO |
| Console | USB-CDC + VGA (PIO) + PS/2 | UART + USB-CDC + ST7735 LCD + PS/2 |
| SD contents | `IMAGE` + `DTB` + `ROOTFS` | single `Image` |
| Targets | RP2040 + RP2350 | RP2040 only |
| Upstream | active (Aug 2025) | abandoned (Feb 2024) |

Shared: core 0 sets clocks and loops on `console_task()`; **core 1 runs the emulator**. Both are
`copy_to_ram` binaries. **Both deliberately overvolt and overclock** (400 MHz / 438 MHz) — that is
load-bearing for emulator throughput, not a bug. Flag it, don't "fix" it.

## Things that will bite you

- **Config headers are the truth, not the READMEs.** Pin assignments are compiled in, and the
  READMEs disagree with the headers in places.
- **`rv32_config.h` has `#if` interlocks.** Its "Config Checks" block `#error`s if `EMULATOR_RAM_MB`
  exceeds the enabled chip count, and silently force-disables the LCD console for 3–4 chip setups.
  Read the bottom of the file before changing a knob.
- **`initPSRAM()` is a chip tester.** It reads each chip's JEDEC ID and checks the "known good die"
  byte `0x5D`, returning `-1`/`-2` for the failing chip or a positive SPI clock in MHz on success
  (`upstream/pico-linux/pico-rv32ima/psram/psram.c`). This is the fastest way to grade
  hand-soldered chips. It proves the chip responds — it does not walk all 8 MB.
- **`PSRAM_SPI_SPEED 52` is optimistic for flying leads.** Drop to ~20 MHz for bring-up; a chip that
  fails at 52 and passes at 20 is a signal-integrity problem, not a dead chip.
- **`pico-linux` vendors ~42k lines of third-party library** (`no-OS-FatFS-SD-SPI-RPi-Pico`,
  `pico-displayDrivs`, `pico-ps2Driv`) — about 95% of it by volume. Actual original code in each
  project is ~2,000 lines. Prefer changing the app layer.

## Desktop testing

`harness/` at the repo root compiles the real `tiny-rv32ima` source
(`upstream/pico-rv32ima/tiny-rv32ima/{emulator,cache,pff}/*.c`, unmodified) against desktop
replacements for the hardware HAL headers, and boots to a Linux shell natively on this machine —
no Pico, no PSRAM chips, no SD card needed. Build/run instructions and how it works are in
PLAN.md's "Desktop harness" section. `harness/desktop_terminal.py` is a real desktop terminal app
(PyQt6 + `pyte`, real VT100/ANSI cursor handling, not a browser page) that watches it live and lets
you type into it — see PLAN.md's "Desktop terminal app" section.

**A real RISC-V cross-compiler for this target has been built and proven** (compile → inject into
rootfs → boot → run, live in the web console). It's not checked into the repo (lives in ephemeral
build scratch, has to be rebuilt per session) — the exact recipe, plus two hard-won gotchas about
not running concurrent `make toolchain` invocations, are in PLAN.md's "Cross-compile toolchain"
section. Don't rediscover this from scratch — read that section first.

Why this exists and not something built on stock `cnlohr/mini-rv32ima`: that builds natively in
seconds too, and boots cnlohr's own images fine, but **not either project's** — `tiny-rv32ima` adds
custom CSRs (`tiny-rv32ima/emulator/emulator.c:396-470`, `0x150`–`0x155` for the `root=fe00` block
device, `0x170` for hibernate) that stock mini-rv32ima doesn't implement, so the kernel comes up
with no root device and dies silently before the console is usable. `harness/` sidesteps that by
building the actual `tiny-rv32ima` core instead of stubbing around it.

## Scope fence

This is a hardware bring-up and porting workbench. Don't turn it into a framework, a build system,
or a general-purpose emulator project. Don't add CI, package manifests, or abstraction layers that
nobody asked for. The upstream trees stay pristine until PLAN.md says a port has started.
