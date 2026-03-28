import threading
import logging
import cv2
from picamera2 import Picamera2

import buffers
from config import RESOLUTION, FPS_LIMIT, JPEG_QUALITY, FLIP_IMAGE, ENCODE_RESOLUTION

log = logging.getLogger(__name__)


def capture():
    cam = Picamera2()
    cam.configure(cam.create_video_configuration(
        main={"size": RESOLUTION, "format": "RGB888"},
        controls={"FrameRate": FPS_LIMIT},
    ))
    cam.start()
    log.info("Caméra démarrée : %s @ %d fps", RESOLUTION, FPS_LIMIT)
    try:
        while True:
            buffers.raw_frame.put(cam.capture_array())
    finally:
        cam.stop()


def encode():
    last_seq = 0
    while True:
        frame, last_seq = buffers.raw_frame.wait_next(last_seq)
        if frame is None:
            continue

        # Si plusieurs frames ont été produites pendant l'encodage, sauter à la plus récente
        latest, latest_seq = buffers.raw_frame.get_with_seq()
        if latest_seq > last_seq:
            frame, last_seq = latest, latest_seq

        bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        if FLIP_IMAGE:
            bgr = cv2.flip(bgr, -1)
        if ENCODE_RESOLUTION:
            bgr = cv2.resize(bgr, ENCODE_RESOLUTION, interpolation=cv2.INTER_LINEAR)

        ok, jpg = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if ok:
            buffers.jpeg.put(jpg.tobytes())


def start():
    threading.Thread(target=capture, name="capture", daemon=True).start()
    threading.Thread(target=encode,  name="encode",  daemon=True).start()
