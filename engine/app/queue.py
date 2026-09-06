import logging
import socket
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EstadoTrabajo, TrabajoCola

logger = logging.getLogger("worker")


def encolar_trabajo(
    db: Session, tipo: str, payload: Optional[dict] = None, expediente_id: Optional[int] = None
) -> TrabajoCola:
    trabajo = TrabajoCola(tipo=tipo, payload=payload, expediente_id=expediente_id)
    db.add(trabajo)
    db.commit()
    db.refresh(trabajo)
    return trabajo


def tomar_siguiente_trabajo(
    db: Session, excluir_tipos: Optional[Iterable[str]] = None
) -> Optional[TrabajoCola]:
    """Bloqueo por fila: SELECT ... FOR UPDATE SKIP LOCKED. Sin Redis, sin Celery.

    `excluir_tipos` (bloque 1 del ciclo de mantenimiento,
    `app.mantenimiento.ciclo`): el drenaje síncrono del ciclo nunca debe
    recoger otro trabajo de su propio tipo (evita que un ciclo se reprocese
    a sí mismo, o que dos ciclos se entrelacen) — el bucle normal del worker
    no pasa este parámetro y sí los recoge, que es como llegan a ejecutarse
    los ciclos programados (bloque 3)."""
    stmt = select(TrabajoCola).where(TrabajoCola.estado == EstadoTrabajo.pendiente)
    if excluir_tipos:
        stmt = stmt.where(TrabajoCola.tipo.notin_(list(excluir_tipos)))
    stmt = stmt.order_by(TrabajoCola.created_at).limit(1).with_for_update(skip_locked=True)
    trabajo = db.execute(stmt).scalar_one_or_none()
    if trabajo is None:
        return None
    trabajo.estado = EstadoTrabajo.en_proceso
    trabajo.bloqueado_por = socket.gethostname()
    trabajo.bloqueado_en = datetime.now(timezone.utc)
    trabajo.intentos += 1
    db.commit()
    db.refresh(trabajo)
    return trabajo


def reclamar_trabajos_huerfanos(db: Session, umbral_segundos: float) -> int:
    """CONTEXTO.md sección 17 (pendiente): un trabajo `en_proceso` cuyo
    `bloqueado_en` supera `umbral_segundos` pertenece a un worker que ya no
    existe (contenedor caído, `dockerd` reiniciado a mitad de ejecución) y
    `tomar_siguiente_trabajo` nunca vuelve a mirarlo porque solo busca
    `estado = pendiente`. Se reclama igual que un fallo normal: vuelve a
    `pendiente` si le quedan intentos, o a `fallido` si ya los agotó — nunca
    se reinicia `intentos`, para no darle una oportunidad extra que un fallo
    corriente no tendría. Devuelve cuántos trabajos se reclamaron."""
    limite = datetime.now(timezone.utc) - timedelta(seconds=umbral_segundos)
    stmt = (
        select(TrabajoCola)
        .where(TrabajoCola.estado == EstadoTrabajo.en_proceso, TrabajoCola.bloqueado_en < limite)
        .with_for_update(skip_locked=True)
    )
    trabajos = db.execute(stmt).scalars().all()
    for trabajo in trabajos:
        if trabajo.intentos < trabajo.max_intentos:
            trabajo.estado = EstadoTrabajo.pendiente
            trabajo.error = (
                f"trabajo huérfano: bloqueado_en superó el umbral de {umbral_segundos:.0f}s "
                "sin completarse (worker caído o reiniciado a mitad de ejecución)"
            )
        else:
            trabajo.estado = EstadoTrabajo.fallido
            trabajo.error = (
                f"trabajo huérfano: bloqueado_en superó el umbral de {umbral_segundos:.0f}s "
                f"y ya agotó sus {trabajo.max_intentos} intentos"
            )
        trabajo.bloqueado_por = None
        trabajo.bloqueado_en = None
    db.commit()
    return len(trabajos)


def ejecutar_trabajo(db: Session, trabajo: TrabajoCola, manejadores: dict) -> None:
    """Despachador genérico por `trabajo.tipo`, con `manejadores` inyectado
    en vez de importado: lo usa tanto el bucle principal del worker
    (`app/worker.py`, con su tabla real de manejadores) como el drenaje
    síncrono del ciclo de mantenimiento (`app.mantenimiento.ciclo`) — una
    sola implementación, nunca una copia."""
    manejador = manejadores.get(trabajo.tipo)
    if manejador is None:
        trabajo.estado = EstadoTrabajo.fallido
        trabajo.error = f"tipo de trabajo desconocido: {trabajo.tipo}"
        db.commit()
        return
    trabajo_id = trabajo.id  # capturado antes del try: sigue legible aunque la sesión quede rota
    try:
        resultado = manejador(db, trabajo)
        trabajo.estado = EstadoTrabajo.completado
        trabajo.resultado = resultado
        trabajo.error = None
    except Exception as exc:  # noqa: BLE001
        # Un fallo a mitad de `manejador` (p.ej. un INSERT que viola una
        # constraint) deja la transacción de `db` en estado "necesita
        # rollback": cualquier acceso a un atributo expirado de `trabajo`
        # -incluido leerlo para este mismo log- dispara un
        # PendingRollbackError que tapaba el error real y mataba el proceso
        # entero del worker en vez de marcar el trabajo como fallido.
        db.rollback()
        logger.exception("fallo procesando trabajo %s", trabajo_id)
        trabajo.estado = (
            EstadoTrabajo.pendiente if trabajo.intentos < trabajo.max_intentos else EstadoTrabajo.fallido
        )
        trabajo.error = str(exc)
    db.commit()
