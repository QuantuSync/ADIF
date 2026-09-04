"""Ciclo de mantenimiento (CLAUDE.md sección 23): descubrir expedientes
nuevos (bloque 2, todavía no implementado en este módulo), descargar lo que
falte y extraer lo que falte — como un tipo de trabajo más de la cola
(CLAUDE.md sección 10: "no un script suelto"), no como un comando aparte.

Bloque 1: decide, expediente a expediente, si hace falta encolar una
descarga o una extracción (`app.mantenimiento.frescura`) y encola lo que
haga falta con la misma `encolar_trabajo` de siempre. Después drena la cola
de forma síncrona (incluye lo que se acaba de encolar, y cualquier otra
descarga/extracción que se encadene sola, p.ej. `app.scraping.job` al
terminar una descarga) reutilizando el mismo despachador que usa el bucle
del worker (`app.queue.ejecutar_trabajo`) — nunca una copia — para que este
mismo trabajo, cuando termina, refleje el trabajo real hecho, no solo lo que
se dejó anotado en la cola para más tarde.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.interfaces.document_storage import DocumentStorage
from app.interfaces.model_provider import ModelProvider
from app.mantenimiento.frescura import debe_descargar, debe_extraer
from app.models import Documento, EstadoExpediente, Expediente, TrabajoCola
from app.queue import ejecutar_trabajo, encolar_trabajo, tomar_siguiente_trabajo

logger = logging.getLogger("mantenimiento.ciclo")

TIPO_TRABAJO = "mantenimiento_ciclo"

# El drenaje síncrono de este mismo ciclo nunca recoge otro trabajo de su
# propio tipo: evita que un ciclo se reprocese a sí mismo o que dos ciclos
# queden entrelazados. El bloqueo real contra solapamiento entre
# *ejecuciones* del ciclo programado es cosa del bloque 3.
_TIPOS_EXCLUIDOS_DEL_DRENAJE = {TIPO_TRABAJO}


@dataclass
class ResumenCiclo:
    expedientes_evaluados: int = 0
    nuevos_descubiertos: int = 0
    descargas_lanzadas: int = 0
    extracciones_lanzadas: int = 0
    saltados_descarga: int = 0
    saltados_extraccion: int = 0
    trabajos_drenados: int = 0
    duracion_segundos: float = 0.0

    def to_dict(self) -> dict:
        return {
            "expedientes_evaluados": self.expedientes_evaluados,
            "nuevos_descubiertos": self.nuevos_descubiertos,
            "descargas_lanzadas": self.descargas_lanzadas,
            "extracciones_lanzadas": self.extracciones_lanzadas,
            "saltados_descarga": self.saltados_descarga,
            "saltados_extraccion": self.saltados_extraccion,
            "trabajos_drenados": self.trabajos_drenados,
            "duracion_segundos": round(self.duracion_segundos, 3),
        }


def _documentos_por_expediente(db: Session, expedientes: list[Expediente]) -> dict[int, list[Documento]]:
    if not expedientes:
        return {}
    ids = [e.id for e in expedientes]
    filas = db.execute(select(Documento).where(Documento.expediente_id.in_(ids))).scalars().all()
    resultado: dict[int, list[Documento]] = {e.id: [] for e in expedientes}
    for doc in filas:
        resultado.setdefault(doc.expediente_id, []).append(doc)
    return resultado


def ejecutar_ciclo_mantenimiento(
    db: Session,
    storage: DocumentStorage,
    model_provider: Optional[ModelProvider],
    manejadores: dict,
    trabajo: TrabajoCola,
) -> dict:
    inicio = time.monotonic()
    payload = trabajo.payload or {}
    forzar_global = bool(payload.get("forzar"))
    forzar_ids = set(payload.get("forzar_expedientes") or [])

    resumen = ResumenCiclo()

    # Bloque 2 se engancha aquí: descubrir expedientes nuevos por sindicación
    # antes de evaluar frescura, para que un expediente recién descubierto
    # entre ya en el mismo bucle de decisión de abajo.

    expedientes = (
        db.execute(
            select(Expediente).where(Expediente.estado != EstadoExpediente.sin_publicar).order_by(Expediente.id)
        )
        .scalars()
        .all()
    )
    documentos_por_expediente = _documentos_por_expediente(db, expedientes)

    for expediente in expedientes:
        resumen.expedientes_evaluados += 1
        forzar_expediente = forzar_global or expediente.id in forzar_ids
        documentos = documentos_por_expediente.get(expediente.id, [])
        tenia_documentos = bool(documentos)

        if debe_descargar(expediente, documentos):
            encolar_trabajo(db, tipo="descargar_expediente", expediente_id=expediente.id)
            resumen.descargas_lanzadas += 1
        else:
            resumen.saltados_descarga += 1

        if not tenia_documentos:
            # La extracción de un expediente sin documentos previos llega
            # encadenada sola desde `app.scraping.job` en cuanto termine su
            # descarga (que el drenaje de más abajo recoge igual):
            # encolarla también aquí sería la misma extracción por
            # duplicado, antes incluso de saber qué documentos trajo.
            continue

        if debe_extraer(expediente, documentos, forzar_expediente):
            encolar_trabajo(db, tipo="extraer_expediente", expediente_id=expediente.id)
            resumen.extracciones_lanzadas += 1
        else:
            resumen.saltados_extraccion += 1

    # Drenaje síncrono: ejecuta aquí mismo todo lo que se acaba de encolar
    # (y cualquier otro trabajo pendiente que hubiera quedado suelto en la
    # cola) con el mismo despachador que usa el bucle del worker, para que
    # esta misma ejecución del ciclo refleje el trabajo real hecho.
    while True:
        siguiente = tomar_siguiente_trabajo(db, excluir_tipos=_TIPOS_EXCLUIDOS_DEL_DRENAJE)
        if siguiente is None:
            break
        ejecutar_trabajo(db, siguiente, manejadores)
        resumen.trabajos_drenados += 1

    resumen.duracion_segundos = time.monotonic() - inicio
    logger.info("ciclo de mantenimiento terminado: %s", resumen.to_dict())
    return resumen.to_dict()
