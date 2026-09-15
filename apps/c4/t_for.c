int main()
{
  int i; int j; int n;
  n = 0;
  for (i = 0; i < 5; i++) for (j = 0; j < 3; j++) n = n + 1;
  printf("nested for: %d (want 15)\n", n);
  n = 0;
  for (i = 10; i > 0; i = i - 2) { n = n + i; }
  printf("counting down by 2: %d (want 30)\n", n);
  i = 0;
  for (;;) { i++; if (i == 7) { printf("empty for exited at %d (want 7)\n", i); i = 100; } if (i == 100) return write(1, "write works\n", 12) - 12; }
}
