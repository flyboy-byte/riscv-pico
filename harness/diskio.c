// Desktop stand-in for pff/mmcbbp.c. pff.c only needs disk_initialize/disk_readp/disk_writep —
// it has no idea whether they're backed by real MMC-over-SPI or a plain file, so this skips the
// SD protocol entirely and serves 512-byte sectors straight out of a raw FAT image on disk.

#include "diskio.h"
#include "harness_disk.h"

FILE *harness_disk_img = NULL;

DSTATUS disk_initialize(void)
{
    return harness_disk_img ? 0 : STA_NOINIT;
}

DRESULT disk_readp(BYTE *buff, DWORD sector, UINT offset, UINT count)
{
    if (!harness_disk_img)
        return RES_NOTRDY;
    if (fseek(harness_disk_img, (long)sector * 512L + (long)offset, SEEK_SET) != 0)
        return RES_ERROR;
    if (buff)
    {
        if (fread(buff, 1, count, harness_disk_img) != count)
            return RES_ERROR;
    }
    return RES_OK;
}

#if PF_USE_WRITE
DRESULT disk_writep(const BYTE *buff, DWORD sc)
{
    if (!harness_disk_img)
        return RES_NOTRDY;

    if (buff)
    {
        // Data bytes for the sector write in progress.
        if (fwrite(buff, 1, sc, harness_disk_img) != sc)
            return RES_ERROR;
        return RES_OK;
    }

    if (sc)
    {
        // Initiate: sc is the sector number.
        if (fseek(harness_disk_img, (long)sc * 512L, SEEK_SET) != 0)
            return RES_ERROR;
        return RES_OK;
    }

    // Finalize.
    fflush(harness_disk_img);
    return RES_OK;
}
#endif
