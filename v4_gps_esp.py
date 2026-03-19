#!/usr/bin/env python3
"""
Raspberry Pi Zero 2W — Proxy capteurs ESP8266
─────────────────────────────────────────────
- Interroge http://192.168.3.16/data toutes les secondes
- Affiche les données dans la console
- Re-expose le JSON sur http://<ip_raspberry>/ et http://<ip_raspberry>/data
"""

import json
import time
import threading
import requests
from flask import Flask, jsonify, make_response   # ← ajouter make_response
from datetime import datetime

# ─── Configuration ────────────────────────────────────────────────────────────
ESP_URL          = "http://192.168.3.16/data"
POLL_INTERVAL    = 1      # secondes entre chaque lecture
FLASK_PORT       = 80     # port du serveur web (80 = accès sans préciser le port)

# ─── État partagé ─────────────────────────────────────────────────────────────
latest_data      = {}
data_lock        = threading.Lock()

# ─── Flask ────────────────────────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/")
@app.route("/data")
def serve_data():
    with data_lock:
        if not latest_data:
            data = {"error": "Aucune donnée disponible"}
            status = 503
        else:
            data = latest_data
            status = 200
    response = make_response(jsonify(data), status)
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return response

# Applique CORS sur TOUTES les réponses Flask automatiquement
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return response

# ─── Affichage console ────────────────────────────────────────────────────────
def afficher(data: dict):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'─'*50}")
    print(f"  {now} — Données ESP8266")
    print(f"{'─'*50}")

    # Environnement
    temp = data.get("temperature")
    humi = data.get("humidity")
    air_q = data.get("air_quality")
    air_l = data.get("air_label", "—")

    print(f"  🌡  Température  : {temp if temp is not None else '—'} °C")
    print(f"  💧 Humidité     : {humi if humi is not None else '—'} %")
    print(f"  🌫  Qualité air  : {air_q if air_q is not None else '—'} %  ({air_l})")

    # GPS
    gps = data.get("gps", {})
    fix = gps.get("fix", False)
    print(f"\n  📡 GPS")
    print(f"     Fix         : {'✅ Oui' if fix else '❌ Non (recherche...)'}")
    print(f"     Latitude    : {gps.get('latitude',  'null')}")
    print(f"     Longitude   : {gps.get('longitude', 'null')}")
    print(f"     Altitude    : {gps.get('altitude',  'null')} m")
    print(f"     Vitesse     : {gps.get('speed_kmh', 'null')} km/h")
    print(f"     Cap         : {gps.get('course_deg','null')} °")
    print(f"     Satellites  : {gps.get('satellites','null')}")
    print(f"     HDOP        : {gps.get('hdop',      'null')}")
    print(f"     Date UTC    : {gps.get('date',      'null')}")
    print(f"     Heure UTC   : {gps.get('time',      'null')}")

# ─── Boucle de polling ────────────────────────────────────────────────────────
def polling_loop():
    global latest_data
    print(f"[Polling] Démarrage — interrogation de {ESP_URL} toutes les {POLL_INTERVAL}s")

    while True:
        try:
            response = requests.get(ESP_URL, timeout=5)
            response.raise_for_status()
            data = response.json()

            with data_lock:
                latest_data = data

            afficher(data)

        except requests.exceptions.ConnectionError:
            print(f"[Polling] ❌ Connexion impossible à {ESP_URL}")
        except requests.exceptions.Timeout:
            print(f"[Polling] ⏱  Timeout — ESP8266 ne répond pas")
        except requests.exceptions.HTTPError as e:
            print(f"[Polling] ⚠️  Erreur HTTP : {e}")
        except json.JSONDecodeError:
            print(f"[Polling] ⚠️  Réponse invalide (pas du JSON)")
        except Exception as e:
            print(f"[Polling] ⚠️  Erreur inattendue : {e}")

        time.sleep(POLL_INTERVAL)

# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Lancement du polling dans un thread séparé
    t = threading.Thread(target=polling_loop, daemon=True)
    t.start()

    # Lancement du serveur Flask
    print(f"[Flask] Serveur démarré sur le port {FLASK_PORT}")
    print(f"[Flask] Accès : http://<ip_raspberry>/ ou http://<ip_raspberry>/data")
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False)