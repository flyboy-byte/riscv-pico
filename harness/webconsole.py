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
  body { background:#0b0d10; color:#d6e2e6; font-family: ui-monospace, Menlo, Consolas, monospace;
         margin:0; display:flex; flex-direction:column; height:100vh; }
  #bar { padding:8px 12px; background:#14171a; border-bottom:1px solid #262b30; font-size:13px;
         color:#8a97a0; }
  #out { flex:1; overflow-y:auto; padding:12px; white-space:pre-wrap; word-break:break-all;
         font-size:13px; line-height:1.4; }
  form { display:flex; border-top:1px solid #262b30; }
  input { flex:1; background:#14171a; color:#d6e2e6; border:0; padding:10px 12px; font:inherit;
          outline:none; }
  button { background:#2b6f4f; color:#fff; border:0; padding:0 18px; font:inherit; cursor:pointer; }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%; background:#2b6f4f;
         margin-right:6px; }
</style>
<div id="bar"><span class="dot"></span>rv32harness &mdash; live console</div>
<div id="out"></div>
<form id="f"><input id="i" autocomplete="off" placeholder="type a command, press enter"><button>send</button></form>
<script>
const out = document.getElementById('out');
function append(text) {
  out.textContent += text;
  out.scrollTop = out.scrollHeight;
}
const es = new EventSource('/stream');
es.onmessage = (e) => append(atob(e.data));
document.getElementById('f').addEventListener('submit', (ev) => {
  ev.preventDefault();
  const i = document.getElementById('i');
  fetch('/input', {method:'POST', body: i.value + '\\n'});
  i.value = '';
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
