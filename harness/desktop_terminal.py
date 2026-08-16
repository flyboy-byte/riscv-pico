#!/usr/bin/env python3
"""Desktop terminal emulator for harness/rv32harness.

Real ANSI/VT100 interpretation via `pyte` (cursor movement, clear-screen, colors — the things
webconsole.py's browser page can't do), rendered in a custom-painted PyQt6 widget so it looks and
behaves like an actual terminal, not a scrolling log. Good enough for Tiny BASIC today; the point
is this is also the foundation for a full-screen editor (nano-alike) or curses-based programs
later, since it now handles cursor positioning correctly instead of stripping it.

Usage: python3 desktop_terminal.py <disk.img> [--binary path/to/rv32harness] [--cols N] [--rows N]
"""

import argparse
import subprocess
import sys
import threading
from pathlib import Path

import pyte
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPainter, QKeyEvent, QPalette
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QStatusBar

HARNESS_DIR = Path(__file__).resolve().parent

# pyte's named ANSI colors -> RGB. "default" is handled separately per fg/bg.
ANSI_COLORS = {
    "black": "#1e1e1e",
    "red": "#e06c75",
    "green": "#98c379",
    "brown": "#d19a66",  # pyte calls yellow "brown" in some palettes; keep both
    "yellow": "#e5c07b",
    "blue": "#61afef",
    "magenta": "#c678dd",
    "cyan": "#56b6c2",
    "white": "#dcdfe4",
    "brightblack": "#5c6370",
    "brightred": "#e88a94",
    "brightgreen": "#b0d68d",
    "brightyellow": "#eccf95",
    "brightblue": "#7fc1f5",
    "brightmagenta": "#d6a1e8",
    "brightcyan": "#7bd1db",
    "brightwhite": "#ffffff",
}
DEFAULT_FG = "#d6e2e6"
DEFAULT_BG = "#0b0d10"


def color_for(name, default):
    if name in (None, "default"):
        return QColor(default)
    if isinstance(name, str) and len(name) == 6:
        try:
            return QColor("#" + name)
        except Exception:
            pass
    return QColor(ANSI_COLORS.get(name, default))


class HarnessIO(QObject):
    data_received = pyqtSignal(bytes)
    exited = pyqtSignal()

    def __init__(self, binary, disk_img):
        super().__init__()
        self.proc = subprocess.Popen(
            [binary, disk_img],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self):
        while True:
            chunk = self.proc.stdout.read(1)
            if not chunk:
                self.exited.emit()
                return
            self.data_received.emit(chunk)

    def write(self, data: bytes):
        if self.proc.stdin:
            try:
                self.proc.stdin.write(data)
                self.proc.stdin.flush()
            except BrokenPipeError:
                pass


KEY_TO_BYTES = {
    Qt.Key.Key_Return: b"\n",
    Qt.Key.Key_Enter: b"\n",
    Qt.Key.Key_Backspace: b"\x7f",
    Qt.Key.Key_Tab: b"\t",
    Qt.Key.Key_Escape: b"\x1b",
    Qt.Key.Key_Up: b"\x1b[A",
    Qt.Key.Key_Down: b"\x1b[B",
    Qt.Key.Key_Right: b"\x1b[C",
    Qt.Key.Key_Left: b"\x1b[D",
    Qt.Key.Key_Home: b"\x1b[H",
    Qt.Key.Key_End: b"\x1b[F",
}


class TerminalWidget(QWidget):
    def __init__(self, cols, rows, on_input):
        super().__init__()
        self.on_input = on_input
        self.screen = pyte.HistoryScreen(cols, rows, history=5000)
        self.stream = pyte.Stream(self.screen)

        family = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
        self.font_ = QFont(family, 12)
        self.font_.setStyleHint(QFont.StyleHint.Monospace)
        self.font_.setFixedPitch(True)
        self.setFont(self.font_)

        metrics = self.fontMetrics()
        self.char_w = metrics.horizontalAdvance("M")
        self.char_h = metrics.height()

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.resize(self.char_w * cols, self.char_h * rows)

        self._blink = QTimer(self)
        self._blink.timeout.connect(self._toggle_cursor)
        self._blink.start(530)
        self._cursor_on = True

    def _toggle_cursor(self):
        self._cursor_on = not self._cursor_on
        self.update()

    def feed(self, data: bytes):
        self.stream.feed(data.decode("utf-8", errors="replace"))
        self.update()

    def resizeEvent(self, ev):
        cols = max(20, self.width() // self.char_w)
        rows = max(5, self.height() // self.char_h)
        if (cols, rows) != (self.screen.columns, self.screen.lines):
            self.screen.resize(rows, cols)
        super().resizeEvent(ev)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(DEFAULT_BG))
        p.setFont(self.font_)

        cursor = self.screen.cursor
        for row in range(self.screen.lines):
            line = self.screen.buffer[row]
            y = row * self.char_h
            for col in range(self.screen.columns):
                ch = line[col]
                is_cursor = (
                    self._cursor_on
                    and not cursor.hidden
                    and row == cursor.y
                    and col == cursor.x
                )
                # Resolve to real colors *before* swapping for reverse/cursor — swapping the
                # symbolic names first is a no-op when both are "default" (the common case: an
                # empty cell at the prompt), which made the cursor invisible almost everywhere.
                fg_color = color_for(ch.fg, DEFAULT_FG)
                bg_color = color_for(ch.bg, DEFAULT_BG)
                if ch.reverse or is_cursor:
                    fg_color, bg_color = bg_color, fg_color

                x = col * self.char_w
                if bg_color != QColor(DEFAULT_BG) or is_cursor:
                    p.fillRect(x, y, self.char_w, self.char_h, bg_color)

                if ch.data and ch.data != " ":
                    f = QFont(self.font_)
                    f.setBold(bool(ch.bold))
                    f.setUnderline(bool(ch.underscore))
                    p.setFont(f)
                    p.setPen(fg_color)
                    p.drawText(x, y + self.fontMetrics().ascent(), ch.data)
        p.end()

    def keyPressEvent(self, ev: QKeyEvent):
        key = ev.key()
        mods = ev.modifiers()

        if mods & Qt.KeyboardModifier.ControlModifier:
            text = ev.text()
            if text:
                code = ord(text.upper())
                if 65 <= code <= 90:
                    self.on_input(bytes([code - 64]))
                    return

        if key in KEY_TO_BYTES:
            self.on_input(KEY_TO_BYTES[key])
            return

        text = ev.text()
        if text:
            self.on_input(text.encode("utf-8", errors="ignore"))


class MainWindow(QMainWindow):
    def __init__(self, binary, disk_img, cols, rows):
        super().__init__()
        self.setWindowTitle(f"rv32harness — {Path(disk_img).name}")

        self.io = HarnessIO(binary, disk_img)
        self.term = TerminalWidget(cols, rows, self.io.write)
        self.setCentralWidget(self.term)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("connected")

        self.io.data_received.connect(self.term.feed)
        self.io.exited.connect(self._on_exit)

        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(DEFAULT_BG))
        self.setPalette(pal)

        self.resize(self.term.width() + 20, self.term.height() + 60)
        self.term.setFocus()

    def _on_exit(self):
        self.status.showMessage("harness exited")

    def closeEvent(self, ev):
        try:
            self.io.proc.terminate()
        except Exception:
            pass
        super().closeEvent(ev)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("disk_img")
    ap.add_argument("--binary", default=str(HARNESS_DIR / "rv32harness"))
    ap.add_argument("--cols", type=int, default=100)
    ap.add_argument("--rows", type=int, default=32)
    args = ap.parse_args()

    app = QApplication(sys.argv)
    win = MainWindow(args.binary, args.disk_img, args.cols, args.rows)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
