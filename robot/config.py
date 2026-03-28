# Réseau
HOST = "0.0.0.0"
PORT = 8000

# Caméra
RESOLUTION        = (640, 480)
FPS_LIMIT         = 10
JPEG_QUALITY      = 60
FLIP_IMAGE        = True
ENCODE_RESOLUTION = (320, 240)

# MLX90614 (I²C)
I2C_BUS         = 1
MLX_ADDR        = 0x5A
REG_AMBIENT     = 0x06
REG_OBJECT      = 0x07
TEMP_INTERVAL_S = 0.5

# ESP8266 (USB série)
SERIAL_PORT     = "/dev/ttyUSB0"
SERIAL_BAUDRATE = 115200
SERIAL_TIMEOUT  = 2
LOG_FILE        = "esp_data.log"

# Détection feu — seuils par défaut (écrasés par thresholds.json si présent)
FIRE_TEMP_C      = 25.0   # température objet MLX (°C)
FIRE_HUMIDITY    = 15.0   # humidité DHT (%)
FIRE_AIR_QUALITY = 75     # qualité air (score 0-100, en dessous = alerte)

THRESHOLDS_FILE  = "thresholds.json"
FIRE_LOG_FILE    = "fire_events.log"

# Rayon anti-doublon carte (mètres) — un feu déjà marqué dans ce rayon est ignoré
FIRE_DEDUP_RADIUS_M = 25
