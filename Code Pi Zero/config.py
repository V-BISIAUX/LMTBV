"""
config.py — Paramètres globaux de l'application.
Modifier ici uniquement ; ne jamais coder en dur dans les autres modules.
"""

# ── Réseau ─────────────────────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8000

# ── Caméra ──────────────────────────────────────────────────────────────────
RESOLUTION   = (640, 480)   # (largeur, hauteur) en pixels
FPS_LIMIT    = 10           # images/seconde maximales côté driver
JPEG_QUALITY = 60           # qualité JPEG [1-100]
FLIP_IMAGE   = True         # True → rotation 180° (montage caméra tête en bas)
ENCODE_RESOLUTION = (320, 240)

# ── Capteur MLX90614 ────────────────────────────────────────────────────────
I2C_BUS    = 1
MLX_ADDR   = 0x5A
REG_AMBIENT = 0x06
REG_OBJECT  = 0x07
TEMP_INTERVAL_S = 0.5       # délai entre deux lectures (secondes)
