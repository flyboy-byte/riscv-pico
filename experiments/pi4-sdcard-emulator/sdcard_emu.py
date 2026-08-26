#!/usr/bin/env python3
"""
SD-over-SPI emulator for the BCM2711 BSC peripheral in SPI-slave mode,
targeting tiny-rv32ima's pff/mmcbbp.c client exactly (not the general SD spec).

Verified against the real mmcbbp.c source (tvlad1234/tiny-rv32ima) on 2026-08-25.

Wiring (Pi is slave/"card", Pico is master):
  Pico CK   (GPIO2)  -> Pi SCLK (GPIO19)
  Pico MOSI (GPIO3)  -> Pi MOSI (GPIO20)
  Pico MISO (GPIO4)  <- Pi MISO (GPIO18)
  Pico CS   (GPIO0)  -> Pi CE   (GPIO21)
  GND <-> GND. Both sides 3.3V, no level shifting needed.

Protocol summary (see mmcbbp.c for ground truth):
  - Commands are 6 bytes: [0x40|cmd][arg3][arg2][arg1][arg0][crc]
  - CRC only matters for CMD0 (0x95) and CMD8 (0x87); everything else ignored.
  - Client polls up to 10 bytes for a response with the high bit clear.
  - Init sequence: CMD0 -> R1=0x01; CMD8(0x1AA) -> R1=0x01 + trailing
    [x,x,0x01,0xAA]; CMD55+ACMD41(HCS) polled until R1=0x00; CMD58 -> R1=0x00 +
    OCR trailing with bit6 of byte0 set (0x40...) to claim block addressing
    (CT_BLOCK) so CMD16 is skipped and sector numbers are raw LBA.
  - CMD17 (read): R1=0x00, then send 0xFF while "not ready", then 0xFE (data
    token), then 512 data bytes, then a real CRC16-CCITT (poly 0x1021, init
    0x0000, big-endian) over the sector -- the sdtest client validates this
    and retries the read on mismatch.
  - CMD24 (write): R1=0x00; client sends 0xFF,0xFE,512 bytes,2 CRC bytes;
    respond with a byte whose low 5 bits are 0x05 (accepted), then respond
    0xFF (ready) on the busy-poll read.

This FSM was originally written against the BSC hardware SPI-slave peripheral
(sdcard_emu.py's own main(), still usable standalone). BSC turned out not to
engage reliably with an external master on this hardware -- see bitbang_slave.c
and bitbang_bridge.py for the working real-time bit-banged GPIO transport that
replaced it. This module (SDEmulator/Backing/crc16_ccitt) is transport-agnostic
and is reused unchanged by both.
"""

import argparse
import sys
import time

import pigpio

SECTOR_SIZE = 512

# --- BSC control word bits (see pigpio docs for bsc_xfer) ---
BSC_EN = 1 << 0   # enable BSC peripheral
BSC_SP = 1 << 3   # enable SPI mode
BSC_PH = 1 << 5   # SPI clock phase
BSC_PL = 1 << 6   # SPI clock polarity
BSC_TE = 1 << 10  # enable transmit
BSC_RE = 1 << 11  # enable receive

CONTROL = BSC_EN | BSC_SP | BSC_RE | BSC_TE

# --- SD/MMC command bytes (0x40 | cmd_number), per mmcbbp.c ---
CMD0 = 0x40   # GO_IDLE_STATE
CMD8 = 0x48   # SEND_IF_COND
CMD16 = 0x50  # SET_BLOCKLEN (unused in CCS path, handled harmlessly anyway)
CMD17 = 0x51  # READ_SINGLE_BLOCK
CMD24 = 0x58  # WRITE_BLOCK
CMD55 = 0x77  # APP_CMD
CMD41 = 0x69  # ACMD41's actual wire byte (0x40 | 41) after CMD55 prefix
CMD58 = 0x7A  # READ_OCR

R1_IDLE = 0x01
R1_READY = 0x00

DATA_START_TOKEN = 0xFE
DATA_ACCEPTED = 0x05  # low 5 bits of the write data-response byte


def crc16_ccitt(data):
    """Standard SD data-block CRC: poly 0x1021, init 0x0000, no reflection,
    no final XOR (CRC-16/XMODEM). Returned big-endian on the wire."""
    crc = 0x0000
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


class Backing:
    """Sector-addressable backing store -- a FAT-formatted disk image."""

    def __init__(self, path):
        self.f = open(path, "r+b")
        self.f.seek(0, 2)
        self.size = self.f.tell()

    def read_sector(self, lba):
        off = lba * SECTOR_SIZE
        self.f.seek(off)
        data = self.f.read(SECTOR_SIZE)
        if len(data) < SECTOR_SIZE:
            data = data + b"\x00" * (SECTOR_SIZE - len(data))
        return data

    def write_sector(self, lba, data):
        assert len(data) == SECTOR_SIZE
        self.f.seek(lba * SECTOR_SIZE)
        self.f.write(data)
        self.f.flush()


class SDEmulator:
    """
    Byte-stream state machine. Feed it inbound bytes via feed(); it appends
    outbound bytes to self.out as they become ready. The main loop drains
    self.out into the BSC TX FIFO.
    """

    WAIT_CMD, SEND_R1, IF_COND_TAIL, OCR_TAIL, \
        READ_WAIT_READY, READ_SEND_TOKEN, READ_SEND_DATA, READ_SEND_CRC, \
        WRITE_WAIT_TOKEN, WRITE_RECV_DATA, WRITE_SEND_RESP, WRITE_WAIT_BUSY = range(12)

    def __init__(self, backing, verbose=False):
        self.backing = backing
        self.verbose = verbose
        self.out = bytearray()
        self.in_buf = bytearray()
        self.state = self.WAIT_CMD
        self.saw_cmd55 = False
        self.block_addressing_claimed = False
        self._read_data = b""
        self._read_pos = 0
        self._write_lba = 0
        self._write_buf = bytearray()

    def log(self, *a):
        if self.verbose:
            print(*a, file=sys.stderr)

    def feed(self, data):
        self.in_buf.extend(data)
        self._pump()

    def _pump(self):
        # Only the WAIT_CMD state consumes from in_buf in fixed 6-byte
        # frames; the WRITE_RECV_DATA state also consumes from in_buf
        # (514 bytes of data+CRC). Everything else is purely output-driven
        # and just needs pump() called again after out is drained.
        while True:
            if self.state == self.WAIT_CMD:
                # mmcbbp.c's send_cmd() always does CS_L(); rcvr_mmc(); --
                # one dummy 0xFF filler byte right after asserting CS, before
                # the real 6-byte command frame. Discard any leading 0xFF
                # filler (also covers 0xFF clocked while we're still
                # draining a previous response) before framing.
                while self.in_buf and self.in_buf[0] == 0xFF:
                    del self.in_buf[0]
                if len(self.in_buf) < 6:
                    return
                frame = bytes(self.in_buf[:6])
                del self.in_buf[:6]
                self._handle_command(frame)
            elif self.state == self.WRITE_WAIT_BUSY:
                # Client polls by clocking filler bytes waiting to read back
                # 0xFF (ready). Consume one filler byte per 0xFF we owe it.
                if not self.in_buf:
                    return
                del self.in_buf[0]
                self.out.append(0xFF)
                self.state = self.WAIT_CMD
            elif self.state == self.WRITE_RECV_DATA:
                # Wire frame here is fixed: 0xFF, 0xFE (header), 512 data
                # bytes, 2 CRC bytes = 516 total. Header/CRC aren't part of
                # the sector payload -- only bytes [2:514] are real data.
                need = 516 - len(self._write_buf)
                if len(self.in_buf) < need:
                    self._write_buf.extend(self.in_buf)
                    del self.in_buf[: len(self.in_buf)]
                    return
                self._write_buf.extend(self.in_buf[:need])
                del self.in_buf[:need]
                sector = bytes(self._write_buf[2:514])
                self.backing.write_sector(self._write_lba, sector)
                self.log(f"WRITE lba={self._write_lba} done")
                self.out.append(DATA_ACCEPTED)  # low 5 bits == 0x05
                self.state = self.WRITE_WAIT_BUSY
                return
            else:
                return

    def _handle_command(self, frame):
        cmd, a3, a2, a1, a0, _crc = frame
        arg = (a3 << 24) | (a2 << 16) | (a1 << 8) | a0
        self.log(f"CMD 0x{cmd:02x} arg=0x{arg:08x}")

        if cmd == CMD55:
            self.saw_cmd55 = True
            self.out.append(R1_IDLE)
            self.state = self.WAIT_CMD
            return

        was_acmd = self.saw_cmd55
        self.saw_cmd55 = False

        if cmd == CMD0:
            self.out.append(R1_IDLE)
            self.state = self.WAIT_CMD

        elif cmd == CMD8:
            self.out.append(R1_IDLE)
            self.out.extend([0x00, 0x00, 0x01, 0xAA])
            self.state = self.WAIT_CMD

        elif cmd == CMD41 and was_acmd:
            self.out.append(R1_READY)
            self.state = self.WAIT_CMD

        elif cmd == CMD58:
            self.out.append(R1_READY)
            self.out.extend([0x40, 0x00, 0x00, 0x00])  # CCS bit set
            self.block_addressing_claimed = True
            self.state = self.WAIT_CMD

        elif cmd == CMD16:
            self.out.append(R1_READY)
            self.state = self.WAIT_CMD

        elif cmd == CMD17:
            sector = self.backing.read_sector(arg)
            crc = crc16_ccitt(sector)
            self.out.append(R1_READY)
            self.out.append(DATA_START_TOKEN)
            self.out.extend(sector)
            self.out.extend([(crc >> 8) & 0xFF, crc & 0xFF])  # real CRC16, big-endian
            self.log(f"READ lba={arg} crc=0x{crc:04x}")
            self.state = self.WAIT_CMD

        elif cmd == CMD24:
            self.out.append(R1_READY)
            self._write_lba = arg
            self._write_buf = bytearray()
            self.state = self.WRITE_RECV_DATA

        else:
            self.log(f"unhandled cmd 0x{cmd:02x}, sending R1_READY")
            self.out.append(R1_READY)
            self.state = self.WAIT_CMD


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", help="path to FAT-formatted disk image (backing store)")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--i2c-addr", type=lambda x: int(x, 0), default=0x13,
                     help="BSC slave address field (unused in SPI mode but required by control word)")
    ap.add_argument("--toggle-en", action="store_true",
                     help="Disable then re-enable BSC every poll instead of leaving EN "
                          "continuously set. Speculative: based on one forum user's report "
                          "that FIFO bytes only get pulled on an EN 0->1 transition "
                          "(forums.raspberrypi.com t=119618), not documented behavior.")
    args = ap.parse_args()

    pi = pigpio.pi()
    if not pi.connected:
        print("could not connect to pigpiod -- is it running? (sudo pigpiod)", file=sys.stderr)
        sys.exit(1)

    backing = Backing(args.image)
    sd = SDEmulator(backing, verbose=args.verbose)

    control = CONTROL | ((args.i2c_addr & 0x7F) << 16)
    control_disabled = control & ~BSC_EN

    mode = "EN-toggling every poll" if args.toggle_en else "EN held continuously"
    print(f"SD emulator running against {args.image} ({backing.size} bytes), {mode}. Ctrl-C to stop.")
    try:
        while True:
            if args.toggle_en:
                pi.bsc_xfer(control_disabled, b"")
            send_chunk = bytes(sd.out[:16])
            del sd.out[: len(send_chunk)]
            status, count, data = pi.bsc_xfer(control, send_chunk)
            if count:
                sd.feed(data)
            elif not send_chunk and not sd.out:
                # nothing queued, nothing received -- avoid busy-spinning the CPU
                time.sleep(0.0005)
    except KeyboardInterrupt:
        pass
    finally:
        pi.bsc_xfer(0, [])  # disable BSC peripheral
        pi.stop()


if __name__ == "__main__":
    main()
