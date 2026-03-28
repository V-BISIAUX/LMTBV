import json
import logging
import math
import threading
from datetime import datetime, timezone
from pathlib import Path

from config import (
    FIRE_TEMP_C, FIRE_HUMIDITY, FIRE_AIR_QUALITY,
    THRESHOLDS_FILE, FIRE_LOG_FILE, FIRE_DEDUP_RADIUS_M,
)

log = logging.getLogger(__name__)

# Événements détectés depuis le démarrage (volatile — remis à zéro au reboot)
_fires: list[dict] = []
_lock  = threading.Lock()


# ── Seuils ────────────────────────────────────────────────────────────────────

def _load_thresholds() -> dict:
    """Lit thresholds.json si présent, sinon retourne les valeurs de config.py."""
    path = Path(THRESHOLDS_FILE)
    if path.exists():
        try:
            data = json.loads(path.read_text())
            return {
                "temp_object_c":  float(data.get("temp_object_c",  FIRE_TEMP_C)),
                "humidity_pct":   float(data.get("humidity_pct",   FIRE_HUMIDITY)),
                "air_quality":    int(  data.get("air_quality",    FIRE_AIR_QUALITY)),
            }
        except Exception as e:
            log.warning("thresholds.json invalide, valeurs par défaut utilisées : %s", e)
    return {
        "temp_object_c": FIRE_TEMP_C,
        "humidity_pct":  FIRE_HUMIDITY,
        "air_quality":   FIRE_AIR_QUALITY,
    }


def _is_fire(esp_data: dict) -> tuple[bool, list[str]]:
    """Retourne (True, [raisons]) si au moins un seuil est dépassé."""
    t   = _load_thresholds()
    why = []

    temp = esp_data.get("temperature")
    if temp is not None and temp > t["temp_object_c"]:
        why.append(f"température={temp:.1f}°C > {t['temp_object_c']}°C")

    humidity = esp_data.get("humidity")
    if humidity is not None and humidity < t["humidity_pct"]:
        why.append(f"humidité={humidity:.1f}% < {t['humidity_pct']}%")

    air_quality = esp_data.get("air_quality")
    if air_quality is not None and air_quality < t["air_quality"]:
        why.append(f"qualité_air={air_quality} < {t['air_quality']}")

    return bool(why), why


# ── Déduplication GPS ─────────────────────────────────────────────────────────

def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Distance en mètres entre deux coordonnées GPS."""
    R = 6_371_000
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p)
         * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def _already_on_map(lat, lon) -> bool:
    """True si un feu existe déjà dans un rayon de FIRE_DEDUP_RADIUS_M."""
    if lat is None or lon is None:
        # Sans coordonnées on ne peut pas dédupliquer — on ajoute toujours
        return False
    with _lock:
        for f in _fires:
            if f["lat"] is None or f["lon"] is None:
                continue
            if _haversine_m(lat, lon, f["lat"], f["lon"]) <= FIRE_DEDUP_RADIUS_M:
                return True
    return False


# ── Point d'entrée principal ──────────────────────────────────────────────────

def check(esp_data: dict):
    """À appeler à chaque trame ESP reçue."""
    detected, reasons = _is_fire(esp_data)
    if not detected:
        return

    gps = esp_data.get("gps", {})
    lat = gps.get("latitude")
    lon = gps.get("longitude")
    fix = bool(gps.get("fix")) and lat is not None

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lat":       lat,
        "lon":       lon,
        "gps_fix":   fix,
        "reasons":   reasons,
        "temp_esp_c":    esp_data.get("temperature"),
        "humidity":      esp_data.get("humidity"),
        "air_quality":   esp_data.get("air_quality"),
    }

    # Log persistant — toujours
    with open(FIRE_LOG_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")
    log.warning("FEU DÉTECTÉ — %s", ", ".join(reasons))

    # Carte — seulement si pas déjà un feu proche
    if not _already_on_map(lat, lon):
        with _lock:
            _fires.append(event)
        log.info("Feu ajouté à la carte (lat=%s, lon=%s)", lat, lon)
    else:
        log.debug("Feu ignoré pour la carte (doublon dans %dm)", FIRE_DEDUP_RADIUS_M)


def get_all() -> list[dict]:
    """Retourne une copie de la liste des feux en mémoire."""
    with _lock:
        return list(_fires)
