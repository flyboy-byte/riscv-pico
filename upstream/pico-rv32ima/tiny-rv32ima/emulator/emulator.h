#ifndef _EMULATOR_H
#define _EMULATOR_H

#include <stdint.h>

enum emulatorCode
{
    EMU_POWEROFF,
    EMU_HIBERNATE,
    EMU_REBOOT,
    EMU_GET_SD,
    EMU_RUNNING,
    EMU_UNKNOWN
};

// Coarse "where is the VM up to" marker, for status displays. Advances monotonically
// through a boot; core 1 writes it, core 0 may read it.
enum vmStage
{
    VM_STAGE_INIT,     // nothing brought up yet
    VM_STAGE_PSRAM_OK, // PSRAM chips answered
    VM_STAGE_SD_OK,    // SD card mounted
    VM_STAGE_LOADING,  // copying kernel/DTB into PSRAM
    VM_STAGE_RUNNING,  // executing guest instructions
    VM_STAGE_HALTED    // guest powered off / rebooting
};

// Retired-instruction count, read from the emulated cycle CSR. Safe to call from the
// other core -- it retries around a torn 64-bit read.
uint64_t vm_get_instret(void);
uint8_t vm_get_stage(void);

int start_vm(int prev_power_state);
void vm_init_hw(void);
uint8_t vm_get_powerstate(void);
uint8_t vm_save_powerstate(uint8_t state);

#endif