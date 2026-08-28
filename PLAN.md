# PLAN.md

Living state document. Current reality, not a task list.

**Status: booting Linux on real hardware (2026-08-27).** See the hardware milestone note below;
the rest of this block is the software state as of 2026-08-17 and is still current.

**Full cross-compile pipeline proven** — hello world, Tiny BASIC, and real GNU nano 7.2 all
run live in the desktop harness. Nano's SIGILL crash, the read-only rootfs, and the Enter-key bug
are all root-caused and fixed. The desktop app is a real menu-bar app (reboot, RAM-config switch,
disk picker, TTY-size sync). `pico-rv32ima` builds clean for all four board targets (`pico`,
`pico_w`, `pico2`, `pico2_w`). The guest kernel has a working TCP/IP stack (loopback-verified) and a
second HVC channel for the SLIP bridge — guest→host byte transfer works, host→guest is blocked on an
unresolved console-freeze bug (see open item #1). The rootfs now also has a real `curl` (HTTP-only
build) and a hand-written `sysinfo` banner (neofetch-alike, but hush-compatible — real neofetch
needs bash, which needs an MMU this NOMMU target doesn't have — **8MB config no longer boots at
all now that curl's added, 16MB only, see open item #5**). README.md rewritten (scannable
highlights + quickstart, a real header image at `docs/images/header.jpg`) and verified rendering
correctly on GitHub via Playwright. All build outputs are published as GitHub releases, not
committed to git. (2026-08-17)

**Real hardware bring-up started 2026-08-25** — Pico H confirmed alive over USB-CDC, both PSRAM
chips individually graded good at 20 MHz SPI. One real firmware bug found and fixed
(`console_panic()` was one-shot, easy to miss entirely — now repeats). Full detail in "Real
hardware bring-up" under "Next steps, in order."

**🎉 FIRST LINUX BOOT ON REAL HARDWARE — 2026-08-27.** Both PSRAM chips wired simultaneously
(16 MB), SD card wired, Linux booted to a shell on the Pico itself. Root mounted at 15.9 s.
GNU nano runs and saves files on real hardware. Memory verified across the chip-select boundary
by measurement, not inference. **This closes steps 3 and 4 of "Next steps, in order" in one
session** — the multi-chip PSRAM port (written 2026-08-15, compile-verified only) is now proven
on real silicon. Full detail in "First Linux boot on real hardware" below.

**Side experiment while waiting on the SD card (2026-08-26): a spare Pi 4B made to act as a
fake SD card over SPI, talking directly to the Pico.** Real working proof of concept — full SD
init handshake + a byte-perfect 512-byte sector read with CRC16 integrity checking, going
further than the one comparable precedent found online. **Not a path to actually booting
Linux** — a real boot needs ~126,000 sequential sector reads with zero tolerance for a bad
one, a different scale of problem than "usually works." Full writeup, working code, and the
honest ceiling in [`experiments/pi4-sdcard-emulator/README.md`](experiments/pi4-sdcard-emulator/README.md).
Paused here — SD card takes over once it arrives.

## Open items, prioritized

1. **SLIP guest↔host bridge, Phase 1 — half-working, one real bug found and NOT fixed. Read the
   whole entry before touching this again.** (2026-08-17)
   - **`guest → host` byte transfer: done and verified.** `harness/netchan.c` (new) opens a PTY at
     harness startup (`harness/main.c`, before `vm_init_hw()` — the emulator core is vendored/
     pristine and can't be touched per D-003) and implements `hal_csr.h`'s `custom_csr_write`/
     `custom_csr_read` for CSR pair `0x141`/`0x142` (confirmed free; needed **zero core
     `emulator.c` changes** — `HandleOtherCSRWrite`/`Read` already fall through to
     `custom_csr_write`/`custom_csr_read` for any CSR they don't recognize). Kernel side is a new
     patch, `0003-second-hvc-channel.patch`, adding a second `hvc_alloc(1, ...)` port (`/dev/hvc1`
     in the guest) alongside the existing console. Verified with a real byte round-trip
     (`echo -n X > /dev/hvc1` on the guest, read back on the host's PTY — exact bytes arrive).
   - **Real bug found and fixed along the way: PTY canonical-mode buffering.** A fresh PTY defaults
     to canonical (cooked) line discipline, which buffers writes until a newline — SLIP framing has
     none, so every byte would sit stuck, invisible to any reader. Fixed with `cfmakeraw()` on the
     slave side in `netchan_init()`, before closing our reference to it.
   - **Real bug found and fixed: `get_chars()` for the second port was never called, at all.**
     `khvcd` (the hvc framework's polling kthread) blocks indefinitely once idle and only wakes via
     `hvc_kick()`. The console port stays kicked by its own printk/typing activity; this second
     channel's data arrives from *outside the kernel entirely* (the host's PTY write), so nothing
     inside the kernel ever kicked it. Fixed with a periodic (50ms) kernel timer in the patch that
     calls `hvc_kick()`. Confirmed via `pr_info` instrumentation: zero `get_chars2()` calls before
     this timer, real calls afterward.
   - **`host → guest`: NOT working. Real bug found, NOT fixed, root cause NOT confirmed.** Once
     something on the guest actively reads `/dev/hvc1` (e.g. `cat /dev/hvc1 &`), the *primary
     console* (`/dev/hvc0`) goes completely unresponsive — not slow, fully silent, no further shell
     input processed at all. This is a new, different bug from the two above, most likely a
     `khvcd` livelock/starvation between the two polled ports (see the comment above the kick timer
     in `hvc_riscv_minirv32.c` for the specific hypothesis — untested). **Next session: test with
     the second port allocated but never opened, to isolate whether allocation alone triggers it or
     it genuinely needs an active reader; then look at whether the timer's 50ms period or
     `__hvc_poll()`'s unconditional `poll_mask |= HVC_POLL_READ` for polled ports is the actual
     mechanism.** Nothing reads `/dev/hvc1` automatically today, so this doesn't affect normal use
     of the current image — full regression pass (clean boot, nano round-trip, loopback ping) all
     still pass clean against this exact kernel build.
   - Kernel+rootfs republished as `net-v1` (now titled "v2, second HVC channel"); harness binaries
     republished to `rv32harness-v1`. Buildroot checkout with the working patch lives at
     `/home/logan/.riscv-pico-scratch/repo/buildroot` (see "Reusable build environment" above).
   - **Phase 2 (real `slattach`/`ifconfig sl0` bring-up, needs `CAP_NET_ADMIN`) is still blocked on
     Phase 1's console-freeze bug** — `slattach` itself would trigger an active read on `/dev/hvc1`.
2. **ext2 corruption on abrupt kill, with root now `rw` — real bug, PARTIALLY fixed.** Killing the
   emulator mid-session (closing the app, `timeout` in tests) can leave the rootfs with `EXT2-fs:
   error: ext2_lookup: deleted inode referenced`, accumulating across repeated abrupt kills on the
   same disk image — reproduced live during 2026-08-16/17 testing, and traced to routine boot-time
   writes (`/run/utmp`, a failed `modprobe`'s `modules.dep.bb`) getting caught mid-write. Real
   partial fix shipped: `desktop_terminal.py` now sends `sync` to the guest before terminating on
   reboot/RAM-switch/disk-switch/window-close (`_sync_and_terminate()`, only when idle at the
   prompt — same safety check as the resize-sync path, never types into a running program). Note:
   this needed `CONFIG_SYNC`/`CONFIG_DD`/`CONFIG_PRINTF` enabled in busybox — they weren't, so the
   very first version of this fix silently no-op'd (`sync` didn't exist in the guest at all). Not a
   complete fix — `sync` only helps at the moments the desktop app controls (reboot/close); an
   external kill (crash, `kill -9` from outside the app) still corrupts. `disk.img` itself was
   found corrupted and repaired (`e2fsck -y`) twice this session.
3. **`UART_TX_PIN` (GPIO0) collides with `SD_SPI_PIN_CS` (GPIO0) in `pico-rv32ima/hw_config.h` — real
   landmine, not fixed.** Currently harmless only because `CONSOLE_UART` defaults to `0` (disabled);
   flipping it on for hardware bring-up debugging would silently break the SD card with no error.
   Blocked on finding a genuinely free UART0-capable alternate pin — needs the real RP2040 datasheet
   §1.4.3 GPIO function table (GPIO16/17 also work for UART0 but are already taken by VGA sync here).
   Software-fixable without hardware once the right pin is confirmed; final verification needs
   hardware. Found 2026-08-15, still open.
~~4. Firmware board-target build wrapper~~ — **DONE 2026-08-17.** `firmware/build.sh` (new) wraps
   `pico-rv32ima`'s per-board CMake build; `firmware/build.sh` with no args builds all four
   boards, `firmware/build.sh pico2_w` builds just one. Output goes to `firmware/out/*.uf2`
   (gitignored, matching the "binaries are GitHub releases, not git history" convention). Verified
   by actually running it for all four boards — output sizes match the earlier board-support audit
   exactly (140800/138240/131584/131584 bytes). Real hardware flashing still not attempted
   (D-005/hardware-parked still applies) — this only builds the `.uf2`, doesn't touch a device.
5. **8MB RAM config no longer boots — real regression, found by the user 2026-08-17 later same
   day, fixed as "16MB only" not as "fix 8MB."** Adding `curl` pushed boot-time memory pressure high
   enough that even the shell itself now fails to spawn on 8MB (`binfmt_flat: Unable to allocate RAM
   for process text/data, errno -12` for `sh` itself, not just nano like before). Same underlying
   class of bug already documented (8MB's usable RAM is genuinely ~5.9MB after kernel overhead,
   confirmed not a harness bug back on 2026-08-15) — just tipped further by curl's footprint.
   **Not chased further** — 16MB is the only viable config with this rootfs going forward; the
   desktop app's RAM-config menu still offers 8MB, so this needs a decision (drop the 8MB option
   from the menu, ship a curl-free 8MB-specific rootfs variant, or leave it and document the
   limitation) before it's really "done," not just worked around by using 16MB.
6. **Real process lesson, same incident:** the `harness/disk.img` actually in place had gone stale
   relative to what testing believed was current — regression tests earlier in the day passed
   against what was assumed to be the updated file, but the live file the desktop app uses didn't
   actually have `curl`/`sysinfo` until the user found it broken and this got re-verified and
   re-injected from the `net-v1` release tarball (the reliable source of truth). Root cause not
   fully pinned down. **Takeaway for future sessions: after any rootfs rebuild, verify the actual
   `harness/disk.img` file directly (`debugfs -R "stat usr/bin/<name>" <extracted-rootfs>`), not
   just a `disk_apptest.img`/`disk_verify.img` copy that gets renamed into place** — confirm the
   real file the app launches against, right before ending the session, not just at the moment of
   the fix.
7. **Backlog, lower priority, not scoped in detail:**
   - MicroPython (unix port) as a bigger showcase app than nano — real complexity (tens of
     thousands of lines, own build system, unconfirmed risk that its GC heap assumes `mmap()`-backed
     paging under no-MMU Linux). Would need a `mmap`-dependency scoping pass before committing.
   - A from-scratch terminal game or Lua interpreter — nano already proves full-screen apps work, so
     this is now just "another demo app," not a capability unlock.
   - Throttling the harness to real hardware instruction-per-second speed — blocked on having a real
     hardware IPS number to calibrate against, which needs hardware bring-up first (parked).
   - Bare-metal (non-Linux) firmware targeting this emulator's exact memory map — unexplored,
     nobody's asked for it, purely speculative.

**Reusable build environment for future kernel/rootfs rebuilds:** buildroot lives at
`/home/logan/.riscv-pico-scratch/repo/buildroot` (~8GB, includes a working host toolchain — reuse
this rather than re-cloning). **Hard lesson, worth reading before touching it again:** don't build
here from inside the session's tmpfs scratchpad (`/tmp/claude-*/.../scratchpad/`) — it's only 7.5GB
and a full kernel+host-GCC build blows straight through it, locking up the shell tool itself (every
command fails with ENOSPC on its own bookkeeping, not just the build). Build from real disk. Also:
pre-built host binaries bake in an absolute RPATH to wherever `output/host` physically lives — moving
the checkout after a partial build breaks buildroot's own `check-host-rpath` sanity check; if
relocating mid-build, wipe `output/host` and `output/build` first rather than trying to preserve them
across the move. The `package/Makefile.in` `-fPIC`→`-fPIE -pie` patch (needed for any package built
through buildroot's normal recipes on this target) also lives only in this checkout — reapply it
(see "Real GNU nano" below) if buildroot ever gets re-cloned fresh.

**Screenshot/verification tooling notes (2026-08-17):** `npx playwright install chromium` works
fine in this environment without `--with-deps` (that flag needs sudo for system libs, fails
non-interactively) — good for rendering-verification screenshots of the GitHub-hosted README, not
just local files. For screenshots of the actual desktop app (a real Wayland window, not a
webpage): Spectacle (`spectacle -b -n -o <path>`) works for capturing it, but there's no working
way found yet to *send synthetic keystrokes into it* — `xdotool` only sees X11 windows (this app is
Wayland-native, doesn't show up), and `ydotool` needs a `ydotoold` daemon that isn't running and
can't be started without root. If a scripted/composed screenshot of the app mid-interaction
(running nano, sysinfo, etc.) is ever needed again, that gap needs solving first — or just ask the
user to drive the interaction and grab the screenshot after.

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

Pico H (RP2040, 2021, has headers) · ST7735 128×160 LCD · two SPI PSRAM chips (APS6404L, 8-lead
SOP, QSPI used in standard-SPI mode) — **both graded good individually 2026-08-25, both wired
simultaneously and verified under load 2026-08-27** · a 5V→3.3V logic level converter (not needed
for PSRAM/SD, both 3.3V-native — earmarked for a PS/2 keyboard later, see "Real hardware bring-up"
below) · **14.6 GB microSD card (FAT32) + SPI breakout module — acquired and working 2026-08-27.**

Previous attempt (Sept 2024) got as far as installing the SDK and configuring a build, then
stalled — the gap was not knowing what happens after wiring, not the wiring itself. That gap is now
closed; see "Real hardware bring-up" below.

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

~~1. Bring-up over USB serial, one PSRAM chip only.~~ — **DONE 2026-08-25.**
~~2. Grade the chips.~~ — **DONE 2026-08-25.** Both real. Full detail in "Real hardware bring-up"
   below.
~~3. First Linux boot.~~ — **DONE 2026-08-27.** Booted to a busybox shell on real hardware,
   root mounted at 15.9 s. See "First Linux boot on real hardware" below.
~~4. Second chip → 16 MB.~~ — **DONE 2026-08-27**, same session as step 3. `PSRAM_TWO_CHIPS 1` +
   `EMULATOR_RAM_MB 16`, both chips wired simultaneously, verified under real load.
5. **Display / standalone-machine work** ← current step. Three independent options, see
   "Display plans" and "ST7735 port" below:
   - **SSD1306 status panel** — host-side panel **DONE 2026-08-27** (`pico-rv32ima-boards-v3`).
     Now superseded by a fuller plan: **see "Guest-driven status panel + image split" below**,
     which is the agreed 6-phase plan covering the guest-driven panel, the `plain` no-network
     image, the A/B firmware split and the glyph-grid refactor.
   - **VGA + PS/2 keyboard** — **zero new code**, `CONSOLE_VGA` is already on. Needs parts ordered
     (VGA breakout, 3× 330 Ω, PS/2 keyboard; the level shifter is already owned). This is the real
     standalone milestone.
   - **ST7735 console** — needs a pin reassignment first, it is *not* a drop-in; display is not
     currently on hand.

Optional but high-leverage, can slot in any time after step 3: **the desktop harness**
(see CLAUDE.md) — makes steps 4–5 iterable without touching hardware.

### Real hardware bring-up (2026-08-25)

First real hardware session — Pico H, both PSRAM chips, no SD card yet. Console is USB-CDC
(`CONSOLE_CDC 1` is already `pico-rv32ima`'s default, no config change needed).

- **Pico H confirmed alive.** Flashed stock `firmware/out/pico-rv32ima-pico.uf2` with nothing wired
  — clean, repeatable `PSRAM ERR` panic over USB-CDC serial confirms clocks/overvolt/USB
  enumeration/console pipeline all work.
- **Real bug found and fixed: one-shot panic message.** `console_panic()` (`pico-rv32ima/console/
  console.c`) printed its message exactly once, then spun silently forever
  (`while(true) tight_loop_contents();`). If nothing happened to be connected at that exact instant
  after boot, the message was gone for good — genuinely unrecoverable without a fresh power cycle
  timed just right. This is exactly what looked like "nothing printed" during initial testing (both
  `screen` and a raw `pyserial` read came back empty even with DTR explicitly toggled — confirmed via
  a script that watches for the `/dev/ttyACM*` node to disappear/reappear across a power cycle and
  opens it the instant permissions allow, still got `b''`). Fixed by making `console_panic()` repeat
  the message every 1s forever instead of going silent — general bring-up quality-of-life fix, not
  just a one-off patch to unblock this session.
- **Added a config knob: `PSRAM_SPI_SPEED_MHZ`** (`hw_config.h`, default 20). Previously hardcoded
  to 50 MHz directly in `main.c`'s `spi_init()` call with no way to turn it down — bad default for
  flying-lead/breadboard bring-up per the standing [[hardware-parked]]-era guidance (a chip that
  fails at 50 and passes at 20 is a signal-integrity problem, not a dead chip). Both chips graded
  clean at 20 MHz; haven't tried 50 yet since the wiring isn't permanent.
  Full pin mapping (APS6404L, 8-lead SOP → Pico H GPIO/physical pin): `SCLK`→GPIO10/pin14,
  `SI`→GPIO11/pin15, `SO`→GPIO12/pin16, `/CE`→GPIO13/pin17 (chip 2 later: GPIO14/pin19), `SIO2`/
  `SIO3` pulled up to VDD (unused quad-mode lines, must not float), `VDD`→3V3(OUT)/pin36 — no level
  shifting needed, chip is 3.3V-native, same rail as the Pico's own GPIOs.
- **Both chips graded good, one at a time on the S1 slot** (not simultaneously — `psram_init()`
  ANDs both chips' results together when `PSRAM_TWO_CHIPS 1`, so a two-chip failure can't tell you
  which chip is bad; grading them individually on the same known-good single-chip wiring avoids
  that ambiguity). Each: reflash unchanged firmware, confirm it gets past `PSRAM ERR` and instead
  fails at `Error initalizing SD` (expected — no SD card wired yet, that failure mode itself is the
  pass signal for the PSRAM step). Chip 1 confirmed good, swapped for chip 2 on the same wiring,
  confirmed good. Not yet tested: both chips wired simultaneously (`PSRAM_TWO_CHIPS 1`, step 4
  above).
- **SD card and SPI breakout module: not owned.** Need to buy — small (4–32 GB, SDHC, FAT32,
  avoid exFAT/SDXC since Petit FatFs here only understands FAT12/16/32) microSD card plus a basic
  SPI breakout module (either 3.3V-only or the common "5V-compatible" regulator/level-shifter kind,
  both fine here since it'll be powered from the Pico's 3.3V rail regardless). Wiring already known
  from `hw_config.h`: `CK`→GPIO2, `MOSI`→GPIO3, `MISO`→GPIO4, `CS`→GPIO0 (shares the pin with
  `UART_TX_PIN` — harmless as long as `CONSOLE_UART` stays 0, see open item #3).
- **The 5V→3.3V logic converter bought for this session turned out unneeded for PSRAM/SD** (both
  3.3V-native, same rail as the Pico) — real find, not wasted though: classic **PS/2 keyboards run
  their clock/data lines at 5V logic**, and this fork's PS/2 driver (`console/ps2/ps2.c`,
  `PS2_PIN_DATA`=GPIO26, `PS2_PIN_CK`=GPIO27) is real and already wired into the default
  `CONSOLE_VGA 1` build — so the converter has a genuine future use once a standalone-display
  milestone (VGA monitor + PS/2 keyboard, no PC tether) gets picked up. Not started, not urgent —
  USB-CDC console covers all current bring-up/testing needs at zero extra cost.

### Display plans — SSD1306 status panel, and VGA+PS/2 needs no code (2026-08-27)

Scoped on paper, **nothing built.** Two separate paths, complementary rather than competing.

#### VGA + PS/2 keyboard — already in the firmware, needs parts only

**`CONSOLE_VGA` defaults to `1` and always has** — the VGA console and PS/2 keyboard driver are
compiled into the firmware currently running on hardware. Nothing has ever been attached. This is
**zero new code**, just wiring, and it is the real "standalone machine, no PC tether" milestone.

| Signal | Pico | Note |
| --- | --- | --- |
| VSYNC | GPIO16 | direct |
| HSYNC | GPIO17 | direct |
| R / G / B | GPIO18 / 19 / 20 | **each through a 330 Ω resistor** — upstream README warns omitting these risks monitor damage |
| PS/2 data | GPIO26 | via level shifter |
| PS/2 clock | GPIO27 | via level shifter |

Shopping list: DE-15 VGA breakout (or a sacrificed VGA cable), 3× 330 Ω, a PS/2 keyboard. **The
5V↔3.3V level shifter is already owned** — bought for PSRAM, turned out unnecessary there, and
this is the future use already flagged for it in "Real hardware bring-up".

**Purchasing gotcha:** buy a *genuine* PS/2 keyboard, not a USB keyboard with a passive purple
PS/2 adapter. Those adapters only work if the keyboard contains legacy PS/2 fallback silicon,
which most modern keyboards dropped.

#### SSD1306 128×64 OLED — status panel — **BUILT (2026-08-27), not yet run on hardware**

Written, builds clean for all four boards, boot-tested in the desktop harness (the emulator-side
changes only). **Not yet verified against a real panel** — that's the open item.

| | |
| --- | --- |
| Driver | `upstream/pico-rv32ima/pico-rv32ima/console/oled/ssd1306.{c,h}` |
| Panel | `upstream/pico-rv32ima/pico-rv32ima/console/oled/status_panel.{c,h}` |
| Config | `hw_config.h` → `CONSOLE_OLED` block (defaults to **1**) |
| Cost | +5,808 bytes RAM vs. the previous build (254,332 of 262,144 used; ~7.8 KB free) |

**Wiring — I2C0, SDA GP28 (pin 34), SCL GP21 (pin 27), plus 3V3 (pin 36) and GND (pin 28).**

⚠️ **This is a correction to the plan recorded earlier the same day**, which said GPIO8/9. That pin
audit missed the **bit-banged SPI on GPIO 5/6/7/8** — the SPI master the guest kernel drives through
CSRs `0x180`–`0x183` (`hal/hal_csr.h`), which is a real feature, not dead config. `BB_SPI_MISO` is
GPIO8, so GPIO8/9 was never free.

The RP2040 constrains this hard: `i2c0` muxes onto GPIOs where `n/2` is even and `i2c1` where it is
odd, SDA always on the even pin and SCL on the odd pin above it. After UART (0,1), SD (0,2,3,4),
bit-banged SPI (5,6,7,8), PSRAM (10–14) and VGA/PS2 (16–20,26,27), the only free GPIOs are
**1, 9, 15, 21, 22, 28** — which yields exactly two usable pairs:

| Bus | SDA | SCL | |
| --- | --- | --- | --- |
| `i2c0` | GP28 (pin 34) | GP21 (pin 27) | **chosen** — both on the right edge, next to GND pin 28 and 3V3 pin 36 |
| `i2c1` | GP22 (pin 29) | GP15 (pin 20) | the alternative, if 28/21 are ever needed elsewhere |

There is **no free adjacent pair**, so the module's four pins need individual jumpers rather than a
4-way strip. Both pairs are free on `pico_w`/`pico2_w` too.

**What it shows** (21 columns × 8 rows, refreshed 2 Hz):

```
 riscv-pico  rv32ima     <- inverted title bar
RAM   16 MB / 2 chip
PSRAM 20 MHz
STATE running
SPEED 1.42 MIPS
INSTR 1247 M
UP    00:04:11
CLK   400 MHz
```

**Design notes worth not re-deriving:**

- **The 5×8 font already in the tree is a perfect fit.** `console/vga/font.h` stores glyphs
  column-major with bit 0 at the top — byte-identical to the SSD1306's page layout. So a text row
  maps 1:1 onto a display page and rendering a character is a 5-byte copy with zero bit twiddling.
  This is why the driver came in at ~160 lines instead of the estimated 250–350. (Cost: a second
  1,280-byte copy of the font, since the header declares it `static`.)
- **Flushing is incremental and dirty-tracked.** A full 1 KB frame at 400 kHz would block core 0 for
  ~23 ms, which is too long to sit inside the `console_task()` loop that also pumps USB. Instead
  `ssd1306_flush_step()` pushes one 64-byte chunk (~1.6 ms) per call, and `ssd1306_row()` skips
  rows whose rendered bytes are unchanged — so the steady state is a handful of chunks per second.
- **No `snprintf`.** The first version used it and cost **+10.6 KB**: it drags in newlib's
  `_svfprintf_r` and `_dtoa_r`, which was most of the remaining RAM headroom on this `copy_to_ram`
  binary. Two hand-rolled ~30-byte helpers (`put_str`/`put_num`) replaced it. Marking them
  `noinline` and narrowing one 64-bit divide to 32 bits took `status_panel_task` from 2,604 bytes
  to 640. **If you add formatting here, don't reach for stdio.**
- **Absent hardware is a non-event.** `ssd1306_init()` probes; no ACK means the driver disables
  itself permanently and the firmware behaves exactly as before. It also gives up after 16
  consecutive I2C errors, so a yanked wire can't stall the console loop forever.

**Upstream edits (D-006):** `emulator.c`/`.h` gained `vm_get_instret()` and `vm_get_stage()` plus a
`vmStage` enum, with the stage set at six points through boot. `vm_get_instret()` retries around a
torn 64-bit read since core 1 writes the counter while core 0 reads it. No new external symbols, so
the desktop harness still builds and boots unchanged (verified).

**This unblocks the parked harness-throttle idea.** `SPEED` is a real measured IPS, not the
one-boot ~45× wall-clock ratio — read it off the panel and the harness can be throttled to match.

**Open: verify on the real panel.** Flash `pico-rv32ima-boards-v3`, wire the four jumpers, confirm
the title bar and that `SPEED` settles to a plausible number once `STATE` reaches `running`. If the
panel stays blank, the module is probably at I2C address **0x3D** rather than 0x3C — one line in
`hw_config.h`.

### Guest-driven status panel + image split — the agreed plan (2026-08-27)

Design settled in conversation with the user on 2026-08-27. **Nothing below is built yet** except
where marked. Phase gates are real: you don't advance by writing more docs.

#### The architecture, in one paragraph

**Linux drives the display by writing bytes to a tty.** The guest has no display driver, no I2C, no
framebuffer. It writes to `/dev/hvc1`, which the emulator turns into CSR `0x141` writes, which core
0 renders onto whichever backend is configured. Core 1 runs the emulator; core 0 owns every
physical display. That is why one guest-side path can feed both the I2C OLED and VGA — the guest
was never coupled to either.

**Verified 2026-08-27 in the harness:** `cat /proc/loadavg > /dev/hvc1` returns 0. `/dev/hvc0`
through `/dev/hvc7` exist; `/proc/consoles` lists only `hvc0`, so **`hvc1` is a plain tty that will
not catch kernel spam** — exactly right for a status channel. The guest half of this is already
done and shipped in `net-v1`.

**Panel protocol** (a byte stream, same shape as the console):

| Byte | Meaning |
| --- | --- |
| `\f` | home + clear — begin a new frame |
| `\n` | next row, wrapping at 21 columns |
| other | a character |

So a full panel update from the shell is `printf '\f...' > /dev/hvc1`. No ioctl, no library.

**The keyboard is orthogonal and needs no thought.** PS/2 → core 0 `kb_queue` → CSR `0x140` → guest
reads it as `hvc0` *input*. Opposite direction, different channel; it never meets the panel.

#### Phase 0 — verify the OLED (user's action, ~10 min) — BLOCKS phases 2, 3, 5

Wire four jumpers (GP28 SDA / GP21 SCL / 3V3 pin 36 / GND pin 28), flash `pico-rv32ima-boards-v3`,
confirm the inverted title bar appears. **Gate: text on the panel.** If blank, try
`OLED_I2C_ADDR 0x3D` — that is the usual cause. Phases 1 and 2 do not wait on this.

#### Phase 1 — the `plain` guest image (no hardware needed)

Networking comes out of the Pico images. It stays only in the desktop harness and the Pico 2 WH
image.

- **Kernel** (`buildroot_overlay/board/tiny-rv32ima/linux-nommu.config`): drop `CONFIG_INET`, TCP,
  UDP, SLIP, `PF_PACKET`. ⚠️ **KEEP the second-HVC-channel patch** (`0003-second-hvc-channel.patch`,
  `hvc_alloc(1, ...)`). It was built during the networking work but it is *not* networking — it is
  the status panel's transport. Removing it silently breaks phases 2–5.
- **Busybox** (`busybox.config`): the applets that annoy us are hand-disabled for size, not missing
  because of NOMMU. Turn on `PS`, `TOP`, `KILL`, `GREP`, `SED`, `AWK`, `HEAD`, `TAIL`, `WC`, `DF`,
  `CP`, `MV`, and **`SLEEP`/`USLEEP`** (phase 3 needs a way to not spin). Drop `PING`, `IFCONFIG`,
  `ROUTE`, `SLATTACH` — the space pays for the rest.
- Rebuild kernel + rootfs. **This is the expensive step — hours in buildroot.** A cheaper variant
  exists (strip only the userspace tools, leave the stack compiled in) but it saves no RAM, and the
  RAM is the point: the network hash tables alone are **~287 KB** of a 13 MB system
  (`Table-perturb 262144` + TCP/UDP tables 24576, read off the boot log).

**Gate:** harness boots the plain image; `ps` lists processes; `sleep 1` works;
`echo x > /dev/hvc1` still returns 0. Ship as release `plain-v1`; `net-v1` stays for the harness
and Pico 2 WH.

#### Phase 2 — panel sink + harness panel emulator (no hardware needed)

- **Firmware `console/oled/panel.c`** — the character sink implementing the protocol above, feeding
  `ssd1306_row()`.
- **Firmware `hal_csr.h`** — route `0x141` → `panel_putc()`. Three lines. The harness has done the
  equivalent since the netchan work (`0x141` → PTY); this is the firmware catching up.
- **Host keeps ownership until the guest claims it.** Core 0 renders boot stages (`psram ok`,
  `sd ok`, `loading`) because those happen before init exists. First byte on `0x141` hands the
  panel to the guest. **No byte for N seconds and the host takes it back and shows
  `GUEST STALLED 14s`** — that turns the panel into a watchdog display, which is worth more than
  the stats.
- **Build a panel emulator into the harness** so the protocol, the layout and phase 3 are all
  testable with zero hardware. This is the usual harness-first move and it de-risks phase 0: if the
  physical panel never works, everything else still lands.

**Gate:** `printf '\fhello\n' > /dev/hvc1` in the harness draws on the emulated panel.

#### Phase 3 — `statusd` (needs phases 1 and 2)

**It cannot be a shell loop.** There is no `sleep` in the current rootfs (`CONFIG_SLEEP is not
set`), so a `while true` loop would spin at 100% on a ~1.4 MIPS machine and starve everything; and
on NOMMU each iteration vforks and *suspends the parent*. So: a ~60-line C program, one process,
`nanosleep()` between frames, reading `/proc/{uptime,loadavg,meminfo}` and `rdcycle` for its own
MIPS, writing one frame to `/dev/hvc1`. Same pipeline as `apps/hello.c`.

Keep it alive with init, not `&`: `::respawn:/usr/bin/statusd` in `/etc/inittab`, next to the shell.

**Gate:** live-updating panel in the harness; rootfs republished.

**What this buys that the host-side panel structurally cannot:** the host sees the emulator from
outside — cycles, boot stage, uptime. It cannot see load average, process count, free memory, or
mounted filesystems. Those live in `/proc` and only the guest can read them.

#### Phase 4 — firmware variants A and B

`firmware/build.sh` grows a variant argument; 8 `.uf2`s instead of 4.

- **A — `classic`**: `CONSOLE_OLED 0`, VGA + PS/2 exactly as tvlad's README intends. Minimal
  divergence from upstream.
- **B — `panel`**: the phase-2 architecture. VGA + PS/2 still the console.

B is technically a superset of A (the OLED driver disables itself when nothing ACKs), but a clean
reference build has real value: "does it also break on classic?" is the same isolation trick that
resolved the `nano` and `df` false alarms.

**Gate:** both variants build for all four boards.

#### Phase 5 — hardware verification

Flash B, `plain-v1` on the SD card, confirm `statusd` drives the real OLED.
**Gate: the panel updates from inside Linux, on hardware.**

#### Phase 6 — the glyph-grid refactor (deferred on purpose)

Makes VGA and the OLED each capable of being *either* a console or a status panel.

`terminal.c` is already a device-independent VT100 engine that merely writes straight into VGA's
arrays. Its whole contact surface is ~10 symbols: `VGA_putc/puts/clear/cursor/initDisplay`,
`termBuf`/`bgColBuf`, `cr_x`/`cr_y`/`fg_col`/`bg_col`, `TERM_WIDTH`/`TERM_HEIGHT`. Both displays
already use the **same 6×8 cell and the same `font.h`**, which is what makes this natural.

Introduce a `glyph_grid_t` (dims + `put`/`clear`/`cursor` function pointers); VGA and SSD1306 each
implement it; `terminal` and `panel` each consume one. Then a **sub-grid view** gives VGA rows 0–27
to the terminal and 28–29 to the panel — i.e. **a full boot console with a permanent status bar**,
falling out of the abstraction rather than being special-cased.

Costs, honestly: the work is de-globalising `terminal.c`'s cursor/colour/escape state, ~250–350
lines touched, mechanical. RAM is a non-issue — an OLED console grid is 21×8 = **168 bytes**, mono
so no colour buffer.

Two things to know: **an OLED console is 21 columns**, so an 80-column kernel message wraps to four
lines — fine for watching early boot, useless for nano. And **VGA is 53×30, not 80×25**
(`SCREEN_WIDTH 320 / FONT_WIDTH 6`), so 80-column output wraps there too.

**Deliberately last.** Refactoring `terminal.c` before there is a second working consumer is how
you get an abstraction that fits exactly one case.

#### Not in scope

- **No MMU work.** The guest has no MMU because `mini-rv32ima` has no `satp` and no S-mode — 21
  registers, M-mode and U-mode only. Adding Sv32 + S-mode + SBI is a different emulator (TinyEMU),
  and every load/store would then need a page walk through a software cache over SPI PSRAM.
  Estimate 2–4× slower; the 16-second boot becomes a minute-plus. Feasible, not worth it.
- **No RP2350-native port.** Interesting long-term (Hazard3 cores are real RISC-V, native
  memory-mapped PSRAM, hundreds of times faster than interpreting) but still NOMMU, and a different
  project.
- Networking is not removed from the harness or the Pico 2 WH image.

#### Parallel, user's action

Order VGA + PS/2 parts — DE-15 breakout, **3× 330 Ω on R/G/B (omitting them risks monitor
damage)**, a *genuine* PS/2 keyboard. Level shifter already owned. **VGA needs zero new code** —
`CONSOLE_VGA` is already 1 and the console driver is in the firmware running on hardware today;
plug in a monitor and you can watch it boot. Phase 6 only adds the status bar.

### ST7735 port — pin conflicts found before starting (2026-08-27)

Scoped on paper, **nothing built, display not on hand.** Recorded so step 5 doesn't open by
rediscovering this.

**The ST7735 is not special hardware** — a commodity SPI TFT controller (128×160 / 128×128, a few
dollars, many vendors). It's the chosen display purely because `pico-linux` already ships a working
driver for it, vendored here at `upstream/pico-linux/pico-displayDrivs/st7735/`, so the port is a
code-move rather than writing a display driver. Any SPI display with an existing driver would have
served equally.

**Two real pin collisions with the current verified wiring** (read directly from
`pico-linux/pico-rv32ima/config/rv32_config.h:138-144` vs our `hw_config.h`):

| `pico-linux` LCD pin | Value | Collides with, in our build |
| --- | --- | --- |
| `LCD_PIN_SCK` | GPIO14 | `PSRAM_SPI_PIN_S2` — **PSRAM chip 2 chip-select** |
| `LCD_PIN_DC` | GPIO4 | `SD_SPI_PIN_RX` — **SD card MISO** |
| `LCD_PIN_TX` | GPIO15 | free |
| `LCD_PIN_RST` | GPIO5 | free |
| `LCD_PIN_CS` | GPIO6 | free |

**This also explains an oddity CLAUDE.md records without a reason** — that `rv32_config.h`
"silently force-disables the LCD console for 3–4 chip setups" (its Config Checks block `#undef`s
`CONSOLE_LCD` when `PSRAM_THREE_CHIPS`/`PSRAM_FOUR_CHIPS` is set). The cause is now clear:
pico-linux assigns `PSRAM_SPI_PIN_S3`=14 and `S4`=15, which are exactly its LCD's `SCK` and `TX`.
The interlock exists because chips 3–4 eat the display's pins. Not a mystery, just undocumented.

**Why we hit it two chips earlier than pico-linux does:** pico-linux puts chips 1–2 on GPIO21/22,
leaving 14/15 free for the LCD at two chips. Our multi-chip port (2026-08-15) picked GPIO14 for
chip 2 — genuinely free at the time, with the display far off — which reintroduces the same
collision at two chips.

**Fix (software + one jumper, not yet done):** move `PSRAM_SPI_PIN_S2` from GPIO14 to **GPIO21 or
GPIO22** — both free in our pin map, and what pico-linux itself uses — freeing GPIO14/15 for the
LCD. Then reassign `LCD_PIN_DC` off GPIO4. Verify against the free-pin list before committing:
currently taken are 0,1 (UART), 2,3,4 (SD), 10–14 (PSRAM), 16,17,18 (VGA), 26,27 (PS/2).
Note this changes the hardware-verified wiring, so re-verify the two-chip boot after moving it.

### First Linux boot on real hardware (2026-08-27)

**Linux booted to a shell on the Pico itself, with both PSRAM chips and a real SD card.** Worked on
the first flash — no debugging cycle needed for either the multi-chip PSRAM port or the SD wiring.

**Config changed** (the only two lines): `PSRAM_TWO_CHIPS 0`→`1` (`hw_config.h`) and
`EMULATOR_RAM_MB 8`→`16` (`vm_config.h`). Build → 141312-byte `.uf2`, byte-size-identical to the
compile-only check recorded 2026-08-15, confirming nothing else drifted. `PSRAM_SPI_SPEED_MHZ`
stayed at 20 — **not** lowered; 20 MHz is stable with both chips on flying leads.

**Wiring.** Chip 2 shares SCLK/SI/SO with chip 1 and differs only in chip-select
(`/CE`→GPIO14/pin19 vs chip 1's GPIO13/pin17). SD module: `CS`→GPIO0/pin1, `CLK`→GPIO2/pin4,
`MOSI`→GPIO3/pin5, `MISO`→GPIO4/pin6, 3V3 + GND. Note the module's header order (CS, MOSI, CLK)
does **not** match the Pico's pin order (CS, CLK, MOSI) — those two wires cross, easiest mistake
to make here.

**SIO2/SIO3 handling — corrected from earlier sessions.** Both pins on both chips now tie to 3V3
through a single shared 10 kΩ (four pins on one node, one resistor to the rail). Reasoning, since
this got argued back and forth: on *this* part they have **no SPI-mode function at all** (datasheet
Table 2-1 lists `-` for both), unlike SPI-NOR flash where they are /WP and /HOLD. So direction is
functionally arbitrary here. Pulled **high** anyway because the risk is asymmetric — several
pin-compatible parts put an active-low /HOLD or /RESET on SIO3, and grounding that would hold such
a chip permanently in reset, while pulling high is harmless in every case. A shared resistor is
fine because nothing ever drives these pins: `psram.c` only ever sends `0x66`/`0x99`/`0x9F`/`0x03`/
`0x0B`/`0x02` (verified by grep), all single-SPI — no `0x35` Enter-Quad-Mode, so the chip never
drives SIO2/SIO3. Total current through the resistor is leakage only (~8 µA for four pins, ~0.08 mV
drop). **Note the datasheet's power-up section says `SI/SO/SIO[3:0]` should be low through the
150 µs init window — that is a sequencing constraint on what the master drives, not a static wiring
directive** (it also covers SI/SO, which obviously aren't tied low). Chip 1 had run with these pins
floating in the 2026-08-25 grading session and worked; tying them is an improvement, not a bug fix.

**SD card prep.** Copied `IMAGE`/`DTB`/`ROOTFS` straight out of `harness/disk.img` (the known-good
`net-v1` contents) onto a stock-FAT32 14.6 GB card — no reformat needed, no `dd` of a raw image.
Per PLAN.md item #6's standing lesson, verified by **sha256 comparison of each file against the
source image**, not just size, and confirmed `curl`/`sysinfo`/`nano` present in the ext2 via
`debugfs -R "stat ..."` before ejecting. All three matched.

**Verified on hardware:**
- `[mem 0x0000000080000000-0x0000000080ffefff]` in the kernel's own boot log — exactly 16 MB, so
  both chips are mapped and addressable.
- `[15.932599] VFS: Mounted root (ext2 filesystem) readonly on device 254:0` — SD served the
  kernel, DTB and the 60 MB rootfs; `254:0` is `0xfe00`, the custom-CSR block device.
- `free` reports **13040 KB total** (16384 KB physical, ~3344 KB kernel image + reserved).
- **Chip 2's data path proven by measurement, not inference.** `dd if=/dev/zero of=/dev/memtest
  bs=1k count=4000` (devtmpfs is RAM-backed and writable even with root read-only) then `cat` it
  back: clean, and `free` showed `buff/cache` rise 508→4528 KB and return to 528 KB after `rm`.
  Peak usage ≈ 3344 KB kernel + 2144 used + 4528 cache ≈ **10016 KB**, against chip 1's 8192 KB
  capacity — so ≥1.8 MB necessarily lived on chip 2 (pigeonhole, independent of allocator
  behaviour). Written, read back, and freed with no fault.
- **GNU nano runs and saves on real hardware** — `/dev/nanotest` read back with its typed contents.

**Real hardware is ~45× slower than the desktop harness** (root mounted at 15.9 s vs 0.34 s on the
same image). This is the first real calibration number, and it retires the blocker on the parked
"throttle the harness to hardware speed" idea — see that section, which was waiting on exactly
this figure. Practical consequence: a full-screen nano redraw that is instant in the harness takes
a long, easily-misread-as-hung time on hardware.

**Two scares that turned out to be nothing** (recorded so they aren't re-chased):
- *"nano froze on Ctrl+X."* It hadn't — the saved file was intact with its typed contents. It was
  the ~45× slowdown on a full-screen redraw.
- *"`df` kernel panicked."* `df` **does not exist in this rootfs** (confirmed by running the same
  image in the harness, which prints a clean `sh: can't execute 'df'`). On a healthy boot the
  hardware prints the identical clean error. Not reproducible; most likely a knock-on from a
  session already wedged by interrupting nano. **Root cause not confirmed** — if a panic ever
  recurs, capture the text (`screen`'s `Ctrl+A h` hardcopy) before resetting.
- Also normal, appears identically in the harness: `modprobe: module 'tinyrv32ima_spi' not found`.

**Published as [`pico-rv32ima-boards-v2`](https://github.com/flyboy-byte/riscv-pico/releases/tag/pico-rv32ima-boards-v2)**
(2026-08-27) — all four board targets rebuilt with the two-chip 16 MB config, plus `sdtest.uf2`,
with wiring tables in the bundled `README.txt`. `pico-rv32ima-boards-v1` was edited to carry a
superseded warning: it holds the single-chip 8 MB builds, which were never flashed *and* no longer
boot the current rootfs (open item #5). Toolchain (`toolchain-v2`), `apps-v1`, `net-v1` and
`rv32harness-v1` all confirmed still intact on GitHub the same date.

**Rootfs command inventory** (saves a round of "command not found" — this build is minimal, and
`df`, `head`, `md5sum`, `grep`, `vi` are all absent):
```
/bin      busybox cat dd dmesg echo false hush ls mkdir mount ping rm sh sync true umount uname
/usr/bin  clear curl free getconf nano printf resize sysinfo uptime  (+ iio_* tools)
/sbin     halt ifconfig init lsmod modprobe reboot route slattach
```
Root mounts **read-only**, so write tests must target `/dev` (devtmpfs). Deliberately avoid
`mount -o remount,rw /` on hardware — item #2 documents ext2 corruption on abrupt power-off, and
hardware has no clean shutdown path.

**Serial gotchas worth knowing:** the Pico re-enumerates to a *different* `/dev/ttyACM*` number
after reflash/reset (a stale `screen` holding the old node makes it look dead) — `screen
/dev/ttyACM* 115200` sidesteps guessing. Only one reader can own the port: running a capture script
and `screen` simultaneously makes both receive interleaved, corrupted text. `screen` eats **Ctrl+A**
(its own escape — matters for nano, send it as `Ctrl+A A`), and **Ctrl+S** silently freezes output
until `Ctrl+Q`, which is an easy false "it crashed".

### Side experiment: Pi 4B as a fake SD card (2026-08-26)

While the real SD card/breakout module was in transit, tried wiring a spare Pi 4B directly to
the Pico and making it answer `mmcbbp.c`'s SD-over-SPI protocol — a Claude session physically
connected to that Pi ("pi-05") did the Pi-side work, coordinated live with this session over
`SendMessage`. **Real result, not just a scoping exercise:** full SD init handshake working
reliably, plus a byte-perfect 512-byte `CMD17` sector read with real CRC16 integrity checking
and automatic retry — went further than the one comparable precedent found online (a forum
thread where someone else tried the same idea and never got bidirectional communication
working). Ruled out the Pi's *hardware* SPI-slave peripheral (BSC) as a genuine dead end first
(confirmed real electrical signals were reaching the pins via `edge_probe.py`, so it wasn't
wiring — the peripheral itself just doesn't reliably engage with an external master; matches a
well-known `pigpio` maintainer's own account of never getting it working). The thing that
actually worked was a real-time C program bit-banging the SPI slave role directly over GPIO,
with the SD init handshake reliable at a slowed-down 20kHz clock.

**Not a path to actually booting Linux, and not meant to be** — a real boot needs ~126,000
sequential sector reads (kernel + rootfs) with zero tolerance for a single bad one, which is a
different scale of problem than "usually works." This was pursued explicitly as low-stakes
curiosity while waiting, not as a serious alternative to the real SD module. Full writeup,
working code (protocol FSM, the C bit-bang transport, tests, the BSC-path diagnostic tooling),
wiring table, and run instructions are in
[`experiments/pi4-sdcard-emulator/README.md`](experiments/pi4-sdcard-emulator/README.md) — kept
because it's a genuinely interesting, reusable result, not because it unblocks anything. The
Pico-side test client used to validate all of this (`firmware/sdtest/`) is a real, reusable
diagnostic firmware in its own right — standalone SD-SPI bring-up probe, not the full
`pico-rv32ima` build, useful for any future SD-wiring debugging regardless of what's on the
other end of the wire.

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

~~Not yet done: no CMakeLists/build script checked in~~ — DONE 2026-08-16, see `harness/build.sh`.
Disk image build still isn't scripted, just documented above.

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

**Unblocked 2026-08-27** — the missing calibration number now exists: real hardware mounted root at
15.9 s against the harness's 0.34 s on the identical image, i.e. **~45× slower**. That's a wall-clock
ratio on one boot, not a measured guest IPS, so it's a starting point for a throttle target rather
than a precise figure. Still not built, but no longer blocked on data.

Originally not done because: no real hardware benchmark existed to calibrate a target IPS against
(hardware was parked), so any number picked would have been a guess, not data. It also wouldn't help find the
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
build itself lives outside the repo at `/home/logan/.riscv-pico-scratch/repo/buildroot`.
**Correction, 2026-08-27: it does persist between sessions** — earlier text here claimed it was
ephemeral scratch that wouldn't survive, and that was wrong. Re-verified working that date: GCC
13.3.0, `BR2_TOOLCHAIN_BUILDROOT_WCHAR=y`, `elf2flt` present, and the full loop
(compile `apps/hello.c` → `debugfs` inject → boot in harness → `hello from riscv32 uclibc nommu`)
runs clean. **Check that path before rebuilding** — a toolchain rebuild is hours and is usually
unnecessary.
This section is the from-source recipe, kept for anyone who'd rather build their own than trust a
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

### Real GNU nano, cross-compiled and verified working (2026-08-16)

First real, non-trivial upstream program ported to this target — not a from-scratch app like
`basic.c`, an actual unmodified GNU nano 7.2 release, and the first thing exercising a full-screen
ncurses UI end to end (proves the desktop terminal app's VT100/`pyte` fix from last session
actually works, not just "should work").

**Built via buildroot's own package recipes, not hand-rolled autotools cross flags** — nano hard-
depends on ncurses (`libncursesw`), and buildroot already knows how to cross-compile both for this
exact uclibc/no-MMU/bFLT target, so this reuses that instead of fighting `./configure --host=...`
by hand. Same `buildroot-tiny-rv32ima` repo as the toolchain section above.

**Config changes needed** (on top of the stock `tinyrv32ima_defconfig` — the pristine defconfig
already has `BR2_PACKAGE_NCURSES=y`, just not the wide-char variant nano needs):
```
BR2_TOOLCHAIN_BUILDROOT_WCHAR=y     # toolchain itself needs wchar support baked in
BR2_PACKAGE_NCURSES_WCHAR=y         # widen the existing ncurses package
BR2_PACKAGE_NANO=y
BR2_PACKAGE_NANO_TINY=y             # strips justify/spell-check/etc — also drops nano's only
                                     # fork()/subprocess dependency, good on a no-MMU target
```
Apply with `make menuconfig`, or hand-edit `buildroot/.config` and run `make olddefconfig`.

**The toolchain needs a full rebuild first** — `wchar` support isn't optional-to-add later, it's a
toolchain-level flag. If starting from the published `toolchain-v1` release, that release predates
this and doesn't have it; rebuild from source using the recipe in the "Cross-compile toolchain"
section above (same gcc-12 host-compiler workaround applies), then:
```sh
cd buildroot
make HOSTCC=gcc-12 HOSTCXX=g++-12 toolchain   # rebuild, now with wchar
make HOSTCC=gcc-12 HOSTCXX=g++-12 ncurses nano
```
Output: `buildroot/output/target/usr/bin/nano` (bFLT, ~655 KB, statically linked — no separate
`.so` to inject) and `buildroot/output/target/usr/lib/libncursesw.a`.

**Terminfo — turned out to need zero extra work.** The rootfs (from the `images.zip` release asset)
already ships a full terminfo database at `/usr/share/terminfo` (`linux`, `vt100`, `vt220`, `xterm`
variants, etc., dated from the original 2025-08-27 build) — didn't need to inject anything for
`TERM=vt100` to work.

**Verified live, not just "compiles":** injected into `ROOTFS` the same way as `apps/*.c` (see
below), booted in `harness/rv32harness`, ran `nano /dev/nanotest` (root is mounted read-only, so
edited a devtmpfs path rather than a real file — that part's an artifact of the test, not of nano),
typed a line of text, saved (`^O`), exited (`^X`), then `cat`'d the file back out and got the exact
text written. Full nano UI rendered correctly over the raw console link: title bar, shortcut
footer, `[ Modified ]`/`[ Wrote 2 lines ]` status messages, the works.

**One real gotcha worth recording:** feeding nano a bare `\n` (LF) for what should be an Enter
keypress does nothing useful — ncurses puts the tty in raw mode once nano starts, so `\n` lands as
literal `Ctrl+J` ("Unbound key" in nano's status line), not "confirm"/"newline". Needs `\r` (CR)
instead. Doesn't affect normal keyboard use (a real terminal's Enter key sends `\r`), only matters
when scripting input via a pipe like this session's test did.

**Published as GitHub releases (2026-08-16), not committed to git** — same reasoning as the
original toolchain decision, this repo may be shared and opaque binary blobs don't belong in
commit history:
- [`toolchain-v2`](https://github.com/flyboy-byte/riscv-pico/releases/tag/toolchain-v2) — the
  wchar-enabled rebuild, supersedes `toolchain-v1`.
- [`apps-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/apps-v1) — prebuilt `hello`,
  `basic`, `nano` bFLT binaries (plus unstripped `.gdb` ELF originals), ready to inject into a
  rootfs without recompiling anything.

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
- **`sysinfo.sh`** (2026-08-17) — a neofetch-style banner, no cross-compile needed (it's a shell
  script, just gets copied to `usr/bin/sysinfo` via buildroot's overlay mechanism, not `apps/`'s
  usual debugfs-inject path). Written for busybox `hush`, not bash — see the `curl`/`sysinfo`
  section below for why bash itself is a hard no on this target.

### `curl` and `sysinfo` — real userspace tools added (2026-08-17)

User asked for `neofetch` and `curl`. **`neofetch` is a hard no, not a config option**: it
`depends on BR2_USE_MMU` in buildroot (needs `bash`, which also `depends on BR2_USE_MMU`) — this is
a NOMMU target (RV32IMA has no MMU), so neither can ever be built for it, full stop. Confirmed by
reading `package/neofetch/Config.in` and `package/bash/Config.in` directly before doing any wasted
work. User's call once told: skip neofetch, write a `hush`-compatible equivalent instead
(`apps/sysinfo.sh` — banner + `uname`/`/proc/meminfo`/`/proc/uptime`, no bashisms).

**`curl` — real, working, HTTP-only.** `BR2_PACKAGE_LIBCURL` + `BR2_PACKAGE_LIBCURL_CURL`, no TLS
backend selected (buildroot's `olddefconfig` picked `BR2_PACKAGE_LIBCURL_TLS_NONE` automatically,
matching this build's minimal-footprint precedent — add `BR2_PACKAGE_LIBCURL_OPENSSL` or similar if
HTTPS is ever needed). No `BR2_USE_MMU` dependency, builds clean. Verified: `curl --version` prints
a real libcurl 8.7.1 banner under the emulator.

**Real bug found and fixed along the way: shell arithmetic was completely disabled.**
`CONFIG_FEATURE_SH_MATH` was `# not set` in this minimal busybox config — `sysinfo.sh`'s uptime
math (`$((UPTIME_SEC / 60))`) failed with `sh: can't execute 'UPTIME_SEC'` (hush tried to run the
literal text as a command instead of doing arithmetic). Enabled `CONFIG_FEATURE_SH_MATH` +
`CONFIG_FEATURE_SH_MATH_64`, confirmed fixed.

Regression-tested clean against the new rootfs (boot, nano round-trip, loopback networking).
Kernel+rootfs republished to `net-v1`; `sysinfo` also added to `apps-v1`.

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
- **D-007** — Second accepted exception to D-003, on `main` this time (not a side branch): a 3-call-
  site `#ifdef PICO_DEFAULT_LED_PIN` guard in `main.c`/`hal/hal_sd.h`, needed to make `pico_w`/
  `pico2_w` board targets build at all (those boards have no GPIO LED). Software-only, no
  emulator/PSRAM logic touched, `pico`/`pico2` byte-identical `.uf2` output before and after.
  (2026-08-16)

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

### Pico 2 / RP2350 (2W) support — scoped on paper 2026-08-16, built and verified in software the same day (later pass)

Evidence tagged **DOCUMENTED** (read directly from source/SDK headers), **REPORTED** (community
consensus, no primary source), or **INFERRED** (derived, not directly sourced) — same convention as
the hardware-readiness audit above. No hardware exists to verify any of this; D-005 (hardware
parked) still applies — everything below is a real `cmake --build`, not a flash.

**Update, same day, later pass: the paper scoping below held up.** All four board targets
(`pico`, `pico_w`, `pico2`, `pico2_w`) build clean against SDK 2.1.1. The build-system claim ("just
works, zero code changes") was *almost* exactly right — one small fix was needed that the paper
scoping missed: `_w` boards have no `PICO_DEFAULT_LED_PIN` (LED lives on the CYW43 chip's own SPI,
not a plain GPIO — the Pico-W audit finding quoted below flagged this pin *routing* but not that
`pico-rv32ima`'s own code unconditionally uses the symbol). `main.c`'s boot-LED init and
`hal/hal_sd.h`'s `sd_led_on`/`sd_led_off` now guard with `#ifdef PICO_DEFAULT_LED_PIN`. Confirmed
`pico`/`pico_w` still build identically to before (byte-identical `.uf2` sizes: 140800/138240) — no
regression on the boards that already worked. All four `.uf2`s published as GitHub release
`pico-rv32ima-boards-v1`. The PIO-count unknown noted below is still genuinely open — nothing at
compile/link time exercises PIO block count, so this doesn't confirm or rule it out, just doesn't
block the build.

**Existing RP2350 accommodation is minimal — DOCUMENTED.** The *only* RP2350-specific code anywhere
in the vendored tree is `main.c:21-34`'s `#ifdef PICO_RP2350A` branch, which picks a different
`vreg_set_voltage` constant (`RP2350_OVERVOLT VREG_VOLTAGE_1_30` vs RP2040's `VREG_VOLTAGE_MAX`) —
both still target 400MHz. Nothing else in the codebase branches on RP2350 vs RP2040.

**Clarifying, not a risk: RP2350's Hazard3 RISC-V core is irrelevant here.** `boards/pico2.h` sets
`PICO_PLATFORM=rp2350` — the board's Cortex-M33 ARM core, same architecture family as RP2040's
Cortex-M0+. `tiny-rv32ima` is a software RV32IMA interpreter compiled as ordinary C for whichever
core builds the firmware; it has nothing to do with RP2350's optional hardware Hazard3 RISC-V core
(`PICO_PLATFORM=rp2350-riscv`, not used or wanted here).

**Build system already just works — DOCUMENTED.** Top-level `CMakeLists.txt` has `PICO_BOARD` as a
plain CMake cache variable (`set(PICO_BOARD pico CACHE STRING ...)`) — `-DPICO_BOARD=pico2` or
`pico2_w` overrides it with zero code changes needed anywhere else in the tree.

**Pico 2 W's CYW43 pin conflict is identical to original Pico W — DOCUMENTED, confirmed by direct
comparison of `boards/pico2_w.h` against `boards/pico_w.h`.** Same GPIO set: `WL_REG_ON=23`,
`WL_DATA=24`, `WL_CS=25`, `WL_CLOCK=29`. This repo's existing Pico-W audit finding (GPIO23/24/25/29
off-limits, `PICO_DEFAULT_LED_PIN` routed through the wireless chip's SPI, GPIO29/VSYS double-duty)
transfers to Pico 2 W unchanged — doesn't need to be re-derived per-board.

**Multi-chip PSRAM port's GPIO14 — INFERRED conflict-free on both variants.** GPIO14 doesn't appear
in either RP2350 board header's pin assignments (UART/I2C/SPI/CYW43/flash) — same conclusion the
original single-Pico-W audit reached, now checked against RP2350 headers too.

**Genuine open unknown, honestly can't be resolved on paper — REPORTED/INFERRED only.** RP2350 has
3 PIO blocks vs RP2040's 2 (superset, documented as backward-compatible by Raspberry Pi, but not
independently verified against a primary PIO ISA diff here) — the VGA console and PS/2 driver both
use PIO (`console/vga/pio/*.pio.h`, `console/ps2/ps2.c`). PIO/SPI hardware-timing behavior is
exactly the class of bug that doesn't surface from reading source; needs a real board.

**Effort read, split by variant:**
- **Plain Pico 2** — low risk. "Should build and run, mostly untested," not a real porting job. The
  only honest gap is PIO/SPI timing, hardware-only.
- **Pico 2 W** — same low risk *if* wireless itself is never actually used (not a current project
  goal; the CYW43 pins simply stay reserved/unused, same as they'd be on any Pico W build). Actually
  driving the wireless chip would be real, separate integration work, not a board-flag flip — but
  nothing here needs that.

No blockers found on paper for either variant.

### Networking for the guest (Pico 2 W target) — scoped 2026-08-16, kernel-side half built and verified same day (later pass)

User's stated vision: a Pico 2 W running this project's Linux with working networking. D-005 still
applies — no hardware to test against, this is all emulator/software work. Evidence-tagged per the
same DOCUMENTED/REPORTED/INFERRED convention as the hardware audit above.

**Update, same day, later pass: the "networking fully compiled out" gap is closed and verified,
end to end, in the guest kernel.** `board/tiny-rv32ima/linux-nommu.config` now sets `CONFIG_NET`,
`CONFIG_INET`, `CONFIG_UNIX`, `CONFIG_PACKET`, `CONFIG_SLIP`, `CONFIG_SLIP_COMPRESSED` (IPv6 left
off, not needed for the SLIP design below); `busybox.config` now enables `ifconfig`, `route`,
`ping`, `slattach`. Built via `buildroot-tiny-rv32ima`'s buildroot 2024.05 overlay, `HOSTCC=gcc-12
HOSTCXX=g++-12` (this host's default `gcc-16` fails building old-gnulib host tools like `m4` —
`-Werror=implicit-function-declaration` is on by default since GCC 14, a real, previously-unknown
gotcha now documented for next time). **Verified, not just compiled in:** booted the new kernel
under `harness/rv32harness-16mb`, `ifconfig lo up` brings up loopback, `ping -c N 127.0.0.1` gets
real ICMP replies at 0% packet loss — the full stack (netlink/route, INET, UNIX, PACKET protocol
families) registers and works. Confirmed no regression against the nano work from earlier in the
day (write/save/exit round-trip still passes). New kernel+rootfs now live in `harness/disk.img` and
published as GitHub release `net-v1`.

~~This is loopback-only — the actual SLIP-over-second-HVC-channel bridge described below is still
not built~~ — **superseded 2026-08-17**: the second HVC channel now exists and `guest→host` works;
`host→guest` hits a real, unresolved console-freeze bug. Full current status is open item #1 at the
top of this file — don't rely on this paragraph, it's the pre-Phase-1 snapshot.

~~A real, separate finding from this build... Not fixed — noted for a future pass~~ — **partially
fixed 2026-08-17**: `desktop_terminal.py` now sends `sync` before terminating (see open item #2 at
the top). Not a complete fix (only covers app-controlled shutdown paths), still tracked as open.

**Recommendation: SLIP over a second HVC console channel, not a new CSR-based NIC.** **DOCUMENTED**
(`tiny-rv32ima/emulator/emulator.c:395-465` + the kernel's own
`0001-mini-rv32ima-HVC-driver.patch`): the existing console is CSRs `0x139`/`0x140` (putchar/
getchar, one byte polled at a time), wired into the guest via a genuinely tiny (66-line) driver on
top of the **mainline Linux hvc framework**, which already supports multiple ports by `vtermno` —
a second channel is `hvc_alloc(1, ...)` plus one more CSR pair, not a new subsystem. SLIP
(`drivers/net/slip/slip.c`) is decades-old, MMU-agnostic, and attaches to *any* tty via `slattach`
in userspace. So this reduces to "one more hvc instance + stock SLIP + stock lwIP framing on the
RP2350 side" — reusing two already-proven mainline pieces instead of designing a new ring-buffer/
DMA-style CSR-MMIO protocol from scratch.

**Real finding, previously unflagged: the guest kernel has networking fully compiled out today.**
**DOCUMENTED** (`board/tiny-rv32ima/linux-nommu.config`): zero `CONFIG_NET*`/`CONFIG_INET*` lines
are set, and `busybox.config` confirms `ifconfig`/`slattach`/`udhcpc` are all `# not set`. So the
real scope is "bring up the network stack from nothing" (`CONFIG_NET`, `INET`, `UNIX`, `PACKET`,
`SLIP` + busybox net tools) — config-only, no kernel source patches needed beyond the one new hvc
channel, but bigger than "flip one option on."

**RAM budget** — **INFERRED** likely fine on the 16MB config (current kernel is ~1.7MB code with
~14MB free, a minimal net stack + SLIP is on the order of a few hundred KB), not independently
re-checked against the default 8MB/1-chip config.

**Real risk, not just more work: throughput.** **INFERRED** from the CSR design itself — both
console bytes today are polled one-at-a-time with no interrupt path. SLIP over that same model will
almost certainly work correctly but be slow. "Network works" is realistic; "network is fast" isn't
a promise this design shape can make.

**RP2350 side** — **REPORTED** (standard, documented SDK pattern): `cyw43_arch_lwip_poll()`-style
polling fits directly into `console_task()`'s existing core0 loop (core1 stays dedicated to the
emulator, no new threading model needed). Rough shape: a few hundred lines bridging CSR byte I/O ↔
SLIP framing ↔ lwIP raw API ↔ `cyw43_arch` — gluing three mature libraries, not inventing a
protocol.

**Effort/risk verdict: multi-session feature, not a single sitting — but no wall found.** Every
piece (hvc multi-port, SLIP, lwIP polling) is a known, mainline, MMU-agnostic mechanism already
designed for exactly this shape of narrow-channel networking. The two things that will only really
surface with a real board: actual throughput, and whether `cyw43_arch`'s init sequence shares core0
cleanly with `console_task()`.

### Desktop harness as a real app — built and verified, 2026-08-16

User wants the desktop harness to feel like a real software package, not a raw CLI binary. Built
and smoke-tested (via `QT_QPA_PLATFORM=offscreen`, scripted — window creation, RAM switch actually
swapping binaries, reboot keeping the subprocess alive, recent-files persistence/ordering, and
`TerminalWidget.set_size()` all verified; ~~not yet clicked through by a human in a real
session~~ — DONE later the same session, live GUI use found and fixed two real bugs, see below):

- **`harness/build.sh`** — new. Builds `rv32harness-8mb` and `rv32harness-16mb` from the same
  source via `-DEMULATOR_RAM_MB=N` (now `#ifndef`-guarded in `harness/vm_config.h` instead of a
  bare `#define`, so it's overridable at compile time without touching the file per build). The old
  single `rv32harness` binary is gone — replaced by these two, `desktop_terminal.py` picks between
  them.
- **RAM-config switch — shipped as the build-matrix approach decided earlier**, not a runtime
  parameter into vendored `tiny-rv32ima` code. Machine → RAM Config menu (radio-button style,
  `QActionGroup`) picks which prebuilt binary to relaunch against; disabled/grayed if `--binary` was
  passed explicitly (then there's no way to know which RAM configs are even available). Keeps
  D-003's "stay pristine" promise intact — zero changes to vendored emulator/cache code, at the cost
  of two binaries to keep in sync.
- **Reboot** — Machine → Reboot (`Ctrl+R`): terminates the subprocess, resets the terminal screen
  (`pyte`'s own `screen.reset()`), relaunches against the same binary+disk image. No emulator-side
  support needed, matches a real hardware reboot's semantics reasonably well (cold restart, not a
  live reset).
- **File → Open Disk Image... / Recent** — `QFileDialog` picker plus a persisted recent-files list
  (`harness/.recent_disk_images.json`, gitignored, newest-first, capped at 8). Switching disk image
  restarts the subprocess against the new image, same machinery as reboot.
- **Machine → TTY Size...** — prompts for cols/rows, calls `TerminalWidget.set_size()`. **Known,
  documented limitation, not a bug**: this only resizes the local display grid — there's no
  SIGWINCH-equivalent over the raw console link to tell the *guest* kernel/program the terminal
  changed size, so a running full-screen program (nano, etc.) won't reflow until the harness is
  restarted. Surfaced to the user via a status-bar message when they resize, not silently wrong.
- **`disk_img` argument is now optional** (defaults to `harness/disk.img`), `--ram {8,16}` replaces
  the old implicit-16MB-only behavior, `--binary` still available as an escape hatch for a custom
  build (disables the RAM-config menu since the harness can't know what RAM size a custom binary
  was compiled for).

**Real bug found and fixed the same day, from actual human use — not caught by this session's
earlier scripted verification.** User tried nano through the live app and line wrapping was
visibly broken. Root cause, confirmed empirically (not guessed): the guest has **no `TIOCGWINSZ`
support and no `stty` binary at all** on this custom console — `echo $COLUMNS $LINES` at the shell
comes back empty, and there's no ioctl path for a program to learn the real terminal size. ncurses'
fallback order is ioctl → `$COLUMNS`/`$LINES` env vars → terminfo's hardcoded default — with the
first two both unavailable, nano was silently rendering as if the terminal were 80×24 (vt100's
terminfo default) regardless of the actual window size. Verified directly: nano's title bar spans
*exactly* 80 columns with nothing set, vs. the real window width once `$COLUMNS`/`$LINES` are
exported — this wasn't a theory, it was measured both ways.

**Fix, first pass**: auto-inject `export COLUMNS=<cols> LINES=<rows>\n` once the first `~ #` prompt
is seen after boot. Verified: title-bar reverse-video run spans the full grid width (102/102 in the
test), not 80.

**User re-tested and it was still broken** — a real gap in the first pass, not a false report. Two
things it missed:
1. **A plain window drag-resize didn't re-sync at all** — only the explicit Machine → TTY Size
   dialog did. A user resizing the window the ordinary way (not through that menu) went stale
   again immediately.
2. **Blindly sending the export string on any resize is actually unsafe, not just incomplete** — if
   a full-screen program (nano) is already running when a resize happens, typing `export
   COLUMNS=...` at that moment types it *into the document*, not into a shell that doesn't exist
   at that moment. This would explain the user's report directly: nano opening but being
   unreadable.

**Fix, second pass**: `TerminalWidget` gained an `on_resize(cols, rows)` callback, fired from both
`set_size()` (the menu dialog) and the real Qt `resizeEvent` (an ordinary window drag) — one code
path covers both triggers now. Syncing itself is gated on an actual "idle at the shell prompt"
check (`_track_output`/`_on_output_quiet`), debounced on a 200ms output-quiet period rather than
firing the instant `~ #` appears anywhere in the stream — a program's own screen output could
transiently end in that exact 4-byte sequence mid-update (a filename, a status line), and a real
idle prompt is reliably followed by silence where a transient mid-stream match isn't. A resize that
happens while a program is running sets a pending flag instead of sending anything immediately, and
the deferred sync fires safely the next time the guest is confirmed back at the prompt.

**Verified with a scripted test exercising the actual danger case, not just the happy path**:
boot-sync fires; resizing while idle at the prompt syncs immediately (no pending flag); resizing
*while nano is actively running* correctly sets the pending flag and — confirmed by scanning nano's
own screen buffer afterward — injects nothing into the document; exiting nano back to the prompt
fires the deferred sync. An already-running program still won't reflow live — no `SIGWINCH`-
equivalent exists over this raw console link, a kernel-side change out of scope for an app-level
fix — but the app no longer corrupts what's on screen while getting there.

**User re-tested again and hit a third, more serious issue — a real screenshot (Spectacle,
2026-08-16) made this one unambiguous instead of guessed at.** Two separate things were visible in
it:
1. **Confirmed bug, now fixed: resize-triggered sync was spamming the shell.** The screenshot
   showed `export COLUMNS=76 LINES=18` / `19` / `20` / `21` fired back-to-back while the window was
   being dragged — `_on_term_resize`'s "safe to send" check was correct in isolation but got
   re-evaluated on *every single resize step* of a drag (a live drag fires many resize events), and
   nothing changes about "are we idle at the prompt" between steps once the shell has settled — so
   every step re-triggered a fresh send. **Fix**: resize itself is now debounced
   (`_resize_debounce`, 300ms) before the safety check ever runs (`_flush_resize_sync`) — a drag
   only produces one send, after it actually stops. Verified: 20 rapid resize steps in a scripted
   test produced zero sends during the drag and exactly one afterward, matching the final size. The
   running-program safety property (previous fix) still holds with the debounce in place — re-ran
   that same scripted check.
2. **The actual crash is unrelated to any of this — a kernel-level Oops, not a nano/userspace bug.**
   `epc: 8097613c` in the register dump is a kernel-space address (not inside nano's binary),
   `cause: 00000002` is RISC-V's standard exception code for illegal instruction — the *kernel*
   executed an instruction it couldn't decode. **Ruled out as something this session's changes
   caused**, checked by direct diff inspection, not just testing: the multi-chip PSRAM port
   (`psram.c`, the one piece of the normally-pristine emulator core touched this session) reduces
   to byte-for-byte the same behavior as the pre-port version when `PSRAM_TWO_CHIPS=0` (the only
   config the harness ever runs) — `local_addr = PSRAM_TWO_CHIPS ? (addr % ...) : addr` is just
   `addr`, `psram_select(addr)`/`psram_deselect(addr)` were already no-ops in
   `harness/hal_psram.h`. `cache.c` was never touched by the port at all (checked via `git log`).
   **Status: real, unexplained, and not reproduced under my own control** — multiple heavy stress
   tests (60-line files, cut/paste, arrow keys, rapid resize, both RAM configs) via scripted input
   never triggered it, so whatever causes it is either timing-sensitive in a way scripted input
   doesn't hit, or rare enough that it needs many more trials.

**Root cause found and fixed, 2026-08-16 — a screenshot with `Comm: nano` and a repeatable
`epc: 8097613c` was the key clue.** On this NOMMU platform there's no separate kernel/userspace
address space, so that address was misread earlier as "kernel code" — it's actually inside nano's
own binary, and `unhandled signal 4` (SIGILL) with `Comm: nano` confirms it's nano crashing, not
the kernel. Same *class* of bug this project already documented for `basic.c`: nano was compiled
with `-fPIC` and no `-pie`, not `-fPIE -pie`. My own `apps/*.c` builds never hit this because they
were compiled standalone with explicit flags, bypassing buildroot's package system entirely — nano
was the first thing built through buildroot's actual internal recipes, which was needed to expose
it. Traced to the real source: `package/Makefile.in` — buildroot's own upstream default for
`BR2_BINFMT_FLAT` + `BR2_riscv` is `TARGET_CFLAGS += -fPIC`, a deliberate buildroot convention that
conflicts with what this project's `elf2flt`/gotpic loader actually needs. Patched at that source
(not a one-off Makefile hack) to `-fPIE -pie` instead, confirmed the fix survives a full clean
rebuild through the normal `make ncurses nano` path (not just my manual test build), re-injected
into `harness/disk.img`'s `ROOTFS`, and re-ran the heaviest stress test from this session (typing,
arrow keys, cut/paste, save) 6 times clean with zero crashes — previously this reproduced reliably
under real GUI use. ~~Not yet done: buildroot itself lives in ephemeral scratch, not this repo, so
this patch needs to be reapplied if buildroot is re-cloned from scratch~~ — still true (patch lives
only in the scratch checkout, see "Reusable build environment" up top), but ~~the fixed `nano`
binary in `disk.img` hasn't been republished~~ — DONE, republished to `apps-v1` same session.

**"Pico vs Pico 2 vs 2W toggle" still doesn't live in the desktop app.** The harness is always
desktop x86; board selection (`-DPICO_BOARD=...`) is a real-hardware CMake build-time concern, a
separate axis from anything the terminal GUI controls. A `build.sh --board=pico2w`-style wrapper for
the *firmware* build (not the harness) is tracked as open item #4 above.

~~Not yet done: no human has actually clicked through the new menus in a live PyQt6 window this
session~~ — DONE later the same session (2026-08-16), found and fixed two real bugs via live use.
`.gitignore` updated (`harness/rv32harness*`,
`harness/.recent_disk_images.json`, `__pycache__/`) so none of the build outputs or local state
land in git, matching the toolchain/apps precedent of publishing binaries as GitHub releases
instead. Published as
[`rv32harness-v1`](https://github.com/flyboy-byte/riscv-pico/releases/tag/rv32harness-v1).

### What can actually run on this — scope question, answered 2026-08-15

Two different questions worth keeping separate:

**"Can I cross-compile and run other userspace programs (MicroPython, etc.)?"** Yes in principle —
the emulator boots a real, general-purpose Linux kernel, so anything cross-compiled for this exact
target (`riscv32ima`, no-MMU, uClibc, bFLT) is fair game, not just things purpose-built for this
project (`apps/hello.c`, `apps/basic.c` already prove the pipeline). MicroPython specifically means
its **unix port** (compiles as a normal Linux userspace binary), not the microcontroller/bare-metal
port. Real complexity, not a quick win like Tiny BASIC was: tens of thousands of lines vs. ~500,
own build system to wrestle into this toolchain, and a genuine unconfirmed risk that its GC heap
allocation assumes `mmap()`-backed paging, which doesn't really exist the same way under no-MMU
Linux. Not attempted; would need scoping (check for hard `mmap` dependencies) before committing to
it.

**"Can the emulator run non-Linux firmware — is it Linux-only?"** Not hardcoded to Linux, but
Linux is the only thing actually ported to it. The RV32IMA CPU core itself is general-purpose —
any correctly-compiled RV32IMA code executes correctly as instructions. But the "hardware" around
it (`tiny-rv32ima/emulator/emulator.c`) is a small, custom platform: fixed RAM offset, one
UART-like console, a CLINT-style timer, and the project's own custom block-device CSRs — built
specifically to run this nommu Linux port, nothing else. Existing firmware written for a real board
or a different emulated platform (QEMU's "virt" machine, etc.) would **not** boot as-is — different
memory map, different peripherals, no driver for this platform's specifics. Writing/porting
bare-metal firmware that specifically targets *this* emulator's actual memory map (no OS at all,
just RV32IMA instructions + the console CSR) is a real, different, and currently unexplored
direction — not gated by anything in the emulator itself, just never attempted.

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
