"""
server.py — Serveur HTTP multithread avec trois routes :

  GET /                      → page HTML (interface de visualisation)
  GET /stream.mjpg           → flux MJPEG (frames JPEG en multipart)
  GET /temperature/stream    → flux SSE   (JSON poussé à chaque mesure)

Les handlers MJPEG et SSE bloquent sur leur buffer respectif (Condition.wait)
et ne consomment pas de CPU entre deux frames/mesures.
"""

from __future__ import annotations

import json
import logging
from http import server
from socketserver import ThreadingMixIn

from buffers import JPEG_BUF, TEMP_BUF
from frontend import PAGE

log = logging.getLogger(__name__)

BOUNDARY = b"FRAME"


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

class StreamingHandler(server.BaseHTTPRequestHandler):

    # ── Routage ─────────────────────────────────────────────────────────────

    def do_GET(self):
        routes = {
            "/":                   self._serve_index,
            "/index.html":         self._serve_index,
            "/stream.mjpg":        self._serve_mjpeg,
            "/temperature/stream": self._serve_temperature_sse,
        }
        handler = routes.get(self.path)
        if handler:
            handler()
        else:
            self.send_error(404)
            self.end_headers()

    # ── Route : page HTML ────────────────────────────────────────────────────

    def _serve_index(self):
        content = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type",   "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control",  "no-cache")
        self.end_headers()
        self.wfile.write(content)

    # ── Route : flux MJPEG ───────────────────────────────────────────────────

    def _serve_mjpeg(self):
        self.send_response(200)
        self.send_header("Age",          "0")
        self.send_header("Cache-Control","no-cache, private")
        self.send_header("Pragma",       "no-cache")
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY.decode()}")
        self.end_headers()

        last_seq = 0
        try:
            while True:
                jpeg, last_seq = JPEG_BUF.wait_for_new(last_seq, timeout=2.0)
                if jpeg is None:
                    continue

                self.wfile.write(b"--" + BOUNDARY + b"\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode())
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
        except (BrokenPipeError, ConnectionResetError):
            pass    # client déconnecté — fermeture propre

    # ── Route : flux SSE température ─────────────────────────────────────────

    def _serve_temperature_sse(self):
        """
        Server-Sent Events : le serveur pousse un événement JSON à chaque
        nouvelle mesure du MLX90614, sans que le client ait à poller.

        Format SSE :
            data: {"ambient_c": 22.5, "object_c": 36.8, "timestamp": 1710000000.0}\n\n
        """
        self.send_response(200)
        self.send_header("Content-Type",  "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection",    "keep-alive")
        self.send_header("X-Accel-Buffering", "no")   # désactive le buffering nginx
        self.end_headers()

        last_seq = 0
        try:
            while True:
                sample, last_seq = TEMP_BUF.wait_for_new(last_seq, timeout=5.0)

                if sample is None:
                    # keepalive SSE : empêche la déconnexion par timeout du navigateur
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue

                payload = json.dumps({
                    "ambient_c": round(sample.ambient_c, 2),
                    "object_c":  round(sample.object_c,  2),
                    "timestamp": sample.timestamp,
                })
                self.wfile.write(f"data: {payload}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass    # client déconnecté

    # ── Logs ─────────────────────────────────────────────────────────────────

    def log_message(self, fmt, *args):
        log.debug("%s - %s", self.address_string(), fmt % args)


# ---------------------------------------------------------------------------
# Serveur
# ---------------------------------------------------------------------------

class ThreadedHTTPServer(ThreadingMixIn, server.HTTPServer):
    """Un thread par connexion cliente — la boucle principale n'est pas bloquée."""
    daemon_threads      = True
    allow_reuse_address = True


def create_server(host: str, port: int) -> ThreadedHTTPServer:
    httpd = ThreadedHTTPServer((host, port), StreamingHandler)
    log.info("Serveur démarré sur %s:%d", host, port)
    return httpd
