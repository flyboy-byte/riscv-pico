#!/usr/bin/env python3
"""Pure software test of SDEmulator's FSM against a scripted mmcbbp.c-style
command sequence, with no pigpio/hardware involved."""
import sys
import types
import tempfile
import os
import binascii

# Stub pigpio so sdcard_emu.py imports cleanly without the real package.
sys.modules["pigpio"] = types.ModuleType("pigpio")

sys.path.insert(0, os.path.dirname(__file__))
from sdcard_emu import SDEmulator, Backing, CMD0, CMD8, CMD55, CMD41, CMD58, CMD17, CMD24  # noqa: E402


def cmd_frame(cmd, arg, crc, lead_dummy=1):
    """Build a wire-realistic command send: `lead_dummy` 0xFF filler bytes
    (mmcbbp.c's send_cmd() always sends exactly one via CS_L(); rcvr_mmc();)
    followed by the 6-byte command frame."""
    return bytes([0xFF] * lead_dummy) + bytes(
        [cmd, (arg >> 24) & 0xFF, (arg >> 16) & 0xFF, (arg >> 8) & 0xFF, arg & 0xFF, crc]
    )


def make_backing(size_sectors=64):
    f = tempfile.NamedTemporaryFile(delete=False)
    f.write(bytes(size_sectors * 512))
    f.close()
    return Backing(f.name), f.name


def drain(sd):
    out = bytes(sd.out)
    sd.out.clear()
    return out


def expect(label, got, want):
    ok = got == want
    print(f"[{'OK' if ok else 'FAIL'}] {label}: got={got!r} want={want!r}")
    return ok


def main():
    backing, path = make_backing()
    # put a recognizable sentinel in sector 5 so we can verify readback
    sentinel = bytes(range(256)) * 2
    backing.write_sector(5, sentinel)

    sd = SDEmulator(backing, verbose=True)
    all_ok = True

    # Exact sequence the standalone sdtest diagnostic firmware runs: CS high
    # dummy clocks never reach us (gated by real CS hardware, not simulated
    # here), then one CS-low dummy 0xFF, then the CMD0 frame.
    sd.feed(cmd_frame(CMD0, 0, 0x95, lead_dummy=1))
    all_ok &= expect("diagnostic-firmware CMD0 -> R1 idle", drain(sd), bytes([0x01]))

    # Robustness: tolerate more than one leading filler byte too (e.g. extra
    # clock slack), not just exactly one.
    sd.feed(cmd_frame(CMD8, 0x1AA, 0x87, lead_dummy=3))
    all_ok &= expect("multiple leading 0xFF tolerated (CMD8)", drain(sd),
                      bytes([0x01, 0x00, 0x00, 0x01, 0xAA]))

    sd.feed(cmd_frame(CMD55, 0, 0x01))
    all_ok &= expect("CMD55 -> R1 idle", drain(sd), bytes([0x01]))
    sd.feed(cmd_frame(CMD41, 1 << 30, 0x01))
    all_ok &= expect("ACMD41(HCS) -> R1 ready", drain(sd), bytes([0x00]))

    sd.feed(cmd_frame(CMD58, 0, 0x01))
    all_ok &= expect("CMD58 -> R1 + OCR (CCS set)", drain(sd), bytes([0x00, 0x40, 0x00, 0x00, 0x00]))

    sd.feed(cmd_frame(CMD17, 5, 0x01))
    got = drain(sd)
    # binascii.crc_hqx is stdlib's independent implementation of the same
    # algorithm (CRC-16/XMODEM: poly 0x1021, init 0x0000) -- a real
    # cross-check against our hand-rolled crc16_ccitt, not testing it
    # against itself.
    ref_crc = binascii.crc_hqx(sentinel, 0x0000)
    want = bytes([0x00, 0xFE]) + sentinel + bytes([(ref_crc >> 8) & 0xFF, ref_crc & 0xFF])
    all_ok &= expect("CMD17 lba=5 -> R1+token+512B+CRC (len)", len(got), len(want))
    all_ok &= expect("CMD17 lba=5 -> data matches sentinel", got[2:514], sentinel)
    all_ok &= expect("CMD17 lba=5 -> CRC16 matches independent binascii reference",
                      got[514:516], want[514:516])

    sd.feed(cmd_frame(CMD24, 9, 0x01))
    all_ok &= expect("CMD24 -> R1 ready", drain(sd), bytes([0x00]))
    write_payload = bytes([0xFF, 0xFE]) + bytes([0xAB]) * 512 + bytes([0x00, 0x00])
    sd.feed(write_payload)
    all_ok &= expect("write data-response -> 0x05 (accepted)", drain(sd), bytes([0x05]))
    all_ok &= expect("write landed in backing store",
                      backing.read_sector(9), bytes([0xAB]) * 512)

    # Busy-poll: drive through the REAL production path (feed), not an
    # internal method called directly -- this is exactly what the earlier
    # version of this test got wrong and let the dead-end bug through.
    sd.feed(bytes([0xFF]))
    all_ok &= expect("busy-poll answers 0xFF (via feed, real path)", drain(sd), bytes([0xFF]))
    all_ok &= expect("state returns to WAIT_CMD after busy-poll", sd.state, sd.WAIT_CMD)

    # Confirm the FSM is usable again immediately after (no leftover state).
    sd.feed(cmd_frame(CMD17, 5, 0x01))
    all_ok &= expect("FSM still works post-write", drain(sd)[:2], bytes([0x00, 0xFE]))

    os.unlink(path)
    print("\nALL OK" if all_ok else "\nSOME FAILED")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
