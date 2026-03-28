import logging
import camera
import temperature
import esp_receiver
import server
from config import PORT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

camera.start()
temperature.start()
esp_receiver.start()

print(f"→ http://<IP_PI>:{PORT}/")
try:
    server.start()   # bloquant
except KeyboardInterrupt:
    pass
