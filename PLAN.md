# PLAN.md

Living state document. Current reality, not a task list.

**Status: staging — both upstreams vendored and buildable, desktop harness boots to a Linux shell,
nothing ported to hardware yet (2026-08-15)**

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
- ❌ Nothing flashed to hardware yet.
- ❌ Nothing ported between the two projects.
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

### The multi-chip PSRAM seam

`tiny-rv32ima/psram/psram.c:44-66` — `psram_access()` already has the address in hand:

```c
cmdAddr[1] = addr >> 16;   // address is right here
...
psram_select();            // ...but select takes no argument
```

and `pico-rv32ima/hal/hal_psram.h` hardcodes one chip:

```c
#define psram_select()   gpio_put(PSRAM_SPI_PIN_S1, false)
```

Fix: make selection address-aware — map `addr` → CS pin, subtract the chip's base offset. That
logic already exists and works in `upstream/pico-linux/pico-rv32ima/psram/psram.c` (`accessPSRAM()`).
Roughly 20 lines, transplanted into a cleaner seam.

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
