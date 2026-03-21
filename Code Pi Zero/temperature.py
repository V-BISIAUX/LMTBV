"""
temperature.py — Thread de lecture du capteur MLX90614 (infrarouge sans contact).

La lecture I²C est effectuée dans une boucle indépendante à fréquence configurable.
En cas d'erreur transitoire (bus occupé, timeout), le thread se contente de logger
et réessaie au prochain cycle — il ne crash pas.
"""

from __future__ import annotations

import threading
import time
import logging

import smbus2

from buffers import TemperatureBuffer
from config import I2C_BUS, MLX_ADDR, REG_AMBIENT, REG_OBJECT, TEMP_INTERVAL_S

log = logging.getLogger(__name__)


def _read_celsius(bus: smbus2.SMBus, register: int) -> float:
    """Lit un registre 16 bits du MLX90614 et convertit en degrés Celsius."""
    raw = bus.read_word_data(MLX_ADDR, register) & 0xFFFF
    return raw * 0.02 - 273.15


class TemperatureThread(threading.Thread):
    """
    Interroge le MLX90614 toutes les TEMP_INTERVAL_S secondes et publie
    les mesures dans un TemperatureBuffer.

    Les clients SSE sont notifiés immédiatement à chaque nouvelle mesure.
    """

    def __init__(self, temp_buf: TemperatureBuffer):
        super().__init__(name="TemperatureThread", daemon=True)
        self._temp_buf = temp_buf

    def run(self) -> None:
        bus = smbus2.SMBus(I2C_BUS)
        log.info(
            "Lecture MLX90614 démarrée (bus=%d, addr=0x%02X, intervalle=%.1fs).",
            I2C_BUS, MLX_ADDR, TEMP_INTERVAL_S,
        )

        while True:
            try:
                ambient = _read_celsius(bus, REG_AMBIENT)
                obj     = _read_celsius(bus, REG_OBJECT)
                self._temp_buf.publish(ambient, obj)
                log.debug("Temp — amb: %.1f°C  obj: %.1f°C", ambient, obj)
            except OSError as e:
                log.warning("Erreur I²C MLX90614 : %s", e)

            time.sleep(TEMP_INTERVAL_S)
