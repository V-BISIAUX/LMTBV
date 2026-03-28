import json
import logging
import threading
import time
from datetime import datetime, timezone

import serial

import buffers
import fire_detector
from config import SERIAL_PORT, SERIAL_BAUDRATE, SERIAL_TIMEOUT, LOG_FILE

log = logging.getLogger(__name__)

RETRY_DELAY = 5


def _is_complete_json(s):
    """Vérifie que la chaîne contient un objet JSON avec accolades équilibrées."""
    depth, in_str, escape = 0, False, False
    for c in s:
        if escape:
            escape = False; continue
        if c == '\\' and in_str:
            escape = True; continue
        if c == '"':
            in_str = not in_str; continue
        if in_str:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return True
    return False


def _handle_frame(raw):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning("JSON invalide : %s | %r", e, raw[:80])
        return

    data["pi_timestamp"] = datetime.now(timezone.utc).isoformat()
    gps = data.get("gps", {})
    log.info("T=%s°C  H=%s%%  Air=%s  GPS=%s",
             data.get("temperature", "?"),
             data.get("humidity",    "?"),
             data.get("air_label",   "?"),
             "FIX" if gps.get("fix") else "no fix")

    buffers.esp.put(data)

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(data) + "\n")

    fire_detector.check(data)


def _read_loop():
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUDRATE, timeout=SERIAL_TIMEOUT)
    except serial.SerialException as e:
        log.warning("Impossible d'ouvrir %s : %s", SERIAL_PORT, e)
        return

    log.info("Port série ouvert (%s)", SERIAL_PORT)
    buf = ""
    try:
        while True:
            raw = ser.readline()
            if not raw:
                continue
            try:
                chunk = raw.decode("utf-8").strip()
            except UnicodeDecodeError:
                buf = ""; continue

            if not chunk:
                continue
            if not buf and not chunk.startswith("{"):
                continue

            buf += chunk

            if _is_complete_json(buf):
                _handle_frame(buf)
                buf = ""
            elif len(buf) > 4096:
                log.warning("Buffer trop grand, reset.")
                buf = ""

    except serial.SerialException as e:
        log.warning("Connexion perdue : %s", e)
    finally:
        ser.close()


def _receiver_loop():
    while True:
        try:
            _read_loop()
        except Exception:
            log.exception("Erreur inattendue dans esp_receiver.")
        time.sleep(RETRY_DELAY)


def start():
    threading.Thread(target=_receiver_loop, name="esp_receiver", daemon=True).start()
