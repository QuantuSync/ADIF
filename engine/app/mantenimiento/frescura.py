"""Bloque 1, ejecución incremental (CLAUDE.md sección 23).

Decide si un expediente necesita una nueva descarga o una nueva extracción
sin abrir ningún documento y sin tocar la cascada de extracción
(`app.extraccion.*`) ni el scraping (`app.scraping.*`) — ninguno de los dos
se modifica en esta sesión. Quien SÍ escribe las columnas de frescura
(`Expediente.descargado_en/extraido_en/version_logica_extraccion/
huella_documentos`) es `app.worker` (los manejadores de trabajo), usando los
helpers `estampar_*` de este módulo, justo después de llamar —sin tocarlas—
a `app.scraping.job.ejecutar_scraping_expediente` y a
`app.extraccion.orquestador.ejecutar_extraccion_expediente`.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import Documento, EstadoExpediente, Expediente

# Sube este valor cuando un cambio en `app.extraccion.*` deba forzar el
# reproceso de todos los expedientes aunque sus documentos no hayan cambiado
# — p.ej. un alias determinista nuevo, un umbral distinto, una regla de
# clasificación nueva (docs/analisis-corpus.md documenta varios cambios de
# este tipo a lo largo del proyecto). Comparado contra
# `Expediente.version_logica_extraccion`; cualquier cadena sirve, no hace
# falta que sea un número — una fecha de sesión es una convención razonable.
VERSION_LOGICA_EXTRACCION = "2026-09-04.1"


def huella_documentos(documentos: Iterable[Documento]) -> str:
    """Hash estable del conjunto de documentos de un expediente, por
    contenido (`Documento.hash`, sección 17 de CLAUDE.md: la ruta de
    almacenamiento ya va por hash), no por índice ni por fecha: cambia si se
    añade, se quita o se sustituye un documento, sin releer ningún PDF."""
    hashes = sorted(d.hash for d in documentos)
    return hashlib.sha256(",".join(hashes).encode("utf-8")).hexdigest()


def debe_descargar(expediente: Expediente, documentos: list[Documento]) -> bool:
    """CLAUDE.md, bloque 1, punto 2: "si los tiene [documentos] y no hay
    indicios de novedad, no se descarga". Sin ninguna fuente de novedad
    propia todavía (llega en el bloque 2 con la sindicación), la única señal
    disponible hoy es si el expediente ya tiene algún documento: si no tiene
    ninguno, nunca se descargó con éxito (o el intento anterior falló sin
    dejar nada), y merece un intento nuevo. Un expediente con documentos
    nunca se redescarga solo, aunque esté `fallido` o `pendiente_revision`
    por otra causa — evitar cada descarga evitable es el punto (CLAUDE.md,
    bloque 1: "la Plataforma es lenta y frágil").

    Deliberadamente sin `forzar`: el punto 4 del bloque 1 lo pide "para
    desarrollo", y en desarrollo lo que hace falta casi siempre es forzar la
    RE-EXTRACCIÓN tras un cambio en `app.extraccion.*`, no volver a golpear
    la Plataforma real para un expediente que ya tiene sus documentos
    íntegros en disco — forzar eso también contradiría el principio de este
    mismo punto ("cada descarga evitada cuenta"). `debe_extraer` sí acepta
    `forzar`; forzar una redescarga de un expediente con documentos queda
    fuera de esta sesión (se puede seguir haciendo a mano, con el endpoint
    ya existente `POST /expedientes/{id}/descargar`)."""
    return not documentos


def debe_extraer(expediente: Expediente, documentos: list[Documento], forzar: bool) -> bool:
    """CLAUDE.md, bloque 1, punto 3: "si los documentos no han cambiado
    (mismo hash) y la lógica tampoco, no se reextrae". Deliberadamente NO
    mira si el expediente tiene documentos: un pedido derivado de acuerdo
    marco sin ningún documento propio (docs/analisis-corpus.md hallazgo 3)
    también necesita que se intente su extracción, aunque no vaya a producir
    ninguna línea — es el único camino que le queda para cruzar con el Excel
    de códigos y, a través de `codigo_matriz`, heredar de su matriz.

    `extraido_en is None` cubre tanto "nunca se ha extraído" como
    "se quedó `esperando_matriz`" — `app.worker` solo estampa `extraido_en`
    en un intento que de verdad corrió la cascada (ver su docstring), nunca
    en ese estado, así que un pedido derivado se reintenta en cada ciclo
    hasta que su matriz esté lista, sin necesitar una regla aparte aquí."""
    if forzar:
        return True
    if expediente.extraido_en is None:
        return True
    if expediente.version_logica_extraccion != VERSION_LOGICA_EXTRACCION:
        return True
    if expediente.huella_documentos != huella_documentos(documentos):
        return True
    return False


def debe_estampar_extraccion(expediente: Expediente) -> bool:
    """Solo se estampa frescura de extracción cuando de verdad corrió un
    intento completo de la cascada: no en `esperando_matriz` (ahí no hay
    nada que registrar todavía, ver docstring de `debe_extraer`) ni en
    `sin_publicar` (`ejecutar_extraccion_expediente` corta en seco sin tocar
    nada, CLAUDE.md sección 22)."""
    return expediente.estado not in (EstadoExpediente.esperando_matriz, EstadoExpediente.sin_publicar)


def estampar_descarga_exitosa(db: Session, expediente: Expediente) -> None:
    expediente.descargado_en = datetime.now(timezone.utc)
    db.commit()


def estampar_extraccion(db: Session, expediente: Expediente, documentos: list[Documento]) -> None:
    """Llamar solo cuando `debe_estampar_extraccion(expediente)` ya es
    `True` — ver docstring de esa función."""
    expediente.extraido_en = datetime.now(timezone.utc)
    expediente.version_logica_extraccion = VERSION_LOGICA_EXTRACCION
    expediente.huella_documentos = huella_documentos(documentos)
    db.commit()
