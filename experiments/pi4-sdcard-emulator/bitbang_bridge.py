#!/usr/bin/env python3
"""
Bridges the C bit-bang hot loop (bitbang_slave) to the already-tested
SDEmulator FSM from sdcard_emu.py. The C side owns all timing-critical
bit-level GPIO work; this process just shuffles complete bytes over pipes
and runs the same protocol logic already verified in test_sdcard_emu.py.
"""
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from sdcard_emu import SDEmulator, Backing  # noqa: E402


def main():
    if len(sys.argv) != 2:
        print("usage: bitbang_bridge.py <disk-image>", file=sys.stderr)
        sys.exit(1)

    backing = Backing(sys.argv[1])
    sd = SDEmulator(backing, verbose=True)

    proc = subprocess.Popen(
        ["./bitbang_slave"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,  # let bitbang_slave's stderr print directly to our terminal
        bufsize=0,
    )

    print(f"bitbang_bridge: running against {sys.argv[1]}, PID {proc.pid}",
          file=sys.stderr)

    try:
        while True:
            b = proc.stdout.read(1)
            if not b:
                print("bitbang_slave exited", file=sys.stderr)
                break
            sd.feed(b)
            if sd.out:
                out = bytes(sd.out)
                sd.out.clear()
                print(f"  -> writing {len(out)}B to stdin: {out[:8].hex()}"
                      f"{'...' if len(out) > 8 else ''}", file=sys.stderr)
                proc.stdin.write(out)
                proc.stdin.flush()
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
