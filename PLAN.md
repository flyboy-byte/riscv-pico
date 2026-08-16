# PLAN.md

Living state document. Current reality, not a task list.

**Status: full cross-compile pipeline proven — wrote, compiled, and ran real programs (hello world,
Tiny BASIC) in the harness. Multi-chip PSRAM port done in software. Desktop terminal app (PyQt6 +
pyte) replaced the old browser console — real cursor support, unblocks full-screen apps. Toolchain
available as a prebuilt release download, no rebuild needed. Real hardware parked until further
notice. (2026-08-15)**

**Next session starts here:** `gh release download toolchain-v1 --pattern '*.tar.gz'` to get the
compiler (no rebuild needed). Tiny BASIC is done (see `apps/basic.c`); text editor, Lua, or a
terminal game are still open — the console can now render full-screen apps correctly (desktop
terminal app fixed this) but that's not yet verified against a real full-screen program.

**Desktop harness works.** `harness/` boots the real tiny-rv32ima emulator (custom CSRs and all) to
a Linux shell prompt natively on this machine — see "Desktop harness" section below for how to run
it. No hardware needed for any future PSRAM/cache/emulator-core iteration.

## Where things actually stand

- ✅ Pico SDK 2.1.1 at `~/pico-sdk` (shallow + tinyusb only, 65 MB). Builds clean on GCC 16.1.
- ✅ `upstream/pico-rv32ima` builds → `build/pico-rv32ima/pico-rv32ima.uf2`, 140 KB. **Flashable now.**
- ✅ Both upstreams vendored as subtrees with full history. `tiny-rv32ima` converted from submodule
  to subtree at the same path, so upstream CMake paths still work.
- ✅ Kernel images for `pico-rv32ima` downloaded and inspected (`images.zip` v1.0, 2025-08-27:
  `Image` 2.2 MB, `dtb` 2 KB, `rootfs` 60 MB ext2).
- ❌ Nothing flashed to hardware yet — **parked, don't pick back up without being asked.**
- ✅ Multi-chip PSRAM port — `pico-linux`'s address-based chip-select logic ported into
  `pico-rv32ima`. Compiles clean for real RP2040 target in both 1-chip and 2-chip configs; default
  config unchanged (1 chip, 8 MB) so nothing about current hardware behavior changed. See below.
- ✅ Desktop harness — boots to a Linux shell, no hardware. See below.

## Hardware on hand

Pico (RP2040) · ST7735 128×160 LCD · a couple of SPI PSRAM chips hand-soldered to DIP adapters,
**condition unverified** · SD card.

The PSRAM chips are the main unknown. Previous attempt (Sept 2024) got as far as installing the SDK
and configuring a build, then stalled — the gap was not knowing what happens after wiring, not the
wiring itself.

## Direction of travel

**Fork `pico-rv32ima`, port `pico-linux`'s features into it.** Not a 50/50 merge.

Reason: upstream's 2025 refactor carved the project into a `hal/` layer of five one-line-macro
headers. That's a deliberate extension point. Merging the other direction means dragging a 2023
codebase and 42k lines of vendored library forward over it.

What's worth porting from `pico-linux`:

| Feature | Why | Effort |
| --- | --- | --- |
| Multi-chip PSRAM (16 MB) | two chips on hand | **easy** — see seam below |
| ST7735 console | the display that was bought | medium — needs `hal_console` + terminal glue, plus vendoring ST7735/GFX drivers |
| SDIO SD card | faster, SPI already works | skip for now |

Kept from upstream for free: RP2350 support, VGA console, snapshot/hibernate, rootfs as a block
device, and the small `pff` instead of the 42k-line FatFS.

### The multi-chip PSRAM port (done, 2026-08-15, `port/multi-chip-psram` branch)

Ported `pico-linux`'s address-based chip-select logic into `pico-rv32ima`. This is the first edit
to the vendored upstream trees — D-003's stated exception point. Split the same way
`pico-rv32ima`'s existing HAL already separates hardware from protocol, rather than copying
`pico-linux`'s `accessPSRAM()` wholesale (which mixes both in one function):

- `pico-rv32ima/hw_config.h` — `PSRAM_TWO_CHIPS` (already existed as an unused stub, now wired up),
  `PSRAM_SPI_PIN_S2` (GPIO14, free pin), `PSRAM_CHIP_SIZE_BYTES` (8 MB, both known-good chip models
  are 8 MB). Added a config-check block (`#include`s `vm_config.h` to compare `EMULATOR_RAM_MB`
  against enabled chip capacity, `#error`s on mismatch) — same pattern `pico-linux` uses, flagged in
  this file as worth adopting back when this repo was first written.
- `pico-rv32ima/main.c` — GPIO init for `PSRAM_SPI_PIN_S2`, gated behind `#if PSRAM_TWO_CHIPS`.
- `pico-rv32ima/hal/hal_psram.h` — `psram_select`/`psram_deselect` now take the *full* address and
  pick the CS pin (`psram_chip_cs()`, a one-line macro). This header owns pin muxing only.
- `tiny-rv32ima/psram/psram.c` — `psram_access()` now computes a chip-local address
  (`addr % PSRAM_CHIP_SIZE_BYTES` when two chips are enabled) for the command bytes it sends,
  separate from the full address it passes to `psram_select()`. `psram_init()` now loops over each
  enabled chip, resetting and KGD-checking each individually (previously only ever touched chip 1) —
  matters for correctness once a second chip is wired, each physical chip needs its own reset over
  its own CS line.

**Verified, not just written:**
- Harness (single flat malloc'd buffer, `harness/hal_psram.h` updated to match the new
  `psram_select(addr)`/`psram_deselect(addr)` signatures) still boots clean after the refactor —
  confirms the single-chip path is behaviorally unchanged.
- Real RP2040 target (`cmake --build`) compiles clean in **both** configs: default
  (`PSRAM_TWO_CHIPS 0`, 8 MB) produced a byte-identical 140800-byte `.uf2` to before the port,
  proving the default path truly didn't change; `PSRAM_TWO_CHIPS 1` + `EMULATOR_RAM_MB 16` also
  compiles clean (141312 bytes).
- The config-check guard actually fires: set `EMULATOR_RAM_MB 16` with `PSRAM_TWO_CHIPS 0` and got
  a compile-time `#error`, not a silent address-wrap bug.
- **Not verified and can't be from a desktop:** the real SPI chip-select GPIO behavior. That needs
  a second physically-wired, graded-good chip — hardware is parked, so this stays unverified until
  hardware work resumes.
- Repo currently sits back on the safe default (1 chip, 8 MB) — nothing about current wiring's
  expected behavior changed by this port landing.

## Next steps, in order

Ordered so the risky unknowns resolve first and nothing depends on the display working.

1. **Bring-up over USB serial, one PSRAM chip only.** Don't wire the LCD yet. Set
   `CONSOLE_CDC 1`, `CONSOLE_UART 0`, LCD off, one chip, `PSRAM_SPI_SPEED` ~20 MHz. Flash, open a
   serial terminal, chase `PSRAM init OK!`. This isolates the one thing that's genuinely uncertain.
2. **Grade the chips.** Rotate each hand-soldered chip through the same known-good wiring. One
   flash, and the whole batch gets individually tested instead of guessed at.
3. **First Linux boot.** SD card FAT32, `IMAGE` + `DTB` + `ROOTFS` in the root. ~30 s to console.
4. **Second chip → 16 MB.** This is where the multi-chip PSRAM port lands.
5. **ST7735 console last.**

Optional but high-leverage, can slot in any time after step 3: **the desktop harness**
(see CLAUDE.md) — makes steps 4–5 iterable without touching hardware.

### Desktop harness (built and working, 2026-08-15)

Chips are hand-soldered and buried; hardware bring-up was a hassle to start with, so the desktop
harness got built *before* hardware step 1, not after step 3. It compiles the real `tiny-rv32ima`
source (`emulator.c`, `cache.c`, `pff.c`) from `upstream/pico-rv32ima/tiny-rv32ima/` — unmodified,
D-003 still holds — against a new set of desktop `hal_*.h` headers in `harness/`, replacing only
`psram.c`'s and `pff`'s hardware backends:

- `harness/hal_console.h`, `hal_csr.h`, `hal_timing.h` — trivial stdio/no-op/`clock_gettime` stubs.
- `harness/console.c`/`.h` — desktop console: stdio putc/puts, non-blocking stdin via `select()`.
- `harness/hal_psram.h` — the one with real logic. `psram.c` drives PSRAM through exactly four
  macros (`select`/`deselect`/`spi_write`/`spi_read`); this reimplements them as a tiny state
  machine over one static `psram_mem[EMULATOR_RAM_MB * 1MB]` array. First `spi_write` after
  `select()` is always the cmd+24-bit-address prefix (parsed from bytes 0 and 1-3); everything after
  is payload, memcpy'd to/from the array at that address. One special case: cmd `0x9F` (READ_ID)
  makes the read return byte 1 = `0x5D` so `psram_read_kgd()` passes. Verified: only `psram.c`
  includes this header, so the file-static state is safe.
- `harness/diskio.c` + `harness/harness_disk.h` — **skips `pff/mmcbbp.c` (the real MMC-over-SPI
  protocol) entirely.** `pff.c` only needs `disk_initialize`/`disk_readp`/`disk_writep`, which don't
  care how they're backed — these serve 512-byte sectors straight out of a raw FAT-image file via
  `fseek`/`fread`/`fwrite`. `main.c` opens the image path from `argv[1]` into `harness_disk_img`
  before calling `vm_init_hw()`.
- `harness/vm_config.h` — trimmed copy of `pico-rv32ima/pico-rv32ima/vm_config.h` (8 MB RAM,
  `IMAGE`/`DTB`/`ROOTFS` filenames, same cache sizing). Both `emulator.c` and `cache.c` need it.
- `harness/main.c` — `vm_init_hw()` then loops `start_vm(EMU_GET_SD)`, same as core 1 on real
  hardware.

**Build:**
```sh
TINY=upstream/pico-rv32ima/tiny-rv32ima
gcc -O1 -g -Wall -I harness -I $TINY/emulator -I $TINY/psram -I $TINY/cache -I $TINY/pff \
  harness/main.c harness/console.c harness/diskio.c \
  $TINY/emulator/emulator.c $TINY/cache/cache.c $TINY/psram/psram.c $TINY/pff/pff.c \
  -o harness/rv32harness
```
Only warnings from upstream's own code (a const-qualifier discard, some `int`/`UINT` pointer-sign
mismatches on `pf_write`/`pf_read` calls) — harmless, not touched since upstream stays pristine.

**Disk image (not checked in — build locally with `mtools`, no root needed):**
```sh
dd if=/dev/zero of=disk.img bs=1M count=80
mformat -F -i disk.img ::
mcopy -i disk.img <path-to>/Image ::IMAGE
mcopy -i disk.img <path-to>/dtb   ::DTB
mcopy -i disk.img <path-to>/rootfs ::ROOTFS
```
`Image`/`dtb`/`rootfs` come from `gh release download v1.0 --repo tvlad1234/buildroot-tiny-rv32ima
--pattern images.zip` (per README).

**Run:** `./harness/rv32harness disk.img` — boots straight to a `~ #` busybox shell in a couple
seconds, full kernel log, no keypress wait (`pwr_button()` is hardwired true for desktop). Shell
builtins work. External exec (`ls`, `cat`, etc.) fails with `binfmt_flat: ... errno -12` — that's
the NOMMU allocator failing to find contiguous space in this Buildroot config's ~5.9 MB usable RAM,
a property of the 8 MB image itself, not a harness bug; same thing would happen on real hardware
with one PSRAM chip. Not chased further — the harness's job (iterate on the emulator/cache/PSRAM
port without hardware) is proven.

Not yet done: no CMakeLists/build script checked in (the harness is one `gcc` line, didn't seem
worth it yet); disk image build isn't scripted, just documented above.

**16 MB config verified (2026-08-15).** Bumped `harness/vm_config.h` `EMULATOR_RAM_MB` to 16,
rebuilt, booted the *same* 8 MB-era image unchanged. `cat /proc/meminfo` reports `MemTotal: 14096
kB` — confirms the DTB memory-node patch in `start_vm()` scales correctly off `ram_amt` at runtime,
no code changes needed. Bonus: `cat`/`ls` (external binfmt_flat exec) now succeed, where they
OOM'd at 8 MB — the earlier `errno -12` really was just the tiny RAM config, not a harness bug.
This validates the *software* side of the multi-chip PSRAM port (RAM sizing, cache addressing over
`ADDR_BITS 24` — exactly 16 MB, right at the edge — DTB patch) independent of the real SPI
chip-select logic, which only matters on hardware. `ADDR_BITS` in `cache.c` is hardcoded to 24 and
was not touched; 16 MB is the max this cache addressing supports without a further change.

### Idea, parked: throttle the harness to real hardware speed (2026-08-15)

Discussed, deliberately not built. The emulator core ties the guest's timer/jiffies to real
elapsed wall-clock microseconds already (`EMULATOR_FIXED_UPDATE 0`, `EMULATOR_TIME_DIV 1` in
`vm_config.h` — `start_vm()`'s main loop computes `elapsedUs` from `timing_micros()`, not from
instruction count), so the guest kernel's *sense* of time is already realistic in both the harness
and on hardware. What differs is throughput: the harness runs the same interpreter loop on a
modern x86 host, so it executes far more guest instructions per real microsecond than an
overclocked RP2040 running the same C interpreter would. Rate-limiting `start_vm()`'s
instructions-per-flip loop against a target guest IPS would make the harness *feel* like real
hardware speed-wise.

Not done because: no real hardware benchmark exists yet to calibrate a target IPS against (hardware
is parked), so any number picked now would be a guess, not data. It also wouldn't help find the
class of bug hardware bring-up actually cares about — bad solder joints, SPI signal integrity,
overvolt stability — those are physical, not timing artifacts, and no software throttle simulates
them. Revisit once there's a real hardware IPS number to target; cheap to add then.

### Cross-compile toolchain — built and proven, 2026-08-15

Full working `riscv32-buildroot-linux-uclibc-gcc` 13.3.0 cross-toolchain built and used to compile
and run a real "hello world" and a Tiny BASIC interpreter live in the harness.

**Now available as a prebuilt download — no rebuild needed**:
[`toolchain-v1` release](https://github.com/flyboy-byte/riscv-pico/releases/tag/toolchain-v1),
`riscv32-tinyrv32ima-toolchain.tar.gz` (69 MB compressed, 205 MB unpacked, x86_64 Linux host only).
```sh
gh release download toolchain-v1 --pattern '*.tar.gz'
tar xzf riscv32-tinyrv32ima-toolchain.tar.gz
export PATH=$PWD/host/bin:$PATH
```
Deliberately a release asset, not a git commit — keeps `git clone` small and doesn't put an opaque
x86_64 binary blob in commit history (this repo may get shared; that matters more than usual). The
build itself still lives in ephemeral session scratchpad and won't survive to a fresh session —
this section is the from-source recipe, kept for anyone who'd rather build their own than trust a
downloaded binary (completely reasonable for a compiler), or who's on a different host arch. Every
failure mode below is already solved, so a from-source rebuild should go straight through without
the trial-and-error this session had.

**Why this needs a real buildroot build, not a distro cross-compiler:** the rootfs binaries
(confirmed via `debugfs -R "dump ..." | file`) are **bFLT** (binary flat, no-MMU format), not
regular ELF. A generic `riscv64-linux-gnu-gcc` from Arch's repos cannot produce these — only the
project's own uClibc+no-MMU+elf2flt-equipped toolchain can.

**Step 1 — host compiler.** This machine's system GCC (16.x) is too new to bootstrap GCC 13:
GCC 16 hard-errors on implicit function declarations and defaults to C++20 (breaking old GCC's
`u8""`-literal-using `libcody` code with `char8_t` type mismatches) — neither is fixable by flags
alone, it cascades through multiple sub-configure scripts that don't inherit `CFLAGS`/`CXXFLAGS`
overrides. **Fix: install `gcc12` from the AUR** (`yay -S gcc12` — installs version-suffixed
`gcc-12`/`g++-12` alongside the system compiler, zero conflict, confirmed safe). Use it as the
*host* compiler for the whole buildroot build; this sidesteps the entire class of problem in one
shot rather than patching each mismatch as it surfaces.

**Step 2 — get buildroot, configured for this target:**
```sh
git clone --depth 1 https://github.com/tvlad1234/buildroot-tiny-rv32ima.git repo
cd repo
make buildroot   # downloads buildroot 2024.05, applies tinyrv32ima_defconfig via BR2_EXTERNAL
```

**Step 3 — build just the toolchain** (not `make everything` — that also builds the kernel/rootfs/
packages, which we don't need; `toolchain` is buildroot's own scoped target for exactly this):
```sh
cd buildroot
make HOSTCC=gcc-12 HOSTCXX=g++-12 toolchain
```
Compiler ends up at `buildroot/output/host/bin/riscv32-buildroot-linux-uclibc-gcc`.

**Step 4 — compile something:**
```sh
riscv32-buildroot-linux-uclibc-gcc -mabi=ilp32 -march=rv32ima -static -Wl,-elf2flt=-r -Os -s \
  hello.c -o hello
```
Those exact flags come from the project's own `goodies/hello_linux/Makefile` — matching them
matters, they're what makes `elf2flt` emit bFLT instead of a normal ELF binary. Verify with
`file hello` → should say `BFLT executable`.

**Step 5 — inject into the rootfs, no full rootfs rebuild needed.** The downloaded `rootfs` file
(from the `images.zip` release asset — see README) is a raw ext2 image; write into it directly:
```sh
debugfs -w -R "write /path/to/hello usr/bin/hello" rootfs
debugfs -w -R "sif usr/bin/hello mode 0100755" rootfs
mcopy -o -i harness/disk.img rootfs ::ROOTFS   # sync into the FAT test image the harness boots
```
Then restart `harness/desktop_terminal.py` (kill any old `rv32harness`/`desktop_terminal.py` first
— see "process hygiene" note below) and the new binary is runnable from the shell immediately.

**Two hard-won gotchas, worth not re-learning:**
- **Never run two `make toolchain` invocations against the same `output/` directory
  concurrently.** This session did (by accident, via repeated background-task restarts) and it
  silently corrupted the compiler's install step — `riscv32-buildroot-linux-uclibc-gcc.br_real`
  ended up as a symlink pointing back to the wrapper script instead of the real compiler binary,
  which only surfaced as a confusing `.br_real.br_real: No such file or directory` error several
  stages later (during `uclibc` headers). The fix was a full `rm -rf output/build output/host` and
  one clean single-threaded rebuild attempt. `pgrep` gave false negatives for whether old builds
  were still running — trust `ps -eo pid,etime,cmd` instead when in doubt.
- **Process hygiene for the harness's background processes generally**: always verify with `ps`,
  not `pgrep -f`, before assuming something died or restarting it — `pgrep -f` gave false negatives
  more than once this session (both for `make toolchain` and for `rv32harness`), and this session
  accumulated duplicate `rv32harness` processes as a result each time.

### apps/ — cross-compiled userspace programs (2026-08-15)

Source lives in `apps/` (checked in — unlike the toolchain, these are small and worth keeping).
Compile with the toolchain from the section above:

```sh
GCC=buildroot/output/host/bin/riscv32-buildroot-linux-uclibc-gcc
$GCC -mabi=ilp32 -fPIE -pie -static -march=rv32ima -Os -s -Wl,-elf2flt=-r apps/NAME.c -o NAME
```

**`-fPIE -pie` are not optional** — they were dropped once while compiling `basic.c` and it
segfaulted on boot (`cause: 00000005`, load access fault at a small address) because the loader
relocates the bFLT image at runtime (`gotpic` format) but the code had been compiled with absolute
addressing. `hello.c` happened to work without them purely because it has almost no static data to
misaddress — don't take that as evidence the flags are skippable. These are the exact flags from
the project's own `goodies/hello_linux/Makefile`; match them.

Inject into the rootfs (no rebuild of the FAT image needed for `IMAGE`/`DTB`, only `ROOTFS`):
```sh
debugfs -w -R "write /path/to/NAME usr/bin/NAME" rootfs
debugfs -w -R "sif usr/bin/NAME mode 0100755" rootfs
mcopy -o -i harness/disk.img rootfs ::ROOTFS
```
Then restart `harness/desktop_terminal.py` (kill old `rv32harness`/`desktop_terminal.py` first,
verify with `ps`, not `pgrep -f` — see the process-hygiene note above).

- **`hello.c`** — minimal smoke test, proves the pipeline works at all.
- **`basic.c`** — a small integer-only BASIC interpreter (26 vars A-Z, `PRINT`/`LET`/`IF THEN`/
  `GOTO`/`GOSUB`/`RETURN`/`FOR..NEXT`/`INPUT`/`LIST`/`RUN`/`NEW`). Line-based I/O only, no cursor
  positioning — matches what the web console can currently render. Verified live: `FOR`/`NEXT`
  loops, `IF`/`GOTO`, string+expression `PRINT`, variable assignment all correct on real target
  execution. One real bug caught and fixed during testing: `NEXT` was jumping back to the `FOR`
  line itself, which re-executed the initialization and reset the loop variable every iteration
  (infinite loop) — fixed by jumping to the line *after* `FOR` instead.

### Full-screen apps — unblocked (2026-08-15)

Was blocked on the old browser console only understanding "append text" + backspace, stripping
real cursor-positioning escape sequences instead of acting on them. Resolved by replacing it with
`harness/desktop_terminal.py` (see "Desktop terminal app" below), which uses `pyte` for real
VT100/ANSI interpretation. The text-editor and terminal-game ideas should now be viable — not yet
tried against this new console, so "should work" is a reasonable bet, not yet verified.

### Vision beyond the port (2026-08-15, from conversation — not yet scoped)

Direction discussed: make this repo's distinguishing feature "runs without hardware," lean into
that, and eventually cross-compile small C programs against the RISC-V toolchain and drop them into
the rootfs to run under the harness (or real hardware) — not full desktop-app ports, just tiny
userspace C binaries. Agreed ordering: the multi-chip PSRAM port and a hello-world cross-compile
proof come *before* any rootfs/buildroot rework (nano, a real compiler) — those are a heavier,
separate-session job (see below).

**Proven end-to-end, 2026-08-15**: wrote `hello.c`, cross-compiled it, injected it into the rootfs,
booted it in the harness, ran it live in the web console. The whole pipeline works. Next
candidates discussed, not yet started, roughly in order of quick-win to impressive: a minimal
text editor written from scratch (~150-300 lines, sidesteps the whole busybox-vi/buildroot-rootfs-
rebuild question), a tiny BASIC interpreter, a Lua interpreter, a terminal game (snake/tetris, raw
ANSI escapes, no curses needed). User wants to pick one (or more) next session — compiling takes
real wall-clock time and today's already spent a lot of it on toolchain archaeology.

### Desktop terminal app (built, 2026-08-15 — superseded the browser console)

`harness/desktop_terminal.py` — a real PyQt6 desktop app, not a browser page. Spawns `rv32harness`
as a subprocess same as before, but interprets its output through `pyte` (a real VT100/ANSI
terminal emulation library — cursor movement, clear-screen, colors) and renders it in a
custom-painted grid widget, instead of the browser console's old "just append text and strip
escape sequences" approach. This is the actual fix for the full-screen-apps limitation noted
above — a text editor or curses program should render correctly here where it couldn't before.

Run: `python3 harness/desktop_terminal.py harness/disk.img` (`--cols`/`--rows` to change the
initial grid size, `--binary` to point at a different harness build). Requires `python-pyte` and
`PyQt6` (both installed via `pacman`/already present respectively as of this session — `pyte` via
`sudo pacman -S python-pyte`).

The old browser-based `harness/webconsole.py` (Server-Sent Events + a local HTTP server) has been
**removed** — this app replaces it entirely, same role (watch the harness live, type into it,
scriptable input) but with real terminal fidelity instead of a line-append hack.

## Decisions already made (do not re-ask)

- **D-001** — Repo is `flyboy-byte/riscv-pico`, public, upstreams vendored as **subtrees** (not
  submodules, not flat copies). Chosen for low-friction hacking while keeping upstream pulls and
  provenance. (2026-08-15)
- **D-002** — Base the eventual fork on `pico-rv32ima`, port `pico-linux` features into it.
  Rationale above. (2026-08-15)
- **D-003** — Upstream trees stay pristine while in staging. Only exception so far: removing the
  `tiny-rv32ima` submodule pointer, which was replaced by a subtree at the same path. (2026-08-15)
- **D-004** — Serial-first bring-up; the LCD is wired last. The previous attempt stalled partly by
  trying to bring up everything at once with no feedback until it all worked. (2026-08-15)
- **D-005** — Real hardware work is parked indefinitely; focus is emulation-only until the user
  explicitly says otherwise. Don't propose flashing, chip-testing, or wiring steps unprompted.
  (2026-08-15)
- **D-006** — Upstream trees are no longer pristine (D-003's exception point). The multi-chip PSRAM
  port landed directly on `upstream/pico-rv32ima` and `upstream/pico-rv32ima/tiny-rv32ima` (on
  branch `port/multi-chip-psram`). Future upstream `git subtree pull`s will need to merge through
  local changes from here on — that's an accepted tradeoff, not an oversight. (2026-08-15)

## Hardware readiness — theoretical audit, no hardware touched (2026-08-15)

Done ahead of real bring-up, specifically to catch mistakes on paper instead of during a debugging
session. Evidence tagged **DOCUMENTED** (datasheet/spec), **REPORTED** (community consensus, no
hard number), or **INFERRED** (derived, not directly sourced) — don't launder one into another.

### Pin/wiring audit — DOCUMENTED (read directly from `hw_config.h`/`main.c`)

Full pin map, `pico-rv32ima`, single source of truth is the header, not the README (README
disagrees with it in places — known issue, noted since this project's `CLAUDE.md` was written):

| Pin(s) | Used by |
| --- | --- |
| GPIO0 | SD CS **and** UART TX (see conflict below) |
| GPIO1 | UART RX |
| GPIO2–4 | SD CLK/TX/RX |
| GPIO5–8 | Bit-banged SPI (CS/SCK/MOSI/MISO) |
| GPIO10–13 | PSRAM CLK/TX/RX/S1 (chip 1 CS) |
| GPIO14 | PSRAM S2 (chip 2 CS) — this session's addition |
| GPIO16–20 | VGA VSYNC/HSYNC/R/G/B (G, B are `VGA_R_PIN`+1/+2, driver-computed, not `#define`d) |
| GPIO25 | Onboard LED (`PICO_DEFAULT_LED_PIN`, SDK-defined) |
| GPIO26–27 | PS/2 data/clock |
| **Free\*** | GPIO9, 15, 21, 22, 23, 24, 28, 29 |

\* **GPIO29 caveat, DOCUMENTED (search-confirmed):** wired to VSYS sense (ADC3) on the physical
Pico board itself, not just an RP2040 chip capability question — using it as a general digital pin
is unreliable regardless of what the chip alone would allow. Treat GPIO29 as not actually free.

**Real conflict found, not previously documented: `UART_TX_PIN` (GPIO0) is the same pin as
`SD_SPI_PIN_CS` (GPIO0).** Harmless right now only because `CONSOLE_UART` defaults to `0`
(disabled) in `hw_config.h`. The moment someone flips it on for hardware-bring-up debugging — a
very likely thing to reach for — it silently breaks the SD card, with no error message pointing at
why.

**Not fixed this session, deliberately** — tried to just move UART to two free pins and stopped
short of it. UART0's alternate-pin table on RP2040 is fixed silicon, not arbitrary (confirmed
GPIO0/1 and GPIO16/17 both work; GPIO16/17 are already taken by VGA sync here); couldn't get
authoritative confirmation via search/community sources for any *other* UART0-capable pin, and
guessing wrong would trade one landmine for another rather than fix anything. The actual fix needs
the real RP2040 datasheet §1.4.3 GPIO function table (or a hardware test) — flagging this precisely
so whoever does that lookup doesn't have to re-discover the conflict itself, just resolve it.

**PSRAM_SPI_PIN_S2 (GPIO14, this session's port) confirmed conflict-free** against every other
subsystem above — it's in the free-pin range.

**Board caveat — DOCUMENTED, but which board wasn't confirmed by the user (session earlier only
established "Pico or Pico W"):** on Pico **W** specifically, GPIO23/24/25/29 are wired to the
CYW43 wireless chip, not general-purpose — the LED especially (`PICO_DEFAULT_LED_PIN`) is driven
through the wireless chip's SPI on a W board, not a direct RP2040 pin, and the SDK's board header
handles that automatically (not a firmware bug to fix), but it means GPIO23/24/29 aren't "free" on
a W board the way the table above implies for a non-W Pico. Doesn't affect anything currently
wired (GPIO14 is unaffected either way) — just don't reach for 23/24/29 later without checking
which board is actually in hand.

### SPI timing / signal integrity — DOCUMENTED (pulled real datasheet PDFs, not summaries)

Both "known-working" chip models the project's README names — LY68L6400 and ESP-PSRAM64H — turn
out to have essentially identical timing envelopes:

- Max clock: **133–144 MHz** (linear, non-page-crossing). **84 MHz max** the instant a burst
  crosses a 1KB page boundary (JEDEC-mandated, not a suggestion).
- ESP-PSRAM64H specifically ([Espressif's own PDF](https://www.espressif.com/sites/default/files/documentation/esp-psram64_esp-psram64h_datasheet_en.pdf)):
  Vcc 2.7–3.6 V (3.3V nominal sits comfortably inside), **Icc (active read/write) max 40 mA**,
  standby 200 µA max, **tCEM (CE# low pulse width) max 8 µs** — CS cannot be held low continuously
  longer than that.
- CLK period minimum 7 ns (matches the 133/144 MHz max) for anything except a plain SPI read
  (`'h03`), which is capped lower (30.3 ns / ~33 MHz).

**So the project's configured `PSRAM_SPI_SPEED` (52 MHz stock, ~20 MHz suggested for bring-up) is
conservative, not aggressive** — both chips are datasheet-rated for 2.5–4x that. `CLAUDE.md`'s
existing "drop to ~20MHz for flying leads" advice is about signal integrity on unshielded wiring,
not the chips' own ceiling — worth keeping as-is; the chips are not the limiting factor, the wiring
is.

**tCEM (8µs max CE-low) checked against the actual code, not just theoretical:** `psram_access()`
already only ever holds CS low for one `CACHE_LINE_SIZE` (16 bytes) at a time (cache.c drives it
per cache line, not per 512-byte block), so even at the slowest realistic SPI speed this session
discussed (~20 MHz), 16 bytes is on the order of tens of nanoseconds of data time plus command
overhead — nowhere near 8µs. **Confirmed compliant by design, not by luck.**

### Power budget — mixed DOCUMENTED/REPORTED, one number genuinely unconfirmed

- **RP2040 total GPIO+QSPI current budget: 50 mA, DOCUMENTED** (RP2040 datasheet, via search — not
  independently re-verified against the primary PDF, treat as REPORTED-strength until it matters).
  This is a *shared pool* across every GPIO sourcing/sinking current, not per-pin.
- **The VGA color lines are the actual budget concern here, not PSRAM/SD.** README's own wiring
  notes already say R/G/B need 330Ω series resistors. Driving 3.3V through 330Ω is ~10 mA per
  active line; three color lines high simultaneously (a white pixel) is ~30 mA right there, before
  anything else. SPI signal lines (PSRAM, SD, bit-banged) don't drive resistive loads — they
  toggle logic levels into a chip's input, current draw there is negligible by comparison. If GPIO
  budget ever gets tight, VGA is where to look, not the new PSRAM chip.
- **Two PSRAM chips do NOT double active current** — INFERRED, but straightforward: only one chip
  is ever selected at a time by design (that's the whole point of per-chip CS), so worst case is
  one chip active (40 mA) plus one idle in standby (200 µA), not 2×40mA simultaneously.
- **Pico's onboard regulator (RT6150): rated ~800 mA continuous, Raspberry Pi's own guidance
  recommends staying under 300 mA external draw — REPORTED**, via search, not the primary
  datasheet. 40 mA (or even 80mA if the "one chip at a time" assumption above is ever wrong) is a
  small fraction of that regardless.
- **RP2040 core current draw at the project's actual overvolt/overclock config (`VREG_VOLTAGE_MAX`
  = 1.30V, 400MHz) — genuinely UNKNOWN, not sourced.** Search turned up plenty of "people run Pico
  at 400MHz routinely without regulator problems" community consensus, but no hard mA figure at
  this exact voltage/clock combination. Worth being honest that this is the one number in this
  whole audit that's a real gap, not a confirmed-safe conclusion — though also worth noting
  `VREG_VOLTAGE_MAX` (1.3V) is the RP2040's *built-in* regulator ceiling, reachable via software
  alone — not the same as the trace-cutting/external-voltage extreme overclocking some hobbyists
  do to push past it, which is a different and much riskier thing this project isn't doing.

### Pico 2 / RP2350 support — noted, not started

User interest, no work done. `pico-rv32ima` upstream already supports RP2350 (`#ifdef
PICO_RP2350A` in `main.c`, `-DPICO_BOARD=pico2` build flag already documented in this repo's own
README/CLAUDE.md) — so this may be closer to "verify it builds and note the differences" than a
real port. Not investigated further this session.

## Ruled out, with reasons

- **Emulating the RP2040 to test this.** Investigated all four options — `rp2040js` (no SPI, single
  core), Wokwi (built on rp2040js, same gaps), `Renode_RP2040` (multicore ✓ but no USB CDC, no SD,
  author marks it frozen), `PicoSimulator` (SPI ✓ but no dual core, no USB, 41 commits). This
  firmware needs two SPI buses, both cores, USB CDC, *and* behavioral models of an external PSRAM
  chip and SD card. Nothing has that combination, and the closest would still leave the PSRAM model
  to write. Size was never the problem — they're all small. (2026-08-15)
- **Stock `cnlohr/mini-rv32ima` as a desktop test rig.** Boots cnlohr's own images fine, but not
  either project's — `tiny-rv32ima` extends the emulator with custom block-device CSRs the stock
  build doesn't implement. Details in CLAUDE.md. Superseded by the desktop-harness idea. (2026-08-15)
