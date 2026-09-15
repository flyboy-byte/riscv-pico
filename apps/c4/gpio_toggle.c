// gpio_toggle.c: toggle guest GPIO line 0 a few times with a for loop
// c4 has no sleep yet, so on real hardware this is too fast to see; it proves for + write.

int main()
{
  int fd; int i;
  fd = open("/sys/class/gpio/export", 1);
  if (fd >= 0) { write(fd, "512", 3); close(fd); }
  fd = open("/sys/class/gpio/gpio512/direction", 1);
  write(fd, "out", 3); close(fd);
  for (i = 0; i < 3; i++) {
    fd = open("/sys/class/gpio/gpio512/value", 1); write(fd, "1", 1); close(fd);
    fd = open("/sys/class/gpio/gpio512/value", 1); write(fd, "0", 1); close(fd);
  }
  printf("toggled %d times\n", i);
  return 0;
}
