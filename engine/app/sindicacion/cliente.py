"""Descarga del ZIP mensual de sindicación (CONTEXTO.md sección 24, bloque 2,
punto 1: "ficheros grandes: procesamiento incremental, no cargarlo entero en
memoria"). Verificado real contra `contrataciondelestado.es`: el ZIP de un
mes completo pesa entre 90 y 130 MB comprimidos — se escribe a disco en
streaming, nunca se acumula en un `bytes` ni en memoria.

Hallazgo de esta sesión, mismo patrón que CONTEXTO.md sección 17 ("el WAF
distingue por tipo de URL"): una petición `HEAD` sin cabeceras (`curl -I`)
contra esta URL no responde (conexión cerrada); una petición `GET` con una
cabecera `User-Agent` de navegador real sí responde `200` con el ZIP
completo, con `curl` plano, sin cookies ni sesión de navegador — no hizo
falta Playwright para este endpoint (a diferencia de las URLs de descarga de
documentos de la sección 17.1, que si lo necesitan). No se aisló si lo que
importa es el método (GET vs HEAD) o la cabecera User-Agent por separado;
por seguridad, este cliente siempre manda una User-Agent de navegador real.
"""
from __future__ import annotations

import logging
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger("sindicacion.cliente")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def url_zip_periodo(periodo: str) -> str:
    return f"{settings.sindicacion_base_url}/licitacionesPerfilesContratanteCompleto3_{periodo}.zip"


def descargar_zip_periodo(periodo: str, destino: Path, timeout_segundos: float = 1200.0) -> Path:
    """Descarga el ZIP del periodo (formato `AAAAMM`) a `destino`, en
    streaming (`httpx.stream`, chunks a disco, nunca `response.content`
    entero). El fichero puede superar los 100 MB — un timeout largo es
    deliberado, no un descuido (verificado en esta sesión: ~460 s para un
    mes completo con la conexión de esta sesión)."""
    url = url_zip_periodo(periodo)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream(
        "GET", url, headers={"User-Agent": _USER_AGENT}, timeout=timeout_segundos, follow_redirects=True
    ) as respuesta:
        respuesta.raise_for_status()
        with open(destino, "wb") as f:
            for chunk in respuesta.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)
    logger.info("descargado %s (%s bytes) -> %s", url, destino.stat().st_size, destino)
    return destino
