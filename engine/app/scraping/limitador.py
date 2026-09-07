"""Espaciado mínimo entre peticiones reales de scraping a la Plataforma
(sesión de límite de tasa, 2026-09-07): verificado con datos reales que una
tanda de cientos de descargas seguidas (`descargar_expediente`), sin
ninguna pausa entre sí, hace que la Plataforma responda con bloqueos o
timeouts -- antes confundidos con "expediente no publicado"
(`app.scraping.pcsp.ExpedienteNoPublicadoError`, ver su docstring para el
caso real, `6.25/28510.0016`).

El worker es un único proceso (CONTEXTO.md sección 10, "Worker"): un turno
en memoria de proceso es suficiente, no hace falta coordinación entre
procesos ni una tabla nueva."""
from __future__ import annotations

import time

from app.config import settings

_ultimo_intento_monotonic: float = 0.0


def esperar_turno() -> None:
    """Bloquea (con `time.sleep`, el worker es síncrono de todos modos)
    hasta que haya pasado `scraping_separacion_minima_segundos` desde la
    última llamada. Llamar justo antes de cada intento real de scraping
    (`scrape_expediente`), nunca antes de trabajo puramente de base de
    datos."""
    global _ultimo_intento_monotonic
    ahora = time.monotonic()
    espera = settings.scraping_separacion_minima_segundos - (ahora - _ultimo_intento_monotonic)
    if espera > 0:
        time.sleep(espera)
    _ultimo_intento_monotonic = time.monotonic()
