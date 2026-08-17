#include <stdio.h>

#include "emulator.h"
#include "harness_disk.h"
#include "netchan.h"

int main(int argc, char **argv)
{
    if (argc < 2)
    {
        fprintf(stderr, "usage: %s <fat-disk-image>\n", argv[0]);
        return 1;
    }

    harness_disk_img = fopen(argv[1], "r+b");
    if (!harness_disk_img)
    {
        perror("fopen");
        return 1;
    }

    netchan_init();
    vm_init_hw();

    int vm_state = EMU_GET_SD;
    while (1)
        vm_state = start_vm(vm_state);
}
