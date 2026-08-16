// Desktop harness copy of pico-rv32ima/pico-rv32ima/vm_config.h — trimmed, values unchanged.
#define SNAPSHOT_FILENAME "SNAP"

#define KERNEL_FILENAME "IMAGE"
#define BLK_FILENAME "ROOTFS"
#define DTB_FILENAME "DTB"

#define DTB_SIZE 2048

#define EMULATOR_RAM_MB 16

#define KERNEL_CMDLINE "console=hvc0 root=fe00"

#define EMULATOR_TIME_DIV 1
#define EMULATOR_FIXED_UPDATE 0

#define CACHE_LINE_SIZE 16
#define OFFSET_BITS 4
#define CACHE_SET_SIZE 4096
#define INDEX_BITS 12
