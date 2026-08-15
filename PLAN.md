# PLAN.md

Living state document. Current reality, not a task list.

**Status: staging — both upstreams vendored and buildable, nothing ported yet (2026-08-15)**

## Where things actually stand

- ✅ Pico SDK 2.1.1 at `~/pico-sdk` (shallow + tinyusb only, 65 MB). Builds clean on GCC 16.1.
- ✅ `upstream/pico-rv32ima` builds → `build/pico-rv32ima/pico-rv32ima.uf2`, 140 KB. **Flashable now.**
- ✅ Both upstreams vendored as subtrees with full history. `tiny-rv32ima` converted from submodule
  to subtree at the same path, so upstream CMake paths still work.
- ✅ Kernel images for `pico-rv32ima` downloaded and inspected (`images.zip` v1.0, 2025-08-27:
  `Image` 2.2 MB, `dtb` 2 KB, `rootfs` 60 MB ext2).
- ❌ Nothing flashed to hardware yet.
- ❌ Nothing ported between the two projects.
- ❌ No desktop harness.

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
