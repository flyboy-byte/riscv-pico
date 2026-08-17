#include "netchan.h"

#include <fcntl.h>
#include <pty.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/select.h>
#include <termios.h>
#include <unistd.h>

static int master_fd = -1;

void netchan_init(void)
{
    int slave_fd;
    char slave_name[256];

    if (openpty(&master_fd, &slave_fd, slave_name, NULL, NULL) != 0)
    {
        perror("netchan: openpty");
        exit(1);
    }

    // Raw mode on the slave side, set before closing our own reference to it. A fresh pty
    // defaults to canonical (cooked) line discipline, which buffers input until a newline -
    // SLIP framing has no newlines, so without this every byte written here would sit stuck
    // in the tty layer, invisible to whatever opens the slave (slattach, or a test harness).
    struct termios raw;
    tcgetattr(slave_fd, &raw);
    cfmakeraw(&raw);
    tcsetattr(slave_fd, TCSANOW, &raw);
    close(slave_fd);

    // Non-blocking so netchan_available()'s select() + netchan_read() never stall the emulator's
    // main loop - same contract as console_available()/console_read() for the primary channel.
    int flags = fcntl(master_fd, F_GETFL, 0);
    fcntl(master_fd, F_SETFL, flags | O_NONBLOCK);

    fprintf(stderr, "netchan: second HVC channel available at %s (guest sees /dev/hvc1)\n", slave_name);
}

void netchan_putc(char c)
{
    if (master_fd < 0)
        return;
    // Best-effort: if the host side hasn't opened the slave yet, or the pty buffer is full,
    // drop the byte rather than block the emulator loop. SLIP/TTY layers above tolerate loss.
    write(master_fd, &c, 1);
}

int netchan_available(void)
{
    if (master_fd < 0)
        return 0;
    fd_set fds;
    struct timeval tv = {0, 0};
    FD_ZERO(&fds);
    FD_SET(master_fd, &fds);
    return select(master_fd + 1, &fds, NULL, NULL, &tv) > 0;
}

char netchan_read(void)
{
    char c = 0;
    if (master_fd < 0 || read(master_fd, &c, 1) != 1)
        return 0;
    return c;
}
