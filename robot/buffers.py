import threading
import time
from dataclasses import dataclass, field


class Buffer:
    """
    Buffer thread-safe générique.
    Permet à plusieurs threads de partager une valeur en toute sécurité.
    - get() : lit la dernière valeur sans bloquer
    - wait_next() : attend qu'une nouvelle valeur soit disponible
    """

    def __init__(self):
        self._cond = threading.Condition()   # verrou + mécanisme d'attente
        self._value = None          # dernière valeur stockée
        self._seq = 0           # compteur pour détecter les nouvelles valeurs

    def put(self, value):
        # Stocke une nouvelle valeur et réveille les threads en attente
        with self._cond:
            self._value = value
            self._seq  += 1
            self._cond.notify_all()

    def get(self):
        # Retourne la dernière valeur sans bloquer
        with self._cond:
            return self._value

    def get_with_seq(self):
        # Retourne (valeur, numéro de séquence) de façon atomique
        with self._cond:
            return self._value, self._seq

    def wait_next(self, last_seq, timeout=2.0):
        # Bloque jusqu'à ce qu'une valeur plus récente que last_seq soit disponible.
        with self._cond:
            self._cond.wait_for(lambda: self._seq > last_seq, timeout=timeout)
            return self._value, self._seq


@dataclass
class TempSample:
    # Représente une mesure du capteur MLX90614
    ambient_c: float      # température ambiante (°C)
    object_c: float          # température de l'objet visé (°C)
    timestamp: float = field(default_factory=time.time) # horodatage Unix de la mesure


# Buffers partagés entre les différents threads
raw_frame = Buffer()   # frame brute (numpy RGB)  : CaptureThread → EncodeThread
jpeg = Buffer()   # frame encodée (bytes)    : EncodeThread  → clients MJPEG
temp = Buffer()   # mesure de température    : TemperatureThread → clients SSE
esp = Buffer()   # données JSON de l'ESP    : EspReceiverThread → route /esp/data