#ifndef HARNESS_CONSOLE_H
#define HARNESS_CONSOLE_H

void console_putc(char c);
void console_puts(char *s);
void console_panic(const char *fmt, ...);
int console_available(void);
char console_read(void);

#endif
