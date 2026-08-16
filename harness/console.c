#include "console.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/select.h>
#include <unistd.h>

void console_putc(char c)
{
    putchar((unsigned char)c);
    fflush(stdout);
}

void console_puts(char *s)
{
    fputs(s, stdout);
    fflush(stdout);
}

void console_panic(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    exit(1);
}

int console_available(void)
{
    fd_set fds;
    struct timeval tv = {0, 0};
    FD_ZERO(&fds);
    FD_SET(STDIN_FILENO, &fds);
    return select(STDIN_FILENO + 1, &fds, NULL, NULL, &tv) > 0;
}

char console_read(void)
{
    char c = 0;
    if (read(STDIN_FILENO, &c, 1) != 1)
        return 0;
    return c;
}
