import threading
import time
import logging
import smbus2

import buffers
from buffers import TempSample
from config import I2C_BUS, MLX_ADDR, REG_AMBIENT, REG_OBJECT, TEMP_INTERVAL_S

log = logging.getLogger(__name__)


def _read_celsius(bus, register):
    raw = bus.read_word_data(MLX_ADDR, register) & 0xFFFF
    return raw * 0.02 - 273.15


def read_loop():
    bus = smbus2.SMBus(I2C_BUS)
    log.info("MLX90614 démarré (bus %d, 0x%02X)", I2C_BUS, MLX_ADDR)
    while True:
        try:
            buffers.temp.put(TempSample(
                ambient_c=_read_celsius(bus, REG_AMBIENT),
                object_c =_read_celsius(bus, REG_OBJECT),
            ))
        except OSError as e:
            log.warning("Erreur I²C : %s", e)
        time.sleep(TEMP_INTERVAL_S)


def start():
    threading.Thread(target=read_loop, name="temperature", daemon=True).start()
