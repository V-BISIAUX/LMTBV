"""
PiCam Thermal Stream
====================
Point d'entrée principal. Lance les threads et démarre le serveur HTTP.
"""

import threading
from camera import CaptureThread, EncodeThread
from temperature import TemperatureThread
from server import create_server
from buffers import RAW_FRAME_BUF, JPEG_BUF, TEMP_BUF
from config import HOST, PORT


def main():
    # --- Threads de production de données ---
    CaptureThread(raw_buf=RAW_FRAME_BUF).start()
    EncodeThread(raw_buf=RAW_FRAME_BUF, jpeg_buf=JPEG_BUF).start()
    TemperatureThread(temp_buf=TEMP_BUF).start()

    # --- Serveur HTTP ---
    httpd = create_server(HOST, PORT)
    print(f"✓ Stream  →  http://<IP_DU_PI>:{PORT}/")
    print(f"✓ Température SSE  →  http://<IP_DU_PI>:{PORT}/temperature/stream")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
