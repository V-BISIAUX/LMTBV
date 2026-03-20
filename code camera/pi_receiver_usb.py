    #!/usr/bin/env python3
"""
pi_receiver_usb.py — Thread de réception USB depuis l'ESP8266.

Lit les trames JSON envoyées par l'ESP8266 via câble USB et les
logue dans un fichier. Tourne en daemon thread, lancé par main.py.

Prérequis :
    pip install pyserial
"""

import serial
import json
import logging
import threading
from datetime import datetime, timezone

# ─── Configuration ─────────────────────────────────────────────────────────
SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE    = 115200
TIMEOUT     = 2                 # secondes avant de réessayer si rien reçu
LOG_FILE    = "/home/remigrassion/esp_data.log"

log = logging.getLogger(__name__)

# ─── Buffer partagé ────────────────────────────────────────────────────────
class EspBuffer:
    """Stocke la dernière trame ESP reçue (thread-safe, lecture sans attente)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._data = None

    def publish(self, data: dict):
        with self._lock:
            self._data = data

    def get(self):
        with self._lock:
            return self._data


ESP_BUF = EspBuffer()

# ─── Traitement d'une trame ────────────────────────────────────────────────
def _traiter_trame(ligne: str):
    try:
        data = json.loads(ligne)
    except json.JSONDecodeError as e:
        log.warning("Trame JSON invalide : %s | brut : %r", e, ligne)
        return

    data["pi_timestamp"] = datetime.now(timezone.utc).isoformat()

    gps = data.get("gps", {})
    log.info(
        "T=%s°C  H=%s%%  Air=%s  GPS=%s  Lat=%s  Lng=%s",
        data.get("temperature", "?"),
        data.get("humidity",    "?"),
        data.get("air_label",   "?"),
        "FIX" if gps.get("fix") else "PAS DE FIX",
        gps.get("latitude",  "—"),
        gps.get("longitude", "—"),
    )

    ESP_BUF.publish(data)

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(data) + "\n")

    # ── Ajoutez ici votre logique (MQTT, base de données, API...) ──


# ─── Thread ────────────────────────────────────────────────────────────────
class EspReceiverThread(threading.Thread):
    """
    Lit en continu les trames JSON de l'ESP8266 sur le port série USB.
    En cas d'erreur d'ouverture ou de coupure, attend 5 secondes et réessaie
    automatiquement — le robot peut être débranché/rebranché sans crasher.
    """

    RETRY_DELAY = 5   # secondes entre deux tentatives de reconnexion

    def __init__(self):
        super().__init__(name="EspReceiverThread", daemon=True)

    def run(self) -> None:
        log.info("EspReceiverThread démarré (%s @ %d baud).", SERIAL_PORT, BAUDRATE)

        while True:
            try:
                self._read_loop()
            except Exception:
                log.exception(
                    "Erreur inattendue dans EspReceiverThread. "
                    "Nouvelle tentative dans %ds.", self.RETRY_DELAY
                )
            threading.Event().wait(self.RETRY_DELAY)

    def _read_loop(self) -> None:
        """Ouvre le port série et lit jusqu'à déconnexion ou erreur."""
        try:
            ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=TIMEOUT)
        except serial.SerialException as e:
            log.warning("Impossible d'ouvrir %s : %s. Nouvelle tentative dans %ds.",
                        SERIAL_PORT, e, self.RETRY_DELAY)
            return

        log.info("Port série ouvert, en attente de données ESP8266...")
        try:
            while True:
                raw = ser.readline()
                if not raw:
                    continue    # timeout TIMEOUT sans données — reboucle
                try:
                    ligne = raw.decode("utf-8").strip()
                except UnicodeDecodeError:
                    log.warning("Erreur de décodage, trame ignorée.")
                    continue
                if ligne:
                    _traiter_trame(ligne)
        except serial.SerialException as e:
            log.warning("Connexion série perdue : %s.", e)
        finally:
            ser.close()
            log.info("Port série fermé.")