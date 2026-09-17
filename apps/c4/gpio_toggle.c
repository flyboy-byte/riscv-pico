// gpio_toggle.c: toggle GPIO line 0 with a for
// loop. c4 has no sleep yet, so on hardware this
// is too fast to see; it proves for + write.

int put(char *path, char *text, int len)
{
  int fd;
  fd = open(path, 1);
  if (fd < 0) return -1;
  write(fd, text, len);
  close(fd);
  return 0;
}

int main()
{
  int i; char *val;
  val = "/sys/class/gpio/gpio512/value";
  put("/sys/class/gpio/export", "512", 3);
  put("/sys/class/gpio/gpio512/direction",
      "out", 3);
  for (i = 0; i < 3; i++) {
    put(val, "1", 1);
    put(val, "0", 1);
  }
  // free the line again for gpioset
  put("/sys/class/gpio/unexport", "512", 3);
  printf("toggled %d times\n", i);
  return 0;
}
