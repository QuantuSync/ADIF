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


# Cabecera real de un fichero ZIP (con o sin entradas) — verificarla es la
# única forma barata de distinguir un ZIP real de una página de bloqueo/error
# servida con código 200 (sesión de límite de tasa, 2026-09-07: 11 periodos
# seguidos fallaron con "File is not a zip file" tras 10 correctos, patrón
# de bloqueo bajo carga, no de 11 meses realmente sin publicar).
_CABECERAS_ZIP = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")


class DescargaSindicacionInvalidaError(RuntimeError):
    """La petición respondió (código 2xx) pero el contenido no es un ZIP
    real -- casi siempre una página de bloqueo/límite de tasa servida con
    código 200, no un mes genuinamente sin publicar (que la Plataforma
    real responde con 404, no con un cuerpo que parece HTML). Se distingue
    de un `httpx.HTTPStatusError` (4xx/5xx real) y de un mes realmente
    ausente -- ver docstring del módulo y `descargar_zip_periodo`."""


def descargar_zip_periodo(periodo: str, destino: Path, timeout_segundos: float = 1200.0) -> Path:
    """Descarga el ZIP del periodo (formato `AAAAMM`) a `destino`, en
    streaming (`httpx.stream`, chunks a disco, nunca `response.content`
    entero). El fichero puede superar los 100 MB — un timeout largo es
    deliberado, no un descuido (verificado en esta sesión: ~460 s para un
    mes completo con la conexión de esta sesión).

    Verifica la cabecera real del fichero antes de darlo por bueno (sesión
    de límite de tasa, 2026-09-07): un código 404 significa que el periodo
    de verdad no está publicado (se deja subir como `httpx.HTTPStatusError`,
    sin cambios); un código 2xx cuyo contenido no empieza como un ZIP real
    es casi siempre una página de bloqueo servida como si fuera la
    descarga -- se borra el fichero a medias y se lanza
    `DescargaSindicacionInvalidaError` con un fragmento del contenido para
    diagnóstico, nunca se deja que un `zipfile.BadZipFile` más adelante lo
    confunda con "este mes no existe"."""
    url = url_zip_periodo(periodo)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream(
        "GET", url, headers={"User-Agent": _USER_AGENT}, timeout=timeout_segundos, follow_redirects=True
    ) as respuesta:
        respuesta.raise_for_status()
        with open(destino, "wb") as f:
            for chunk in respuesta.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)
    with open(destino, "rb") as f:
        cabecera = f.read(4)
    if not cabecera.startswith(_CABECERAS_ZIP):
        with open(destino, "rb") as f:
            fragmento = f.read(300)
        destino.unlink(missing_ok=True)
        try:
            texto = fragmento.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            texto = repr(fragmento)
        raise DescargaSindicacionInvalidaError(
            f"la respuesta de {url} no es un ZIP real (probable bloqueo/límite de tasa servido con "
            f"código 200): {texto[:200]!r}"
        )
    logger.info("descargado %s (%s bytes) -> %s", url, destino.stat().st_size, destino)
    return destino
