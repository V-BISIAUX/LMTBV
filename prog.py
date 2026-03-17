import time
import threading
from http import server
from socketserver import ThreadingMixIn

import cv2
from picamera2 import Picamera2
import smbus2

# --- Configuration ---
HOST = "0.0.0.0"
PORT = 8000
JPEG_QUALITY = 80   # 1-100
FPS_LIMIT = 15
RESOLUTION = (640, 480)

# --- MLX90614 ---
I2C_BUS = 1
MLX_ADDR = 0x5A
REG_AMBIENT = 0x06
REG_OBJECT  = 0x07


class FrameBuffer:
    """
    Stocke la dernière frame JPEG.
    Utilise un threading.Condition pour notifier les clients HTTP
    dès qu'une nouvelle frame est disponible → latence minimale.
    """
    def __init__(self):
        self.condition = threading.Condition()
        self.jpeg = None

    def update(self, jpeg_bytes: bytes):
        with self.condition:
            self.jpeg = jpeg_bytes
            self.condition.notify_all()   # réveille tous les clients en attente

    def wait_for_frame(self, timeout=2.0):
        """Bloque jusqu'à la prochaine frame (ou timeout). Retourne le JPEG."""
        with self.condition:
            self.condition.wait(timeout)
            return self.jpeg


class TemperatureBuffer:
    """Stocke la dernière température MLX90614 (thread-safe)."""
    def __init__(self):
        self.lock = threading.Lock()
        self.ambient = None
        self.object  = None

    def update(self, ambient, obj):
        with self.lock:
            self.ambient = ambient
            self.object  = obj

    def get(self):
        with self.lock:
            return self.ambient, self.object


FRAMEBUF = FrameBuffer()
TEMPBUF  = TemperatureBuffer()


# ---------------------------------------------------------------------------
# Thread caméra
# ---------------------------------------------------------------------------
def camera_capture_loop():
    picam2 = Picamera2()
    config = picam2.create_video_configuration(
        main={"size": RESOLUTION, "format": "RGB888"},
        controls={"FrameRate": FPS_LIMIT},   # limite côté driver → moins de CPU
    )
    picam2.configure(config)
    picam2.start()

    try:
        while True:
            # capture_array() est bloquant : il attend la prochaine frame du driver.
            # Pas besoin de sleep manuel → latence réduite au minimum.
            frame = picam2.capture_array()

            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            frame_bgr = cv2.flip(frame_bgr, -1)   # rotation 180°

            ambient, obj = TEMPBUF.get()
            if ambient is not None:
                text = f"Amb: {ambient:.1f} C | Obj: {obj:.1f} C"
                cv2.putText(
                    frame_bgr, text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                    (0, 0, 255), 2, cv2.LINE_AA
                )

            ok, jpg = cv2.imencode(
                ".jpg", frame_bgr,
                [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
            )
            if ok:
                FRAMEBUF.update(jpg.tobytes())
    finally:
        picam2.stop()


# ---------------------------------------------------------------------------
# Thread température
# ---------------------------------------------------------------------------
def read_temp(bus, reg):
    raw  = bus.read_word_data(MLX_ADDR, reg)
    return (raw & 0xFFFF) * 0.02 - 273.15


def temperature_loop():
    bus = smbus2.SMBus(I2C_BUS)
    while True:
        try:
            ambient = read_temp(bus, REG_AMBIENT)
            obj     = read_temp(bus, REG_OBJECT)
            TEMPBUF.update(ambient, obj)
        except Exception as e:
            print("Erreur MLX90614 :", e)
        time.sleep(0.5)


# ---------------------------------------------------------------------------
# Serveur HTTP
# ---------------------------------------------------------------------------
PAGE = """\
<html>
<head>
  <title>Raspberry Pi MJPEG Stream</title>
  <style>
    body { margin: 0; background: #111; display: flex; justify-content: center; align-items: center; height: 100vh; }
    img  { max-width: 100%; image-rendering: auto; }
  </style>
</head>
<body>
  <img src="/stream.mjpg" />
</body>
</html>
"""


class StreamingHandler(server.BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            content = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        if self.path == "/stream.mjpg":
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type",
                             "multipart/x-mixed-replace; boundary=FRAME")
            self.end_headers()

            try:
                while True:
                    # Bloque ici jusqu'à ce qu'une nouvelle frame soit prête
                    jpeg = FRAMEBUF.wait_for_frame(timeout=2.0)
                    if jpeg is None:
                        continue

                    self.wfile.write(b"--FRAME\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(
                        f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
                    )
                    self.wfile.write(jpeg)
                    self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                return
            return

        self.send_error(404)
        self.end_headers()

    def log_message(self, format, *args):
        return   # silence


class ThreadedHTTPServer(ThreadingMixIn, server.HTTPServer):
    daemon_threads     = True
    allow_reuse_address = True


def main():
    threading.Thread(target=camera_capture_loop, daemon=True).start()
    threading.Thread(target=temperature_loop,    daemon=True).start()

    httpd = ThreadedHTTPServer((HOST, PORT), StreamingHandler)
    print(f"Stream prêt : http://IP_DU_PI:{PORT}/")
    httpd.serve_forever()


if __name__ == "__main__":
    main()