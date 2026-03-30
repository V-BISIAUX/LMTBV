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

RETRY_DELAY = 5   # secondes d'attente avant de retenter en cas d'erreur série


def _is_complete_json(s):
    # Vérifie que la chaîne contient un objet JSON complet
    # Ignore les accolades à l'intérieur des chaînes de caractères
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
    # Traite une trame JSON reçue : la décode, la stocke et vérifie s'il y a un incendie
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning("JSON invalide : %s | %r", e, raw[:80])
        return

    data["pi_timestamp"] = datetime.now(timezone.utc).isoformat()
    gps = data.get("gps", {})
    log.info("T=%s°C  H=%s%%  Air=%s  GPS=%s",
             data.get("temperature", "?"),
             data.get("humidity", "?"),
             data.get("air_label", "?"),
             "FIX" if gps.get("fix") else "no fix")

    buffers.esp.put(data)   # met à jour le buffer pour la route /esp/data

    # Sauvegarde la trame dans le fichier de log
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(data) + "\n")

    fire_detector.check(data)   # analyse les données pour détecter un incendie


def _read_loop():
    # Ouvre le port série et lit les trames ligne par ligne
    # Les trames JSON peuvent arriver sur plusieurs lignes, on les accumule dans buf
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
                continue   # ignore les lignes qui ne commencent pas un JSON

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
    # Relance _read_loop automatiquement en cas d'erreur ou de déconnexion
    while True:
        try:
            _read_loop()
        except Exception:
            log.exception("Erreur inattendue dans esp_receiver.")
        time.sleep(RETRY_DELAY)


def start():
    # Lance la boucle de réception dans un thread daemon
    threading.Thread(target=_receiver_loop, name="esp_receiver", daemon=True).start()