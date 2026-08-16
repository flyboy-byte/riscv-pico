# PLAN.md

Living state document. Current reality, not a task list.

**Status: full cross-compile pipeline proven — wrote, compiled, and ran a real program in the
harness. Multi-chip PSRAM port done in software. Real hardware parked until further notice.
(2026-08-15)**

**Next session starts here:** toolchain needs rebuilding (lives in ephemeral scratchpad, recipe
below is fully de-risked — should go straight through this time). Then pick a utility to compile:
text editor, tiny BASIC, Lua, or a terminal game — all discussed, none started.

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

### Cross-compile toolchain — built and proven, 2026-08-15 (must be rebuilt next session)

Full working `riscv32-buildroot-linux-uclibc-gcc` 13.3.0 cross-toolchain built and used to compile
and run a real "hello world" live in the harness/web console. **The build itself lives in the
session's ephemeral scratchpad and will not survive to the next session** — this section is the
exact recipe to redo it, now de-risked (every failure mode below is already solved, so a rebuild
should go straight through without the trial-and-error this session had).

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
Then restart `harness/webconsole.py` (kill any old `rv32harness`/`webconsole.py` first — see
"process hygiene" note below) and the new binary is runnable from the shell immediately.

**Two hard-won gotchas, worth not re-learning:**
- **Never run two `make toolchain` invocations against the same `output/` directory
  concurrently.** This session did (by accident, via repeated background-task restarts) and it
  silently corrupted the compiler's install step — `riscv32-buildroot-linux-uclibc-gcc.br_real`
  ended up as a symlink pointing back to the wrapper script instead of the real compiler binary,
  which only surfaced as a confusing `.br_real.br_real: No such file or directory` error several
  stages later (during `uclibc` headers). The fix was a full `rm -rf output/build output/host` and
  one clean single-threaded rebuild attempt. `pgrep` gave false negatives for whether old builds
  were still running — trust `ps -eo pid,etime,cmd` instead when in doubt.
- **Process hygiene for the harness/webconsole background processes generally**: always verify
  with `ps`, not `pgrep -f`, before assuming something died or restarting it — this session
  accumulated duplicate `rv32harness` processes the same way.

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

### Live web console (built, 2026-08-15)

`harness/webconsole.py` — stdlib-only Python, no dependencies. Spawns `rv32harness` as a subprocess
and serves a local page at `http://127.0.0.1:8765` (port configurable) that shows the console
output live via Server-Sent Events, plus a text box to send input. A plain `POST /input` (e.g.
`curl -X POST http://127.0.0.1:8765/input --data-binary $'uname -a\n'`) drives the same running VM
from a script or from Claude — verified end to end: booted, `uname -a` and `echo` sent via curl
both executed and their output showed up in `/backlog`. There's also `GET /backlog` (full
transcript, plain text, easiest for scripted checks) alongside `GET /stream` (SSE, for the page).

Not a claude.ai Artifact — this account only has the `downloads`/`mcp` runtime capabilities, no
live-streaming one, so a published Artifact can't back a live local process. This is a plain local
dev server instead; open the URL in a normal browser tab.

Run: `python3 harness/webconsole.py harness/disk.img --port 8765` (the `harness/disk.img` FAT test
image is gitignored, build it locally per the steps above).

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
