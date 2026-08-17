#ifndef HARNESS_NETCHAN_H
#define HARNESS_NETCHAN_H

// Second HVC channel, backed by a host PTY - bridges CSRs 0x141 (putc) / 0x142 (getc)
// to a real /dev/pts/N so slattach can be pointed at it from the host side.
void netchan_init(void);
void netchan_putc(char c);
int netchan_available(void);
char netchan_read(void);

#endif
