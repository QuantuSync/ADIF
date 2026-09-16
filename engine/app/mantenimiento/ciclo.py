"""Ciclo de mantenimiento (CONTEXTO.md sección 23): descubrir expedientes
nuevos por sindicación (bloque 2, `app.sindicacion.descubrimiento`),
descargar lo que falte y extraer lo que falte — como un tipo de trabajo más
de la cola (CONTEXTO.md sección 10: "no un script suelto"), no como un comando
aparte.

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
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.interfaces.document_storage import DocumentStorage
from app.interfaces.model_provider import ModelProvider
from app.mantenimiento.auditoria import TIPO_TRABAJO as TIPO_TRABAJO_AUDITORIA
from app.mantenimiento.frescura import (
    debe_descargar,
    debe_extraer,
    debe_rebuscar_sin_publicar,
    sin_publicar_confirmado,
    sin_publicar_reintento_desde,
)
from app.models import Documento, DocumentoExpediente, EstadoExpediente, Expediente, TrabajoCola
from app.queue import ejecutar_trabajo, encolar_trabajo, tomar_siguiente_trabajo
from app.scraping.descubrimiento_busqueda import descubrir_por_busqueda
from app.sindicacion.descubrimiento import descubrir_novedades

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
    # Sesión 2026-09-15 (`_reintentar_sin_publicar`): búsquedas lanzadas de
    # nuevo, las que tocaban pero no cupieron en el tope, y las que aún
    # están dentro de su plazo.
    sin_publicar_reintentados: int = 0
    sin_publicar_aplazados: int = 0
    sin_publicar_en_plazo: int = 0
    duracion_segundos: float = 0.0
    # Resumen completo de app.sindicacion.descubrimiento.ResumenDescubrimiento
    # (o {"error": ...} si el descubrimiento falló) — None si estaba
    # desactivado para esta ejecución (payload "sindicacion_desactivada").
    descubrimiento: Optional[dict] = field(default=None)
    # Sesión 2026-09-16: resumen de `app.scraping.descubrimiento_busqueda`
    # (la vía que cubre lo que sigue en licitación, que la sindicación no
    # ve). None si estaba desactivado para esta ejecución
    # (`BUSQUEDA_DESCUBRIMIENTO_ACTIVO` o payload "busqueda_desactivada").
    descubrimiento_busqueda: Optional[dict] = field(default=None)
    # BLOQUE 1, sesión de auditoría automática 2026-09-08: resultado completo
    # de `app.mantenimiento.auditoria.ejecutar_auditoria` sobre el estado del
    # catálogo YA con lo que este mismo ciclo acaba de descargar/extraer —
    # None solo si encolarla o ejecutarla fallara (nunca debe impedir que el
    # resto del ciclo se dé por bueno: ver el manejo de errores más abajo).
    auditoria: Optional[dict] = field(default=None)

    def to_dict(self) -> dict:
        return {
            "expedientes_evaluados": self.expedientes_evaluados,
            "nuevos_descubiertos": self.nuevos_descubiertos,
            "descargas_lanzadas": self.descargas_lanzadas,
            "extracciones_lanzadas": self.extracciones_lanzadas,
            "saltados_descarga": self.saltados_descarga,
            "saltados_extraccion": self.saltados_extraccion,
            "trabajos_drenados": self.trabajos_drenados,
            "sin_publicar_reintentados": self.sin_publicar_reintentados,
            "sin_publicar_aplazados": self.sin_publicar_aplazados,
            "sin_publicar_en_plazo": self.sin_publicar_en_plazo,
            "duracion_segundos": round(self.duracion_segundos, 3),
            "descubrimiento": self.descubrimiento,
            "descubrimiento_busqueda": self.descubrimiento_busqueda,
            "auditoria": self.auditoria,
        }


def _renovar_bloqueo(db: Session, trabajo: TrabajoCola) -> None:
    """Latido de resumibilidad (sesión 2026-09-11, propuesta ya documentada en
    CONTEXTO.md "pendiente de resolver"): `tomar_siguiente_trabajo` fija
    `bloqueado_en` una sola vez al arrancar el trabajo y nunca lo refresca
    mientras corre -- un `mantenimiento_ciclo` real dura horas por diseño
    (drena la cola de forma síncrona dentro de sí mismo), así que cualquier
    reinicio del worker durante una ejecución sana lo marcaba huérfano casi
    con certeza (`reclamar_trabajos_huerfanos`, umbral de 300 s). Refrescar
    `bloqueado_en` en cada vuelta del drenaje (ya hay una por trabajo
    drenado, es el punto natural) hace que un reinicio real detecte un
    cuelgue rápido de verdad sin penalizar una ejecución larga y viva."""
    trabajo.bloqueado_en = datetime.now(timezone.utc)
    db.commit()


def _documentos_por_expediente(db: Session, expedientes: list[Expediente]) -> dict[int, list[Documento]]:
    """Sesión de colisión de hash entre expedientes hermanos (2026-09-08,
    migración 0021): un documento puede pertenecer a varios expedientes, así
    que se agrupa por `DocumentoExpediente.expediente_id` (la relación),
    nunca por un `Documento.expediente_id` que ya no existe -- el mismo
    `Documento` puede aparecer en la lista de más de un expediente."""
    if not expedientes:
        return {}
    ids = [e.id for e in expedientes]
    filas = db.execute(
        select(DocumentoExpediente.expediente_id, Documento)
        .join(Documento, Documento.id == DocumentoExpediente.documento_id)
        .where(DocumentoExpediente.expediente_id.in_(ids))
    ).all()
    resultado: dict[int, list[Documento]] = {e.id: [] for e in expedientes}
    for expediente_id, doc in filas:
        resultado.setdefault(expediente_id, []).append(doc)
    return resultado


def _reintentar_sin_publicar(db: Session, resumen: ResumenCiclo) -> None:
    """Sesión 2026-09-15: `sin_publicar` deja de ser definitivo. Hasta ahora
    el ciclo lo excluía siempre (arriba sigue fuera del bucle normal: sin
    documentos, `debe_descargar` lo buscaría en cada ciclo), así que un
    negativo falso -- los del bloqueo de la Plataforma de antes del
    2026-09-07 -- dejaba el expediente fuera para siempre. Aquí se vuelve a
    buscar el que ya toca (`debe_rebuscar_sin_publicar`): primero los no
    confirmados y los más antiguos, hasta `sin_publicar_reintentos_por_ciclo`.
    La descarga encadena su extracción sola si lo encuentra, y el drenaje de
    abajo la recoge igual que cualquier otra."""
    plazo = timedelta(days=settings.sin_publicar_reintento_dias)
    ahora = datetime.now(timezone.utc)
    candidatos = (
        db.execute(select(Expediente).where(Expediente.estado == EstadoExpediente.sin_publicar))
        .scalars()
        .all()
    )
    pendientes = sorted(
        (e for e in candidatos if debe_rebuscar_sin_publicar(e, plazo, ahora)),
        key=lambda e: (sin_publicar_confirmado(e), sin_publicar_reintento_desde(e, plazo), e.id),
    )
    tope = max(settings.sin_publicar_reintentos_por_ciclo, 0)
    for expediente in pendientes[:tope]:
        encolar_trabajo(db, tipo="descargar_expediente", expediente_id=expediente.id)
    resumen.sin_publicar_reintentados = min(len(pendientes), tope)
    resumen.sin_publicar_aplazados = len(pendientes) - resumen.sin_publicar_reintentados
    resumen.sin_publicar_en_plazo = len(candidatos) - len(pendientes)


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

    # Bloque 2: descubrir expedientes nuevos (y detectar cambio de estado en
    # los que ya existían) por sindicación, ANTES de evaluar frescura, para
    # que un expediente recién descubierto entre ya en el mismo bucle de
    # decisión de abajo sin esperar al ciclo siguiente. Un fallo aquí (red,
    # ZIP no disponible para el periodo) no debe impedir que el resto del
    # ciclo -- descargar/extraer lo que ya se conocía -- siga su curso.
    if not payload.get("sindicacion_desactivada"):
        try:
            resumen_descubrimiento = descubrir_novedades(
                db,
                periodo=payload.get("sindicacion_periodo"),
                ruta_zip=Path(payload["sindicacion_ruta_zip"]) if payload.get("sindicacion_ruta_zip") else None,
            )
            resumen.nuevos_descubiertos = resumen_descubrimiento.expedientes_nuevos
            resumen.descubrimiento = resumen_descubrimiento.to_dict()
        except Exception as exc:  # noqa: BLE001
            # Igual que app.queue.ejecutar_trabajo: un fallo a mitad de
            # descubrir_novedades (p.ej. un IntegrityError) deja `db` en
            # estado "necesita rollback" -- sin esto, el resto del ciclo
            # (que reutiliza la misma sesión) reventaría con un
            # PendingRollbackError que enterraría el motivo real.
            db.rollback()
            logger.warning("descubrimiento por sindicación falló, se continúa sin él: %s", exc)
            resumen.descubrimiento = {"error": str(exc)}

    # Sesión 2026-09-16: segunda vía de descubrimiento, por búsqueda directa
    # en la Plataforma (`app.scraping.descubrimiento_busqueda`). Va aquí, en
    # el mismo sitio y con el mismo trato que la sindicación -- antes del
    # bucle de frescura, para que lo que aparezca se descargue y se extraiga
    # en esta misma pasada, y con su fallo aislado (red, WAF, formulario
    # cambiado) para que no se lleve por delante el resto del ciclo. Las dos
    # vías son complementarias, no alternativas: la sindicación ve lo
    # adjudicado de cualquier mes pasado, la búsqueda ve lo que hoy está en
    # licitación o pendiente.
    if settings.busqueda_descubrimiento_activo and not payload.get("busqueda_desactivada"):
        try:
            resumen_busqueda = descubrir_por_busqueda(db, fragmentos=payload.get("busqueda_fragmentos"))
            resumen.nuevos_descubiertos += resumen_busqueda.expedientes_nuevos
            resumen.descubrimiento_busqueda = resumen_busqueda.to_dict()
        except Exception as exc:  # noqa: BLE001
            # Mismo motivo que arriba: sin el rollback, el resto del ciclo
            # reventaría con un PendingRollbackError que enterraría la causa.
            db.rollback()
            logger.warning("descubrimiento por búsqueda falló, se continúa sin él: %s", exc)
            resumen.descubrimiento_busqueda = {"error": str(exc)}

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

        if debe_extraer(expediente, documentos, forzar_expediente, ciclo_creado_en=trabajo.created_at):
            encolar_trabajo(db, tipo="extraer_expediente", expediente_id=expediente.id)
            resumen.extracciones_lanzadas += 1
        else:
            resumen.saltados_extraccion += 1

    _reintentar_sin_publicar(db, resumen)

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
        _renovar_bloqueo(db, trabajo)

    # BLOQUE 1, sesión de auditoría automática (2026-09-08): "que corra sola
    # al terminar cada ciclo de mantenimiento" -- se encola DESPUÉS de que el
    # drenaje de arriba haya vaciado la cola con todo lo que este ciclo
    # lanzó, para que audite el catálogo ya con las descargas/extracciones
    # de esta misma pasada aplicadas, no el estado de antes de empezar. Se
    # ejecuta aquí mismo (no se deja pendiente para la siguiente vuelta del
    # worker) por el mismo motivo que el drenaje síncrono de arriba: que esta
    # ejecución del ciclo refleje el trabajo real hecho. Un fallo aquí (bug
    # en una comprobación, tabla bloqueada) no debe tirar el ciclo entero —
    # ya hizo su trabajo real (descubrir/descargar/extraer) antes de llegar
    # a esto.
    try:
        trabajo_auditoria = encolar_trabajo(db, tipo=TIPO_TRABAJO_AUDITORIA)
        siguiente = tomar_siguiente_trabajo(db, excluir_tipos=_TIPOS_EXCLUIDOS_DEL_DRENAJE)
        if siguiente is not None:
            ejecutar_trabajo(db, siguiente, manejadores)
            resumen.trabajos_drenados += 1
            db.refresh(trabajo_auditoria)
            resumen.auditoria = trabajo_auditoria.resultado
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning("auditoría automática de fin de ciclo falló, se continúa sin ella: %s", exc)
        resumen.auditoria = {"error": str(exc)}

    resumen.duracion_segundos = time.monotonic() - inicio
    logger.info("ciclo de mantenimiento terminado: %s", resumen.to_dict())
    return resumen.to_dict()
