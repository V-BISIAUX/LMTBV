"""
buffers.py — Tampons thread-safe partagés entre producteurs et consommateurs.

Chaque buffer utilise un threading.Condition pour permettre aux consommateurs
de se bloquer (wait) jusqu'à ce qu'une nouvelle donnée soit disponible, sans
boucle active (pas de busy-wait / sleep).

Singletons globaux créés en bas de fichier et importés par les autres modules.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# RawFrameBuffer  — tableau numpy (frame non compressée)
# ---------------------------------------------------------------------------

class RawFrameBuffer:
    """
    Stocke la dernière frame brute (numpy array RGB/BGR) issue du driver caméra.
    Le thread d'encodage attend ici une nouvelle frame avant de compresser.
    """

    def __init__(self):
        self._condition = threading.Condition()
        self._frame = None
        self._seq: int = 0          # numéro de séquence → évite de ré-encoder la même frame

    # -- Producteur ----------------------------------------------------------

    def publish(self, frame) -> None:
        """Publie une nouvelle frame brute et réveille les consommateurs."""
        with self._condition:
            self._frame = frame
            self._seq  += 1
            self._condition.notify_all()

    # -- Consommateur --------------------------------------------------------

    def wait_for_new(self, last_seq: int, timeout: float = 2.0):
        """
        Bloque jusqu'à ce qu'une frame avec seq > last_seq soit disponible.
        Retourne (frame, new_seq). Retourne (None, last_seq) en cas de timeout.
        """
        with self._condition:
            self._condition.wait_for(lambda: self._seq > last_seq, timeout=timeout)
            return self._frame, self._seq


    def get_latest(self):
        """
        Retourne immédiatement la frame la plus récente sans bloquer.
        Utilisé par EncodeThread pour sauter les frames en retard (frame-drop).
        """
        with self._condition:
            return self._frame, self._seq

# ---------------------------------------------------------------------------
# JpegBuffer  — bytes JPEG prêts à être envoyés au client
# ---------------------------------------------------------------------------

class JpegBuffer:
    """
    Stocke la dernière frame encodée en JPEG.
    Notifie tous les handlers HTTP connectés dès qu'une nouvelle frame arrive.
    """

    def __init__(self):
        self._condition = threading.Condition()
        self._jpeg: Optional[bytes] = None
        self._seq:  int = 0

    # -- Producteur ----------------------------------------------------------

    def publish(self, jpeg_bytes: bytes) -> None:
        with self._condition:
            self._jpeg = jpeg_bytes
            self._seq += 1
            self._condition.notify_all()

    # -- Consommateur --------------------------------------------------------

    def wait_for_new(self, last_seq: int, timeout: float = 2.0):
        """
        Bloque jusqu'à la prochaine frame JPEG.
        Retourne (jpeg_bytes, new_seq) ou (None, last_seq) si timeout.
        """
        with self._condition:
            self._condition.wait_for(lambda: self._seq > last_seq, timeout=timeout)
            return self._jpeg, self._seq


# ---------------------------------------------------------------------------
# TemperatureBuffer  — dernière mesure MLX90614
# ---------------------------------------------------------------------------

@dataclass
class TemperatureSample:
    ambient_c: float
    object_c:  float
    timestamp: float = field(default_factory=time.time)


class TemperatureBuffer:
    """
    Stocke la dernière mesure de température et notifie les abonnés SSE
    dès qu'une nouvelle valeur est disponible.
    """

    def __init__(self):
        self._condition = threading.Condition()
        self._sample: Optional[TemperatureSample] = None
        self._seq: int = 0

    # -- Producteur ----------------------------------------------------------

    def publish(self, ambient_c: float, object_c: float) -> None:
        with self._condition:
            self._sample = TemperatureSample(ambient_c=ambient_c, object_c=object_c)
            self._seq   += 1
            self._condition.notify_all()

    # -- Consommateur (snapshot, sans attente) --------------------------------

    def get(self) -> Optional[TemperatureSample]:
        with self._condition:
            return self._sample

    # -- Consommateur (SSE : attend la prochaine mesure) ----------------------

    def wait_for_new(self, last_seq: int, timeout: float = 5.0):
        """
        Bloque jusqu'à la prochaine mesure.
        Retourne (TemperatureSample, new_seq) ou (None, last_seq) si timeout.
        """
        with self._condition:
            self._condition.wait_for(lambda: self._seq > last_seq, timeout=timeout)
            return self._sample, self._seq


# ---------------------------------------------------------------------------
# Singletons partagés — importés directement par les autres modules
# ---------------------------------------------------------------------------

RAW_FRAME_BUF = RawFrameBuffer()
JPEG_BUF      = JpegBuffer()
TEMP_BUF      = TemperatureBuffer()
