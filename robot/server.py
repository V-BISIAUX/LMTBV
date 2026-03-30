import json
import logging
import socket
from http import server
from socketserver import ThreadingMixIn
from pathlib import Path

import buffers
import fire_detector
from config import HOST, PORT

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static" # dossier contenant les fichiers HTML
BOUNDARY = b"FRAME" # séparateur utilisé dans le flux MJPEG


class Handler(server.BaseHTTPRequestHandler):

    # Table de correspondance URL vers méthode du handler
    ROUTES = {
        "/": "_index",
        "/index.html": "_index",
        "/stream.mjpg": "_mjpeg",
        "/temperature/stream": "_sse_temp",
        "/esp/data": "_esp_data",
        "/fires": "_fires",
    }

    def do_GET(self):
        # Dispatch les requêtes GET vers la bonne méthode selon l'URL
        method = self.ROUTES.get(self.path)
        if method:
            getattr(self, method)()
        else:
            self.send_error(404)

    def _index(self):
        # Sert la page HTML principale
        content = (STATIC / "index.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type",   "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control",  "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def _mjpeg(self):
        # Envoie un flux vidéo MJPEG en continu
        # Chaque image est envoyée comme une partie d'une requête HTTP multipart
        self.send_response(200)
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY.decode()}")
        self.end_headers()
        last_seq = 0
        try:
            while True:
                frame, last_seq = buffers.jpeg.wait_next(last_seq, timeout=2.0)
                if frame is None:
                    continue
                self.wfile.write(
                    b"--" + BOUNDARY + b"\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(frame)}\r\n\r\n".encode()
                    + frame + b"\r\n"
                )
        except (BrokenPipeError, ConnectionResetError):
            pass # le client a fermé la connexion, on arrête proprement

    def _sse_temp(self):
        # Envoie les mesures de température en temps réel via Server-Sent Events (SSE)
        # Le client reçoit un événement à chaque nouvelle mesure du capteur
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        last_seq = 0
        try:
            while True:
                sample, last_seq = buffers.temp.wait_next(last_seq, timeout=5.0)
                if sample is None:
                    # Envoie un commentaire vide pour maintenir la connexion active
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
            pass

    def _esp_data(self):
        # Retourne la dernière trame JSON reçue de l'ESP8266
        data = buffers.esp.get()
        if data is None:
            self.send_error(503, "Aucune donnée ESP disponible")
            return
        payload = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type",   "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control",  "no-cache")
        self.end_headers()
        self.wfile.write(payload)

    def _fires(self):
        # Retourne la liste de tous les incendies détectés au format JSON
        payload = json.dumps(fire_detector.get_all()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        # Redirige les logs HTTP vers le logger Python
        log.debug("%s %s", self.address_string(), fmt % args)


class _Server(ThreadingMixIn, server.HTTPServer):
    # Serveur HTTP multi-threadé : chaque connexion est gérée dans un thread séparé
    daemon_threads      = True # les threads s'arrêtent avec le programme principal
    allow_reuse_address = True

    def server_bind(self):
        # Options socket pour éviter les erreurs au redémarrage et réduire la latence
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        super().server_bind()


def start():
    httpd = _Server((HOST, PORT), Handler)
    log.info("Serveur HTTP sur %s:%d", HOST, PORT)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        log.info("Serveur arrêté.")