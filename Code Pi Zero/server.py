"""
server.py — Serveur HTTP multithread avec quatre routes :

  GET /                      → page HTML
  GET /stream.mjpg           → flux MJPEG
  GET /temperature/stream    → flux SSE température MLX90614
  GET /esp/data              → dernière trame ESP8266 en JSON (polling)
"""

from __future__ import annotations

import json
import logging
import socket
from http import server
from socketserver import ThreadingMixIn

from buffers import JPEG_BUF, TEMP_BUF
from pi_receiver_usb import ESP_BUF
from frontend import PAGE

log = logging.getLogger(__name__)

BOUNDARY = b"FRAME"


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

class StreamingHandler(server.BaseHTTPRequestHandler):

    def do_GET(self):
        routes = {
            "/":                   self._serve_index,
            "/index.html":         self._serve_index,
            "/stream.mjpg":        self._serve_mjpeg,
            "/temperature/stream": self._serve_temperature_sse,
            "/esp/data":           self._serve_esp_data,
        }
        handler = routes.get(self.path)
        if handler:
            handler()
        else:
            self.send_error(404)
            self.end_headers()

    def _serve_index(self):
        content = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type",   "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control",  "no-cache")
        self.end_headers()
        self.wfile.write(content)

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

    def _serve_esp_data(self):
        """Retourne la dernière trame ESP8266 en JSON. 503 si aucune trame reçue."""
        data = ESP_BUF.get()
        if data is None:
            self.send_error(503, "Aucune donnée ESP disponible")
            return
        payload = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type",   "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control",  "no-cache")
        self.end_headers()
        self.wfile.write(payload)

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

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        super().server_bind()


def create_server(host: str, port: int) -> ThreadedHTTPServer:
    httpd = ThreadedHTTPServer((host, port), StreamingHandler)
    log.info("Serveur démarré sur %s:%d", host, port)
    return httpd
