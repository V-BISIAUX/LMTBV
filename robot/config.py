# Réseau
HOST = "0.0.0.0"   # écoute sur toutes les interfaces réseau
PORT = 8000

# Caméra
RESOLUTION = (640, 480)   # résolution de capture
FPS_LIMIT = 10           # nombre d'images par seconde max
JPEG_QUALITY = 60           # qualité JPEG (0-100)
FLIP_IMAGE  = True         # retourne l'image
ENCODE_RESOLUTION = (320, 240)   # résolution d'encodage pour le flux vidéo

# MLX90614 (capteur de température infrarouge, connecté en I²C)
I2C_BUS = 1       # numéro du bus I²C sur le Raspberry Pi
MLX_ADDR = 0x5A    # adresse I²C du capteur
REG_AMBIENT = 0x06    # registre température ambiante
REG_OBJECT = 0x07    # registre température objet (infrarouge)
TEMP_INTERVAL_S = 0.5     # délai entre deux lectures (en secondes)

# ESP8266 (via USB/série)
SERIAL_PORT = "/dev/ttyUSB0"   # port série de l'ESP8266
SERIAL_BAUDRATE = 115200           # vitesse de communication
SERIAL_TIMEOUT  = 2               # timeout de lecture en secondes
LOG_FILE = "esp_data.log"  # fichier de log des trames ESP reçues

# Seuils de détection d'incendie (valeurs par défaut, remplaçables via thresholds.json)
FIRE_TEMP_C = 25.0   # température objet au-dessus de laquelle on alerte (°C)
FIRE_HUMIDITY = 15.0   # humidité en dessous de laquelle on alerte (%)
FIRE_AIR_QUALITY = 75    # qualité de l'air en dessous de laquelle on alerte (0-100)

THRESHOLDS_FILE = "thresholds.json"   # fichier de seuils personnalisés
FIRE_LOG_FILE = "fire_events.log"   # fichier de log des incendies détectés

# Distance minimale entre deux feux sur la carte (en mètres)
# Si un feu est détecté à moins de cette distance d'un feu existant, il est ignoré
FIRE_DEDUP_RADIUS_M = 25