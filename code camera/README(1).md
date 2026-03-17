# PiCam Thermal Stream

Flux vidéo MJPEG + données de température MLX90614 en temps réel,
servis par un serveur HTTP Python sur Raspberry Pi.

## Architecture

```
┌─────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  CaptureThread  │──────▶│  RawFrameBuffer  │──────▶│  EncodeThread    │
│  (Picamera2)    │       │  (numpy array)   │       │  (JPEG / OpenCV) │
└─────────────────┘       └──────────────────┘       └────────┬─────────┘
                                                               │
┌─────────────────┐       ┌──────────────────┐                ▼
│ TemperatureThread│──────▶│  TemperatureBuffer│       ┌──────────────────┐
│  (MLX90614 I²C) │       │  (dataclass)      │       │    JpegBuffer    │
└─────────────────┘       └────────┬──────────┘       └────────┬─────────┘
                                   │ SSE (push)                 │ MJPEG
                                   ▼                            ▼
                           GET /temperature/stream     GET /stream.mjpg
                           (text/event-stream)         (multipart/x-mixed-replace)
```

**Deux flux entièrement indépendants :**
- `/stream.mjpg` → frames JPEG, aucune donnée de température embarquée
- `/temperature/stream` → Server-Sent Events JSON, poussés dès qu'une mesure arrive
- L'overlay est rendu côté client en JavaScript → CPU Pi préservé

## Fichiers

| Fichier | Rôle |
|---|---|
| `main.py` | Point d'entrée, lance les threads et le serveur |
| `config.py` | Tous les paramètres (résolution, FPS, I²C…) |
| `buffers.py` | `RawFrameBuffer`, `JpegBuffer`, `TemperatureBuffer` (thread-safe) |
| `camera.py` | `CaptureThread` + `EncodeThread` |
| `temperature.py` | `TemperatureThread` (MLX90614) |
| `server.py` | Serveur HTTP + handlers MJPEG / SSE |
| `frontend.py` | Page HTML/CSS/JS embarquée |

## Installation

```bash
pip install picamera2 opencv-python-headless smbus2
```

## Lancement

```bash
python main.py
```

Puis ouvrir `http://<IP_DU_PI>:8000/` dans un navigateur.

## Paramètres

Modifier `config.py` :

```python
RESOLUTION      = (640, 480)   # résolution caméra
FPS_LIMIT       = 15           # images/seconde
JPEG_QUALITY    = 80           # qualité JPEG [1-100]
FLIP_IMAGE      = True         # rotation 180°
TEMP_INTERVAL_S = 0.5          # fréquence de lecture MLX90614
PORT            = 8000
```
