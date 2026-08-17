// Desktop harness copy of pico-rv32ima/pico-rv32ima/vm_config.h — trimmed, values unchanged.
#define SNAPSHOT_FILENAME "SNAP"

#define KERNEL_FILENAME "IMAGE"
#define BLK_FILENAME "ROOTFS"
#define DTB_FILENAME "DTB"

#define DTB_SIZE 2048

// Overridable at compile time (-DEMULATOR_RAM_MB=N) so the build can produce multiple
// fixed-RAM harness binaries — see harness/build.sh.
#ifndef EMULATOR_RAM_MB
#define EMULATOR_RAM_MB 16
#endif

// rw: no init script remounts root, and a read-only rootfs silently breaks anything writing
// to it (nano's save, /tmp files) with no error surfaced anywhere. Harness-only change — the
// upstream vm_config.h this mirrors is deliberately left untouched (see CLAUDE.md's scope fence).
#define KERNEL_CMDLINE "console=hvc0 root=fe00 rw"

#define EMULATOR_TIME_DIV 1
#define EMULATOR_FIXED_UPDATE 0

#define CACHE_LINE_SIZE 16
#define OFFSET_BITS 4
#define CACHE_SET_SIZE 4096
#define INDEX_BITS 12
