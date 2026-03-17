"""
camera.py — Threads de capture et d'encodage vidéo.

Architecture à deux étages :
  CaptureThread  →  RawFrameBuffer  →  EncodeThread  →  JpegBuffer

Avantages :
  • L'encodage JPEG (CPU-bound) ne bloque jamais la capture.
  • Chaque étage tourne à son propre rythme.
  • Un seul thread accède à Picamera2 (pas de race condition).
"""

from __future__ import annotations

import threading
import logging

import cv2
from picamera2 import Picamera2

from buffers import RawFrameBuffer, JpegBuffer
from config import RESOLUTION, FPS_LIMIT, JPEG_QUALITY, FLIP_IMAGE

log = logging.getLogger(__name__)


class CaptureThread(threading.Thread):
    """
    Lit les frames brutes (numpy RGB888) depuis le driver Picamera2 et les
    publie dans un RawFrameBuffer.

    La méthode capture_array() est bloquante : elle attend naturellement la
    prochaine frame du driver — aucun sleep nécessaire.
    """

    def __init__(self, raw_buf: RawFrameBuffer):
        super().__init__(name="CaptureThread", daemon=True)
        self._raw_buf = raw_buf

    def run(self) -> None:
        picam2 = Picamera2()
        config = picam2.create_video_configuration(
            main={"size": RESOLUTION, "format": "RGB888"},
            controls={"FrameRate": FPS_LIMIT},
        )
        picam2.configure(config)
        picam2.start()
        log.info("Capture démarrée : %s @ %d fps", RESOLUTION, FPS_LIMIT)

        try:
            while True:
                frame = picam2.capture_array()   # bloquant → pas de busy-wait
                self._raw_buf.publish(frame)
        except Exception:
            log.exception("Erreur fatale dans CaptureThread")
        finally:
            picam2.stop()
            log.info("Capture arrêtée.")


class EncodeThread(threading.Thread):
    """
    Attend chaque nouvelle frame brute, applique les transformations
    (flip, conversion couleur) puis encode en JPEG.

    Le résultat est publié dans un JpegBuffer, notifiant les clients HTTP.
    """

    def __init__(self, raw_buf: RawFrameBuffer, jpeg_buf: JpegBuffer):
        super().__init__(name="EncodeThread", daemon=True)
        self._raw_buf  = raw_buf
        self._jpeg_buf = jpeg_buf

    def run(self) -> None:
        log.info("Encodeur JPEG démarré (qualité=%d).", JPEG_QUALITY)
        last_seq = 0

        while True:
            frame, last_seq = self._raw_buf.wait_for_new(last_seq)
            if frame is None:
                continue    # timeout sans nouvelle frame — boucle

            jpeg = self._encode(frame)
            if jpeg is not None:
                self._jpeg_buf.publish(jpeg)

    # -----------------------------------------------------------------------

    @staticmethod
    def _encode(frame_rgb) -> bytes | None:
        """Convertit RGB→BGR, applique le flip, encode en JPEG."""
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

        if FLIP_IMAGE:
            frame_bgr = cv2.flip(frame_bgr, -1)    # rotation 180°

        ok, jpg = cv2.imencode(
            ".jpg", frame_bgr,
            [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY],
        )
        return jpg.tobytes() if ok else None
