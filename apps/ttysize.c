/* ttysize: show or set the console's window size.
 *
 * The VGA screen is 53 columns by 30 rows, but the kernel console reports 0x0, so nano and other
 * full-screen programs assume 80x24 and draw past the edge. The image has no `stty`, so inittab runs
 * `ttysize 30 53` at boot. Over USB serial with a normal-sized terminal, `ttysize 24 80` puts it
 * back.
 *
 *   ttysize              print "rows cols"
 *   ttysize ROWS COLS    set it
 */

#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>

int main(int argc, char **argv)
{
    struct winsize ws = {0};

    if (argc == 3) {
        ws.ws_row = atoi(argv[1]);
        ws.ws_col = atoi(argv[2]);
        if (ioctl(0, TIOCSWINSZ, &ws) != 0) {
            perror("ttysize");
            return 1;
        }
        return 0;
    }
    if (argc != 1) {
        fprintf(stderr, "usage: ttysize [ROWS COLS]\n");
        return 2;
    }
    if (ioctl(0, TIOCGWINSZ, &ws) != 0) {
        perror("ttysize");
        return 1;
    }
    printf("%d %d\n", ws.ws_row, ws.ws_col);
    return 0;
}
