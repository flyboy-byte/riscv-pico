#!/usr/bin/env python3
"""Desktop terminal emulator for harness/rv32harness.

Real ANSI/VT100 interpretation via `pyte` (cursor movement, clear-screen, colors — the things
webconsole.py's browser page can't do), rendered in a custom-painted PyQt6 widget so it looks and
behaves like an actual terminal, not a scrolling log. Proven against real full-screen programs
(GNU nano) as well as line-based ones (Tiny BASIC).

A real little app now, not just a CLI wrapper: Machine menu (reboot, RAM config, TTY size), File
menu (open disk image, recent files). RAM config is a choice of which prebuilt `rv32harness-Nmb`
binary to launch — see harness/build.sh — not a live runtime switch; EMULATOR_RAM_MB is baked into
the vendored tiny-rv32ima core at compile time, so switching RAM means relaunching the subprocess
against a different binary, same as a real reboot with different hardware would.

**Terminal-size sync**: the guest has no `TIOCGWINSZ`/`stty` on this custom console — ncurses
programs (nano) fall back to their terminfo default (80x24 for TERM=vt100) with no way to learn the
real grid size, which visibly corrupts wrapping/positioning the moment the actual window isn't
80x24 (confirmed: nano's title bar spans exactly 80 columns without this, vs. the real window width
with it). Fixed by auto-injecting `export COLUMNS=<cols> LINES=<rows>` at the shell (ncurses
respects these env vars when the ioctl isn't available) — both after boot and after any resize
(menu-driven or a plain window drag, `TerminalWidget`'s `on_resize` callback covers both). This is
debounced against a "quiet output + tail ends in the shell prompt" check (`_track_output` /
`_on_output_quiet`) rather than fired blindly — typing a shell command the instant a resize happens
would land *inside* whatever's currently running (nano, etc.) if it's not actually at a prompt, not
in the shell. An already-running full-screen program still won't reflow live — no SIGWINCH-
equivalent exists over this raw console link — only the next thing launched picks up the new size.

Usage: python3 desktop_terminal.py [disk.img] [--binary path/to/rv32harness] [--ram 8|16]
                                    [--cols N] [--rows N]
"""

import argparse
import json
import subprocess
import sys
import threading
from pathlib import Path

import pyte
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPainter, QKeyEvent, QPalette, QAction, QActionGroup
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QStatusBar,
    QFileDialog,
    QInputDialog,
    QMessageBox,
)

HARNESS_DIR = Path(__file__).resolve().parent
RAM_CONFIGS = (8, 16)  # MB — must match the binaries harness/build.sh produces
SHELL_PROMPT = b"~ # "
RECENT_FILE = HARNESS_DIR / ".recent_disk_images.json"
MAX_RECENT = 8

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

    def terminate(self):
        try:
            self.proc.terminate()
        except Exception:
            pass


KEY_TO_BYTES = {
    # CR, not LF: raw-mode programs (nano) bind \n to literal Ctrl+J, not Enter.
    # Canonical line discipline (the plain shell) still line-ends on CR via ICRNL.
    Qt.Key.Key_Return: b"\r",
    Qt.Key.Key_Enter: b"\r",
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
    def __init__(self, cols, rows, on_input, on_resize=None):
        super().__init__()
        self.on_input = on_input
        self.on_resize = on_resize  # called with (cols, rows) whenever the grid size changes
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

    def reset(self):
        self.screen.reset()
        self.update()

    def set_size(self, cols, rows):
        self.screen.resize(rows, cols)
        self.resize(self.char_w * cols, self.char_h * rows)
        self.update()
        if self.on_resize:
            self.on_resize(cols, rows)

    def resizeEvent(self, ev):
        cols = max(20, self.width() // self.char_w)
        rows = max(5, self.height() // self.char_h)
        if (cols, rows) != (self.screen.columns, self.screen.lines):
            self.screen.resize(rows, cols)
            if self.on_resize:
                self.on_resize(cols, rows)
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


def _load_recent():
    try:
        return json.loads(RECENT_FILE.read_text())
    except Exception:
        return []


def _save_recent(paths):
    try:
        RECENT_FILE.write_text(json.dumps(paths))
    except Exception:
        pass


def _binary_for_ram(mb):
    return HARNESS_DIR / f"rv32harness-{mb}mb"


class MainWindow(QMainWindow):
    def __init__(self, binary, disk_img, cols, rows, ram_mb=None):
        super().__init__()
        # ram_mb is None when --binary was given explicitly (a fixed, non-standard binary) —
        # the RAM-config menu only makes sense when we know which prebuilt binary we're on.
        self.fixed_binary = binary if ram_mb is None else None
        self.ram_mb = ram_mb
        self.disk_img = disk_img
        self.io = None

        self.term = TerminalWidget(cols, rows, self._send_input, on_resize=self._on_term_resize)
        self.setCentralWidget(self.term)

        self._quiet_timer = QTimer(self)
        self._quiet_timer.setSingleShot(True)
        self._quiet_timer.timeout.connect(self._on_output_quiet)

        self._resize_debounce = QTimer(self)
        self._resize_debounce.setSingleShot(True)
        self._resize_debounce.timeout.connect(self._flush_resize_sync)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(DEFAULT_BG))
        self.setPalette(pal)

        self._build_menu()
        self._start(self._current_binary(), disk_img)

        self.resize(self.term.width() + 20, self.term.height() + 60)
        self.term.setFocus()

    def _current_binary(self):
        return self.fixed_binary or _binary_for_ram(self.ram_mb)

    def _send_input(self, data):
        if self.io:
            self.io.write(data)

    def _build_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("&File")
        open_act = QAction("&Open Disk Image...", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self._pick_disk_image)
        file_menu.addAction(open_act)

        self.recent_menu = file_menu.addMenu("Recent")
        self._rebuild_recent_menu()

        file_menu.addSeparator()
        exit_act = QAction("E&xit", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        machine_menu = mb.addMenu("&Machine")
        reboot_act = QAction("&Reboot", self)
        reboot_act.setShortcut("Ctrl+R")
        reboot_act.triggered.connect(self._reboot)
        machine_menu.addAction(reboot_act)

        machine_menu.addSeparator()
        ram_menu = machine_menu.addMenu("RAM Config")
        self.ram_group = QActionGroup(self)
        self.ram_group.setExclusive(True)
        for mb_size in RAM_CONFIGS:
            act = QAction(f"{mb_size} MB", self, checkable=True)
            act.setChecked(self.ram_mb == mb_size)
            act.setEnabled(self.fixed_binary is None and _binary_for_ram(mb_size).exists())
            act.triggered.connect(lambda checked, m=mb_size: self._switch_ram(m))
            self.ram_group.addAction(act)
            ram_menu.addAction(act)
        if self.fixed_binary is not None:
            ram_menu.setTitle("RAM Config (fixed — using --binary)")

        machine_menu.addSeparator()
        tty_act = QAction("&TTY Size...", self)
        tty_act.triggered.connect(self._pick_tty_size)
        machine_menu.addAction(tty_act)

    def _rebuild_recent_menu(self):
        self.recent_menu.clear()
        recent = _load_recent()
        if not recent:
            empty = QAction("(none yet)", self)
            empty.setEnabled(False)
            self.recent_menu.addAction(empty)
            return
        for path in recent:
            act = QAction(path, self)
            act.triggered.connect(lambda checked, p=path: self._open_disk_image(p))
            self.recent_menu.addAction(act)

    def _remember_recent(self, path):
        recent = [p for p in _load_recent() if p != path]
        recent.insert(0, path)
        _save_recent(recent[:MAX_RECENT])
        self._rebuild_recent_menu()

    def _start(self, binary, disk_img):
        if not Path(binary).exists():
            QMessageBox.warning(
                self, "Missing binary",
                f"{binary} doesn't exist — run harness/build.sh first.",
            )
            return
        self._env_synced = False       # has the initial post-boot sync happened at all yet
        self._pending_resize = False   # a resize happened while we weren't confirmed idle at $
        self._tail = b""               # rolling recent-output buffer, for idle-at-prompt detection
        self.io = HarnessIO(str(binary), str(disk_img))
        self.io.data_received.connect(self.term.feed)
        self.io.data_received.connect(self._track_output)
        self.io.exited.connect(self._on_exit)
        self.disk_img = disk_img
        self.setWindowTitle(
            f"rv32harness — {Path(disk_img).name}"
            + (f" ({self.ram_mb}MB)" if self.ram_mb else "")
        )
        self.status.showMessage(f"connected — {Path(binary).name}")

    def _track_output(self, chunk):
        # Debounced "idle at a shell prompt" detector, used to safely auto-sync
        # $COLUMNS/$LINES (see _on_output_quiet). Debouncing on a quiet period, rather than
        # firing the instant "~ # " appears in the stream, matters for correctness, not just
        # politeness: a program's own screen output could transiently end in that exact
        # 4-byte sequence mid-stream (a filename, a status line), and immediately treating
        # that as "safe to type a shell command" risks typing into whatever's actually
        # running. Real idle prompts are followed by silence; transient mid-stream matches
        # are followed immediately by more output, so requiring quiet first filters this out.
        self._tail = (self._tail + chunk)[-256:]
        self._quiet_timer.start(200)

    def _on_output_quiet(self):
        if not self._tail.endswith(SHELL_PROMPT):
            return
        if not self._env_synced:
            self._env_synced = True
            self._send_env_size()
        elif self._pending_resize:
            self._pending_resize = False
            self._send_env_size()

    def _on_term_resize(self, cols, rows):
        # Never send anything directly from here — a live window drag fires this once per
        # pixel-step, and a naive "send if idle" check re-passes on every single step once
        # the shell settles (nothing new arrives to change that judgment between steps),
        # which was a real, confirmed bug: dragging the window spammed a fresh `export
        # COLUMNS=... LINES=...` at the shell for every intermediate size. Debounce the
        # resize itself first — only decide whether it's safe to send once resizing has
        # actually stopped for a moment (_flush_resize_sync), not on every intermediate step.
        if not self._env_synced:
            return  # initial boot sync hasn't happened yet, nothing to update
        self._pending_resize = True
        self._resize_debounce.start(300)

    def _flush_resize_sync(self):
        # Never blindly type a shell command here either — if a full-screen program (nano,
        # etc.) is currently running, that would type literally into it instead of into a
        # shell. Only send if we're confirmed idle at the prompt right now; otherwise leave
        # _pending_resize set so _on_output_quiet sends it once we're actually back at a
        # prompt (e.g. after the running program exits).
        if self._tail.endswith(SHELL_PROMPT) and not self._quiet_timer.isActive():
            self._pending_resize = False
            self._send_env_size()

    def _send_env_size(self):
        # $COLUMNS/$LINES are the fallback ncurses checks before its terminfo default — see
        # the module docstring for why the guest needs this at all (no TIOCGWINSZ here).
        cols, rows = self.term.screen.columns, self.term.screen.lines
        self._send_input(f"export COLUMNS={cols} LINES={rows}\n".encode())

    def _send_env_size(self):
        cols, rows = self.term.screen.columns, self.term.screen.lines
        self._send_input(f"export COLUMNS={cols} LINES={rows}\n".encode())

    def _restart(self, binary=None, disk_img=None):
        binary = binary or self._current_binary()
        disk_img = disk_img if disk_img is not None else self.disk_img
        if self.io:
            self.io.terminate()
        self.term.reset()
        self._start(binary, disk_img)
        self.term.setFocus()

    def _reboot(self):
        self._restart()

    def _switch_ram(self, mb_size):
        if not _binary_for_ram(mb_size).exists():
            QMessageBox.warning(
                self, "Missing binary",
                f"rv32harness-{mb_size}mb doesn't exist — run harness/build.sh first.",
            )
            return
        self.ram_mb = mb_size
        self._restart(binary=_binary_for_ram(mb_size))

    def _pick_disk_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open disk image", str(HARNESS_DIR), "Disk images (*.img);;All files (*)"
        )
        if path:
            self._open_disk_image(path)

    def _open_disk_image(self, path):
        self._remember_recent(path)
        self._restart(disk_img=path)

    def _pick_tty_size(self):
        cols, ok = QInputDialog.getInt(
            self, "TTY size", "Columns:", self.term.screen.columns, 20, 300
        )
        if not ok:
            return
        rows, ok = QInputDialog.getInt(
            self, "TTY size", "Rows:", self.term.screen.lines, 5, 100
        )
        if not ok:
            return
        # set_size() triggers on_resize -> _on_term_resize, which safely re-syncs
        # $COLUMNS/$LINES only once we're confirmed idle at the shell prompt (never types
        # into a program that's currently running — see _on_term_resize). There's still no
        # SIGWINCH-equivalent over this raw console link, so a program already running won't
        # reflow — this only helps things started after the resize.
        self.term.set_size(cols, rows)
        self.resize(self.term.width() + 20, self.term.height() + 60)
        self.status.showMessage(
            f"TTY resized to {cols}x{rows} — already-running full-screen programs won't reflow", 5000
        )

    def _on_exit(self):
        self.status.showMessage("harness exited")

    def closeEvent(self, ev):
        if self.io:
            self.io.terminate()
        super().closeEvent(ev)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("disk_img", nargs="?", default=str(HARNESS_DIR / "disk.img"))
    ap.add_argument("--binary", default=None, help="explicit harness binary (disables RAM-config menu)")
    ap.add_argument("--ram", type=int, choices=RAM_CONFIGS, default=16, help="RAM config in MB")
    ap.add_argument("--cols", type=int, default=100)
    ap.add_argument("--rows", type=int, default=32)
    args = ap.parse_args()

    app = QApplication(sys.argv)
    win = MainWindow(
        args.binary, args.disk_img, args.cols, args.rows,
        ram_mb=None if args.binary else args.ram,
    )
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
