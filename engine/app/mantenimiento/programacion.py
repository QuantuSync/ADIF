"""Bloque 3 (CONTEXTO.md sección 25): ejecución programada del ciclo de
mantenimiento. Vive dentro del bucle del worker que ya existe
(`app.worker.bucle_principal`) — CONTEXTO.md sección 10, "cuatro procesos, ni
uno más": no hay un quinto proceso de tipo "scheduler", ni Redis, ni un cron
del sistema operativo. Cada vuelta del bucle (cada `WORKER_POLL_INTERVAL_
SECONDS`, unos segundos) es una comprobación barata contra `trabajos_cola`
— nunca red, nunca Playwright aquí.

"Sin solaparse consigo mismo" (bloque 3, punto 2) sale gratis de la misma
cola que ya existe: si ya hay un trabajo de un tipo `pendiente` o
`en_proceso` (programado o disparado a mano, da igual el origen), no se
encola otro. El histórico (punto 4) es la propia tabla `trabajos_cola`,
consultable con SQL (CONTEXTO.md sección 10, invariante de la cola): no hace
falta una tabla nueva que duplique la misma información.

Las funciones privadas de aquí abajo son deliberadamente genéricas por
`tipo` de trabajo, no solo por `mantenimiento_ciclo`: las copias de
seguridad automáticas (sesión 2026-09-06, `app.mantenimiento.copia_seguridad`)
necesitan exactamente el mismo mecanismo de "cada cuánto, sin solaparse
consigo mismo, con histórico en la propia cola" sobre un segundo tipo de
trabajo -- duplicar el algoritmo en un módulo aparte lo habría dejado
divergiendo con el tiempo sin que nada lo obligara a mantenerse igual.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.mantenimiento.ciclo import TIPO_TRABAJO
from app.mantenimiento.copia_seguridad import TIPO_TRABAJO as TIPO_TRABAJO_COPIA
from app.models import EstadoTrabajo, TrabajoCola
from app.queue import encolar_trabajo

DISPARADO_POR_PROGRAMADO = "programado"
DISPARADO_POR_MANUAL = "manual"


def _ultimo_trabajo(db: Session, tipo: str) -> Optional[TrabajoCola]:
    return db.execute(
        select(TrabajoCola).where(TrabajoCola.tipo == tipo).order_by(TrabajoCola.created_at.desc()).limit(1)
    ).scalar_one_or_none()


def _hay_trabajo_en_curso(db: Session, tipo: str) -> bool:
    return (
        db.execute(
            select(TrabajoCola.id)
            .where(
                TrabajoCola.tipo == tipo,
                TrabajoCola.estado.in_((EstadoTrabajo.pendiente, EstadoTrabajo.en_proceso)),
            )
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


def _con_tz(momento: Optional[datetime]) -> Optional[datetime]:
    """Mismo motivo que `app.sindicacion.descubrimiento._con_tz`: SQLite
    (tests) no conserva el huso horario al releer una columna
    `DateTime(timezone=True)`; Postgres sí."""
    if momento is not None and momento.tzinfo is None:
        return momento.replace(tzinfo=timezone.utc)
    return momento


def _proxima_ejecucion_desde(ultimo: Optional[TrabajoCola], intervalo_segundos: float) -> datetime:
    if ultimo is None:
        # Nunca ha corrido ningún trabajo de este tipo: ya tocaba (un
        # instante en el pasado, no "ahora mismo" -- comparar dos
        # `datetime.now()` tomados en instantes distintos del mismo
        # `now < próxima` sería casi siempre `True` por los microsegundos
        # de diferencia, y no lanzaría nunca la primera ejecución).
        return datetime.fromtimestamp(0, tz=timezone.utc)
    return _con_tz(ultimo.created_at) + timedelta(seconds=intervalo_segundos)


def _debe_lanzar(db: Session, tipo: str, activo: bool, intervalo_segundos: float) -> bool:
    if not activo:
        return False
    if _hay_trabajo_en_curso(db, tipo):
        return False
    ultimo = _ultimo_trabajo(db, tipo)
    return datetime.now(timezone.utc) >= _proxima_ejecucion_desde(ultimo, intervalo_segundos)


@dataclass
class EstadoMantenimiento:
    ultima_ejecucion: Optional[TrabajoCola]
    en_curso: bool
    proxima_ejecucion: datetime
    intervalo_segundos: float
    programado_activo: bool


def _obtener_estado(db: Session, tipo: str, intervalo_segundos: float, programado_activo: bool) -> EstadoMantenimiento:
    ultimo = _ultimo_trabajo(db, tipo)
    # Para mostrar en la web, "nunca ha corrido" se lee mejor como "ahora"
    # que como el 1 de enero de 1970 (ver el comentario de
    # `_proxima_ejecucion_desde` sobre por qué la decisión interna sí usa
    # el epoch).
    proxima = datetime.now(timezone.utc) if ultimo is None else _proxima_ejecucion_desde(ultimo, intervalo_segundos)
    return EstadoMantenimiento(
        ultima_ejecucion=ultimo,
        en_curso=_hay_trabajo_en_curso(db, tipo),
        proxima_ejecucion=proxima,
        intervalo_segundos=intervalo_segundos,
        programado_activo=programado_activo,
    )


def obtener_estado(db: Session) -> EstadoMantenimiento:
    """CONTEXTO.md, bloque 3 punto 3: lo que consulta la web para mostrar
    cuándo fue la última ejecución, qué encontró (`ultima_ejecucion.
    resultado`), y cuándo será la próxima."""
    return _obtener_estado(
        db, TIPO_TRABAJO, settings.mantenimiento_intervalo_segundos, settings.mantenimiento_programado_activo
    )


def verificar_y_lanzar_ciclo_programado(db: Session) -> Optional[TrabajoCola]:
    """Se llama en cada vuelta del bucle del worker. Encola un ciclo nuevo
    (`disparado_por: "programado"` en el payload, para que el histórico
    distinga por qué corrió cada ejecución — punto 4) solo si:

    1. La ejecución programada está activa (`MANTENIMIENTO_PROGRAMADO_ACTIVO`).
    2. No hay ya un ciclo `pendiente` o `en_proceso` (punto 2, "sin
       solaparse consigo mismo") -- ni programado ni disparado a mano.
    3. Ya tocaría, según el intervalo configurado desde la última vez que
       se lanzó un ciclo (de cualquier origen).

    Limitación conocida, no un descuido: con un único proceso `worker`
    (CONTEXTO.md sección 10, arquitectura de cuatro procesos) esta
    comprobación no compite consigo misma. Si algún día hubiera varias
    réplicas del worker, dos podrían decidir lanzar en la misma vuelta antes
    de que ninguna llegue a insertar — no se ha construido un bloqueo
    distribuido para un caso que la arquitectura actual no tiene."""
    if not _debe_lanzar(
        db, TIPO_TRABAJO, settings.mantenimiento_programado_activo, settings.mantenimiento_intervalo_segundos
    ):
        return None
    return encolar_trabajo(db, tipo=TIPO_TRABAJO, payload={"disparado_por": DISPARADO_POR_PROGRAMADO})


def obtener_estado_copia(db: Session) -> EstadoMantenimiento:
    """Copias de seguridad automáticas (sesión 2026-09-06): mismo cálculo
    que `obtener_estado`, sobre el tipo de trabajo `copia_seguridad`."""
    return _obtener_estado(db, TIPO_TRABAJO_COPIA, settings.backup_intervalo_segundos, settings.backup_activo)


def verificar_y_lanzar_copia_programada(db: Session) -> Optional[TrabajoCola]:
    """Mismo mecanismo que `verificar_y_lanzar_ciclo_programado` (activo,
    sin solaparse consigo mismo, según el intervalo desde la última vez),
    aplicado a las copias de seguridad automáticas -- diarias por defecto,
    configurable con `BACKUP_INTERVALO_SEGUNDOS`/`BACKUP_ACTIVO`. Se llama
    en la misma vuelta del bucle del worker que ya comprueba el ciclo de
    mantenimiento, sin ningún proceso ni cron nuevo."""
    if not _debe_lanzar(db, TIPO_TRABAJO_COPIA, settings.backup_activo, settings.backup_intervalo_segundos):
        return None
    return encolar_trabajo(db, tipo=TIPO_TRABAJO_COPIA, payload={"disparado_por": DISPARADO_POR_PROGRAMADO})
