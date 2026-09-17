// gpio_set.c: set GPIO line 0 high or low
// (Pico GP1, physical pin 2)
// usage: c4 gpio_set.c 1   or   c4 gpio_set.c 0
// The line stays exported so it holds its level.
// To free it for gpioset:
//   echo 512 > /sys/class/gpio/unexport

int put(char *path, char *text, int len)
{
  int fd;
  fd = open(path, 1);
  if (fd < 0) {
    printf("cannot open %s\n", path);
    return -1;
  }
  write(fd, text, len);
  close(fd);
  return 0;
}

int main(int argc, char **argv)
{
  char *v;
  if (argc < 2) {
    printf("usage: c4 gpio_set.c 0|1\n");
    return 1;
  }
  v = argv[1];
  put("/sys/class/gpio/export", "512", 3);
  put("/sys/class/gpio/gpio512/direction",
      "out", 3);
  if (*v == '1')
    put("/sys/class/gpio/gpio512/value", "1", 1);
  else
    put("/sys/class/gpio/gpio512/value", "0", 1);
  printf("line 0 set to %c\n", *v);
  return 0;
}
