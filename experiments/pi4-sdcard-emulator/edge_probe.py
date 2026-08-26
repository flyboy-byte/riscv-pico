#!/usr/bin/env python3
"""
Cheap pre-check before committing to a C bit-bang rewrite: does ANY
electrical activity reach SCLK/MOSI/CE at all?

Uses pigpio's edge-count callbacks. Important: the *detection* of edges
happens in pigpiod's own DMA-based sampling loop in the daemon, which
samples at up to ~1MHz independent of Python's callback dispatch speed --
so this is reliable for catching a brief transaction even though Python
itself is too slow to bit-bang with. This only answers "did anything
toggle at all", not framing/protocol -- much cheaper than the full rewrite,
and tests the load-bearing assumption first.
"""
import pigpio
import time
import sys

SCLK, MOSI, MISO, CE = 19, 20, 18, 21

pi = pigpio.pi()
if not pi.connected:
    print("pigpiod not running / not connected", file=sys.stderr)
    sys.exit(1)

counts = {"SCLK": 0, "MOSI": 0, "CE": 0}


def make_cb(name):
    def cb(gpio, level, tick):
        counts[name] += 1
    return cb


for gpio in (SCLK, MOSI, MISO, CE):
    pi.set_mode(gpio, pigpio.INPUT)

cbs = [
    pi.callback(SCLK, pigpio.EITHER_EDGE, make_cb("SCLK")),
    pi.callback(MOSI, pigpio.EITHER_EDGE, make_cb("MOSI")),
    pi.callback(CE, pigpio.EITHER_EDGE, make_cb("CE")),
]

DURATION = 12
print(f"Watching SCLK(19)/MOSI(20)/CE(21) for {DURATION}s "
      f"(should span several Pico CMD0 attempts at 2s intervals)...")
print(f"Current levels: SCLK={pi.read(SCLK)} MOSI={pi.read(MOSI)} "
      f"MISO={pi.read(MISO)} CE={pi.read(CE)}")

start = time.time()
last_report = start
while time.time() - start < DURATION:
    time.sleep(0.5)
    now = time.time()
    if now - last_report >= 2:
        print(f"  t={now-start:4.1f}s  SCLK edges={counts['SCLK']:5d}  "
              f"MOSI edges={counts['MOSI']:5d}  CE edges={counts['CE']:5d}")
        last_report = now

for cb in cbs:
    cb.cancel()

print()
print(f"FINAL: SCLK edges={counts['SCLK']}  MOSI edges={counts['MOSI']}  "
      f"CE edges={counts['CE']}  over {DURATION}s")
if sum(counts.values()) == 0:
    print("=> ZERO electrical activity detected on any pin. This is upstream "
          "of any software (BSC or bit-bang) -- points at a genuine physical "
          "wiring/electrical issue, not a peripheral engagement problem.")
else:
    print("=> Activity detected -- signals ARE reaching the Pi. Points at a "
          "BSC-hardware-specific engagement limitation, and the bit-bang "
          "approach has a real electrical foundation to work with.")

pi.stop()
