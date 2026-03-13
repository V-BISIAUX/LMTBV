import io
import time
import threading
from http import server
from socketserver import ThreadingMixIn

import cv2
from picamera2 import Picamera2
import smbus
import smbus2

# --- Configuration ---
HOST = "0.0.0.0" # écoute sur toutes les interfaces
PORT = 8000
JPEG_QUALITY = 80 # 1-100 (plus haut = meilleure qualité, plus lourd)
FPS_LIMIT = 15 # limite d'envoi (pour alléger le Pi)
RESOLUTION = (640, 480)

# --- MLX90614 ---
I2C_BUS = 1
MLX_ADDR = 0x5A
REG_AMBIENT = 0x06
REG_OBJECT = 0x07


class FrameBuffer:
    """Stocke la dernière frame JPEG, thread-safe."""
    def __init__(self):
        self.lock = threading.Lock()
        self.jpeg = None
        self.timestamp = 0.0

    def update(self, jpeg_bytes: bytes):
        with self.lock:
            self.jpeg = jpeg_bytes
            self.timestamp = time.time()

    def get(self):
        with self.lock:
            return self.jpeg, self.timestamp
            
class TemperatureBuffer:
    """Stocke la dernière température MLX90614 (thread-safe)."""
    def __init__(self):
        self.lock = threading.Lock()
        self.ambient = None
        self.object = None
        self.timestamp = 0.0

    def update(self, ambient, obj):
        with self.lock:
            self.ambient = ambient
            self.object = obj
            self.timestamp = time.time()

    def get(self):
        with self.lock:
            return self.ambient, self.object, self.timestamp


FRAMEBUF = FrameBuffer()
TEMPBUF = TemperatureBuffer()


def camera_capture_loop():
    """Capture en boucle, encode en JPEG et met à jour FRAMEBUF."""
    picam2 = Picamera2()
    config = picam2.create_video_configuration(
        main={"size": RESOLUTION, "format": "RGB888"}
    )
    picam2.configure(config)
    picam2.start()

    delay = 1.0 / max(1, FPS_LIMIT)
    last = 0.0

    try:
        while True:
            now = time.time()
            if now - last < delay:
                time.sleep(0.001)
                continue
            last = now

            frame = picam2.capture_array() # RGB
            # OpenCV attend plutôt BGR, mais pour JPEG ça n'a pas d'importance si on ne traite pas.
            # Si tu veux afficher correctement en OpenCV côté client, on garde un encodage standard.
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            ambient, obj, _ = TEMPBUF.get()

            if ambient is not None:
                text = f"Amb: {ambient:.1f} C | Obj: {obj:.1f} C"
                cv2.putText(
                    frame_bgr,
                    text,
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                    cv2.LINE_AA
                )
            
            ok, jpg = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
            if ok:
                FRAMEBUF.update(jpg.tobytes())
    finally:
        picam2.stop()

def read_temp(bus, reg):
    raw = bus.read_word_data(MLX_ADDR, reg)
    temp = (raw & 0xFFFF) * 0.02 - 273.15
    return temp


def temperature_loop():
    bus = smbus.SMBus(I2C_BUS)

    while True:
        try:
            ambient = read_temp(bus, REG_AMBIENT)
            obj = read_temp(bus, REG_OBJECT)
            TEMPBUF.update(ambient, obj)
        except Exception as e:
            print("Erreur MLX90614 :", e)

        time.sleep(0.5)


PAGE = """\
<html>
<head>
<title>Raspberry Pi MJPEG Stream</title>
</head>
<body>
<h1>MJPEG Stream</h1>
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
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=FRAME")
            self.end_headers()

            try:
                while True:
                    jpeg, ts = FRAMEBUF.get()
                    if jpeg is None:
                        time.sleep(0.01)
                        continue

                    self.wfile.write(b"--FRAME\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode("utf-8"))
                    self.wfile.write(jpeg)
                    self.wfile.write(b"\r\n")

                    # petit sleep pour éviter de saturer inutilement
                    time.sleep(0.001)
            except (BrokenPipeError, ConnectionResetError):
                # client a fermé
                return

        self.send_error(404)
        self.end_headers()

    def log_message(self, format, *args):
        # évite de spammer la console
        return


class ThreadedHTTPServer(ThreadingMixIn, server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    t_cam = threading.Thread(target=camera_capture_loop, daemon=True)
    t_temp = threading.Thread(target=temperature_loop, daemon=True)

    t_cam.start()
    t_temp.start()

    httpd = ThreadedHTTPServer((HOST, PORT), StreamingHandler)
    print(f"Stream prêt : http://IP_DU_PI:{PORT}/")
    httpd.serve_forever()


if __name__ == "__main__":
    main()