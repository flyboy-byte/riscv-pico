# buildroot-overlay

This is `buildroot_overlay/` from the persistent toolchain checkout at
`~/.riscv-pico-scratch/repo/buildroot_overlay/` — the actual source of the guest-side changes
that make this project's kernel different from stock Linux: the block device driver, the second
HVC channel, and the GPIO driver, plus the kernel/busybox config fragments and the rootfs overlay
files (`inittab`, `fstab`, `load_modules.sh`, `sysinfo`).

**Checked in 2026-08-29** after noticing it had never been tracked anywhere — the toolchain binary
is deliberately not checked in (it's rebuildable from a documented recipe, see PLAN.md's
"Cross-compile toolchain" section), but these are small, hand-written, and irreplaceable the same
way `apps/*.c` is. This copy is the record; the live working copy buildroot actually builds from
stays at `~/.riscv-pico-scratch/repo/buildroot_overlay/` — after editing a patch or config here,
copy it back there before rebuilding (`cp -r board ~/.riscv-pico-scratch/repo/buildroot_overlay/`).

- `board/tiny-rv32ima/patches/linux/6.6.18/` — numbered patch series against a pristine Linux
  6.6.18 tarball, applied by buildroot during the `linux` package build.
- `board/tiny-rv32ima/linux-nommu.config` — the kernel config (used as-is, not a fragment;
  `make olddefconfig` fills in anything unset).
- `board/tiny-rv32ima/busybox.config` — the busybox config.
- `board/tiny-rv32ima/overlay/` — files copied verbatim into the target rootfs.

See PLAN.md for the full rebuild recipe and the story behind each patch.
