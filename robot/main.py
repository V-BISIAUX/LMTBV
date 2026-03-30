import logging
import camera
import temperature
import esp_receiver
import server
from config import PORT

# Configure les logs : affiche l'heure, le niveau et le nom du module
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

# Démarrage des threads en arrière-plan
camera.start() # capture et encodage vidéo
temperature.start()  # lecture du capteur MLX90614
esp_receiver.start() # réception des données de l'ESP8266

print(f"→ http://<IP_PI>:{PORT}/")
try:
    server.start() # démarre le serveur HTTP (bloquant jusqu'à Ctrl+C)
except KeyboardInterrupt:
    pass