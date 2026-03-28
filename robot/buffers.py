import threading
import time
from dataclasses import dataclass, field


class Buffer:
    """
    Buffer thread-safe générique.
    Les consommateurs peuvent soit lire la dernière valeur (get),
    soit attendre la prochaine (wait_next).
    """

    def __init__(self):
        self._cond  = threading.Condition()
        self._value = None
        self._seq   = 0

    def put(self, value):
        with self._cond:
            self._value = value
            self._seq  += 1
            self._cond.notify_all()

    def get(self):
        with self._cond:
            return self._value

    def get_with_seq(self):
        """Retourne (valeur, seq) atomiquement, sans bloquer."""
        with self._cond:
            return self._value, self._seq

    def wait_next(self, last_seq, timeout=2.0):
        """Bloque jusqu'à ce qu'une valeur plus récente que last_seq soit dispo.
        Retourne (valeur, nouveau_seq), ou (None, last_seq) si timeout."""
        with self._cond:
            self._cond.wait_for(lambda: self._seq > last_seq, timeout=timeout)
            return self._value, self._seq


@dataclass
class TempSample:
    ambient_c: float
    object_c:  float
    timestamp: float = field(default_factory=time.time)


raw_frame = Buffer()   # numpy array RGB — CaptureThread → EncodeThread
jpeg      = Buffer()   # bytes JPEG      — EncodeThread  → clients MJPEG
temp      = Buffer()   # TempSample      — TemperatureThread → clients SSE
esp       = Buffer()   # dict JSON       — EspReceiverThread → route /esp/data
