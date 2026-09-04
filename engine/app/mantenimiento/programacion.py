"""Bloque 3 (CLAUDE.md sección 25): ejecución programada del ciclo de
mantenimiento. Vive dentro del bucle del worker que ya existe
(`app.worker.bucle_principal`) — CLAUDE.md sección 10, "cuatro procesos, ni
uno más": no hay un quinto proceso de tipo "scheduler", ni Redis, ni un cron
del sistema operativo. Cada vuelta del bucle (cada `WORKER_POLL_INTERVAL_
SECONDS`, unos segundos) es una comprobación barata contra `trabajos_cola`
— nunca red, nunca Playwright aquí.

"Sin solaparse consigo mismo" (bloque 3, punto 2) sale gratis de la misma
cola que ya existe: si ya hay un trabajo `mantenimiento_ciclo` `pendiente` o
`en_proceso` (programado o disparado a mano, da igual el origen), no se
encola otro. El histórico (punto 4) es la propia tabla `trabajos_cola`,
consultable con SQL (CLAUDE.md sección 10, invariante de la cola): no hace
falta una tabla nueva que duplique la misma información.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.mantenimiento.ciclo import TIPO_TRABAJO
from app.models import EstadoTrabajo, TrabajoCola
from app.queue import encolar_trabajo

DISPARADO_POR_PROGRAMADO = "programado"
DISPARADO_POR_MANUAL = "manual"


def _ultimo_trabajo_ciclo(db: Session) -> Optional[TrabajoCola]:
    return db.execute(
        select(TrabajoCola)
        .where(TrabajoCola.tipo == TIPO_TRABAJO)
        .order_by(TrabajoCola.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _hay_ciclo_en_curso(db: Session) -> bool:
    return (
        db.execute(
            select(TrabajoCola.id)
            .where(
                TrabajoCola.tipo == TIPO_TRABAJO,
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


def _proxima_ejecucion_desde(ultimo: Optional[TrabajoCola]) -> datetime:
    if ultimo is None:
        # Nunca ha corrido ningún ciclo: ya tocaba (un instante en el
        # pasado, no "ahora mismo" -- comparar dos `datetime.now()`
        # tomados en instantes distintos del mismo `now < próxima` sería
        # casi siempre `True` por los microsegundos de diferencia, y no
        # lanzaría nunca el primer ciclo).
        return datetime.fromtimestamp(0, tz=timezone.utc)
    return _con_tz(ultimo.created_at) + timedelta(seconds=settings.mantenimiento_intervalo_segundos)


@dataclass
class EstadoMantenimiento:
    ultima_ejecucion: Optional[TrabajoCola]
    en_curso: bool
    proxima_ejecucion: datetime
    intervalo_segundos: float
    programado_activo: bool


def obtener_estado(db: Session) -> EstadoMantenimiento:
    """CLAUDE.md, bloque 3 punto 3: lo que consulta la web para mostrar
    cuándo fue la última ejecución, qué encontró (`ultima_ejecucion.
    resultado`), y cuándo será la próxima."""
    ultimo = _ultimo_trabajo_ciclo(db)
    # Para mostrar en la web, "nunca ha corrido" se lee mejor como "ahora"
    # que como el 1 de enero de 1970 (ver el comentario de
    # `_proxima_ejecucion_desde` sobre por qué la decisión interna sí usa
    # el epoch).
    proxima = datetime.now(timezone.utc) if ultimo is None else _proxima_ejecucion_desde(ultimo)
    return EstadoMantenimiento(
        ultima_ejecucion=ultimo,
        en_curso=_hay_ciclo_en_curso(db),
        proxima_ejecucion=proxima,
        intervalo_segundos=settings.mantenimiento_intervalo_segundos,
        programado_activo=settings.mantenimiento_programado_activo,
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
    (CLAUDE.md sección 10, arquitectura de cuatro procesos) esta
    comprobación no compite consigo misma. Si algún día hubiera varias
    réplicas del worker, dos podrían decidir lanzar en la misma vuelta antes
    de que ninguna llegue a insertar — no se ha construido un bloqueo
    distribuido para un caso que la arquitectura actual no tiene."""
    if not settings.mantenimiento_programado_activo:
        return None
    if _hay_ciclo_en_curso(db):
        return None
    ultimo = _ultimo_trabajo_ciclo(db)
    if datetime.now(timezone.utc) < _proxima_ejecucion_desde(ultimo):
        return None
    return encolar_trabajo(db, tipo=TIPO_TRABAJO, payload={"disparado_por": DISPARADO_POR_PROGRAMADO})
