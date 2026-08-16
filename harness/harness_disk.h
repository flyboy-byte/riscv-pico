#ifndef HARNESS_DISK_H
#define HARNESS_DISK_H

#include <stdio.h>

// Set by main() before vm_init_hw()/pf_mount() runs. A raw FAT-formatted disk image standing in
// for the SD card — diskio.c serves sectors straight out of it.
extern FILE *harness_disk_img;

#endif
