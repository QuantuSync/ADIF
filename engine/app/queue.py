import socket
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EstadoTrabajo, TrabajoCola


def encolar_trabajo(
    db: Session, tipo: str, payload: Optional[dict] = None, expediente_id: Optional[int] = None
) -> TrabajoCola:
    trabajo = TrabajoCola(tipo=tipo, payload=payload, expediente_id=expediente_id)
    db.add(trabajo)
    db.commit()
    db.refresh(trabajo)
    return trabajo


def tomar_siguiente_trabajo(db: Session) -> Optional[TrabajoCola]:
    """Bloqueo por fila: SELECT ... FOR UPDATE SKIP LOCKED. Sin Redis, sin Celery."""
    stmt = (
        select(TrabajoCola)
        .where(TrabajoCola.estado == EstadoTrabajo.pendiente)
        .order_by(TrabajoCola.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
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
    """CLAUDE.md sección 17 (pendiente): un trabajo `en_proceso` cuyo
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
