import socket
from datetime import datetime, timezone
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
