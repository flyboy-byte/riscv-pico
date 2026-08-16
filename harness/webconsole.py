#!/usr/bin/env python3
"""Live browser console for harness/rv32harness.

Spawns the desktop emulator harness as a subprocess, streams its stdout to any browser tab
connected to /stream (Server-Sent Events), and accepts input from either the browser or a plain
curl POST to /input — so a person watching the page and a script (Claude, a test runner, whatever)
can both drive the same running VM.

No third-party dependencies — stdlib only, meant to be thrown away as easily as it was written.

Usage: python3 webconsole.py <disk.img> [--port 8765] [--ram 16]
"""

import argparse
import html
import http.server
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent

clients_lock = threading.Lock()
clients = []  # list[queue.Queue[bytes]]
backlog_lock = threading.Lock()
backlog = bytearray()
BACKLOG_MAX = 200_000

proc = None


def broadcast(chunk: bytes):
    with backlog_lock:
        backlog.extend(chunk)
        if len(backlog) > BACKLOG_MAX:
            del backlog[: len(backlog) - BACKLOG_MAX]
    with clients_lock:
        for q in clients:
            q.put(chunk)


def reader_thread(p: subprocess.Popen):
    while True:
        chunk = p.stdout.read(1)
        if not chunk:
            broadcast(b"\r\n[harness exited]\r\n")
            return
        broadcast(chunk)


PAGE = """<!doctype html>
<meta charset="utf-8">
<title>rv32harness console</title>
<style>
  * { box-sizing: border-box; }
  html, body { height:100%; margin:0; }
  body { background:#0b0d10; color:#d6e2e6; font-family: ui-monospace, "Cascadia Code", Menlo,
         Consolas, monospace; display:flex; flex-direction:column; }
  #bar { padding:6px 12px; background:#14171a; border-bottom:1px solid #262b30; font-size:12px;
         color:#8a97a0; display:flex; align-items:center; gap:6px; flex-shrink:0; }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%; background:#2b6f4f; }
  .dot.off { background:#6f2b2b; }
  #term { flex:1; overflow-y:auto; padding:10px 12px; white-space:pre-wrap; word-break:break-all;
          font-size:13px; line-height:1.45; cursor:text; }
  #cursor { display:inline-block; width:0.6em; height:1.1em; background:#d6e2e6; vertical-align:text-bottom;
            animation: blink 1s step-end infinite; }
  @keyframes blink { 50% { opacity:0; } }
</style>
<div id="bar"><span class="dot" id="dot"></span><span id="status">connecting&hellip;</span> &mdash;
  click the console and just type. Ctrl-C sends SIGINT, Ctrl-L clears the screen.</div>
<div id="term" tabindex="0"><span id="out"></span><span id="cursor"></span></div>
<script>
const out = document.getElementById('out');
const term = document.getElementById('term');
const dot = document.getElementById('dot');
const status = document.getElementById('status');

// Not a real terminal emulator — just enough handling to make backspace/erase-line look right.
// The shell erases with BS (delete previous char) and ANSI CSI sequences like ESC[J
// (erase-to-end-of-line); since we only ever append at the true end of the buffer, "erase
// forward from cursor" is a no-op here, so CSI sequences are simply consumed and dropped
// rather than interpreted. State persists across chunks since a sequence can split across
// SSE messages.
let inEscape = false;
function append(text) {
  let buf = out.textContent;
  for (const ch of text) {
    if (inEscape) {
      if (/[A-Za-z]/.test(ch)) inEscape = false; // final byte of the CSI sequence
      continue;
    }
    if (ch === '\\x1b') inEscape = true;
    else if (ch === '\\b') buf = buf.slice(0, -1);
    else buf += ch;
  }
  out.textContent = buf;
  term.scrollTop = term.scrollHeight;
}

const es = new EventSource('/stream');
es.onmessage = (e) => append(atob(e.data));
es.onopen = () => { dot.classList.remove('off'); status.textContent = 'live'; };
es.onerror = () => { dot.classList.add('off'); status.textContent = 'reconnecting\\u2026'; };

term.addEventListener('click', () => term.focus());
term.focus();

function send(bytes) {
  fetch('/input', {method:'POST', body: bytes});
}

term.addEventListener('keydown', (ev) => {
  ev.preventDefault();
  let b = null;
  if (ev.ctrlKey && ev.key.length === 1) {
    // Ctrl-A..Ctrl-Z -> 0x01..0x1a (Ctrl-C = SIGINT, Ctrl-L = clear, Ctrl-D = EOF, etc.)
    const code = ev.key.toUpperCase().charCodeAt(0);
    if (code >= 65 && code <= 90) {
      if (ev.key.toLowerCase() === 'l') { out.textContent = ''; return; }
      b = String.fromCharCode(code - 64);
    }
  } else if (ev.key === 'Enter') b = '\\n';
  else if (ev.key === 'Backspace') b = '\\x7f';
  else if (ev.key === 'Tab') b = '\\t';
  else if (ev.key === 'ArrowUp') b = '\\x1b[A';
  else if (ev.key === 'ArrowDown') b = '\\x1b[B';
  else if (ev.key === 'ArrowRight') b = '\\x1b[C';
  else if (ev.key === 'ArrowLeft') b = '\\x1b[D';
  else if (ev.key.length === 1) b = ev.key;
  if (b !== null) send(b);
});
</script>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            import base64

            q = queue.Queue()
            with backlog_lock:
                initial = bytes(backlog)
            with clients_lock:
                clients.append(q)
            try:
                if initial:
                    self.wfile.write(b"data: " + base64.b64encode(initial) + b"\n\n")
                    self.wfile.flush()
                while True:
                    chunk = q.get()
                    self.wfile.write(b"data: " + base64.b64encode(chunk) + b"\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with clients_lock:
                    if q in clients:
                        clients.remove(q)
            return

        if self.path == "/backlog":
            with backlog_lock:
                body = bytes(backlog)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path == "/input":
            length = int(self.headers.get("Content-Length", 0))
            data = self.rfile.read(length)
            if proc and proc.stdin:
                proc.stdin.write(data)
                proc.stdin.flush()
            self.send_response(204)
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()


def main():
    global proc
    ap = argparse.ArgumentParser()
    ap.add_argument("disk_img")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--binary", default=str(HARNESS_DIR / "rv32harness"))
    args = ap.parse_args()

    proc = subprocess.Popen(
        [args.binary, args.disk_img],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
    )
    threading.Thread(target=reader_thread, args=(proc,), daemon=True).start()

    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"rv32harness console: http://127.0.0.1:{args.port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
