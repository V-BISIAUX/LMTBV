"""
PiCam Thermal Stream
====================
Point d'entrée principal. Lance les threads et démarre le serveur HTTP.
"""

import logging
import threading
from camera import CaptureThread, EncodeThread
from temperature import TemperatureThread
from pi_receiver_usb import EspReceiverThread
from server import create_server
from buffers import RAW_FRAME_BUF, JPEG_BUF, TEMP_BUF
from config import HOST, PORT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main():
    # --- Threads de production de données ---
    CaptureThread(raw_buf=RAW_FRAME_BUF).start()
    EncodeThread(raw_buf=RAW_FRAME_BUF, jpeg_buf=JPEG_BUF).start()
    TemperatureThread(temp_buf=TEMP_BUF).start()
    EspReceiverThread().start()

    # --- Serveur HTTP ---
    httpd = create_server(HOST, PORT)
    print(f"✓ Stream  →  http://<IP_DU_PI>:{PORT}/")
    print(f"✓ Température SSE  →  http://<IP_DU_PI>:{PORT}/temperature/stream")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
