from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import Usuario, get_current_user
from app.db import get_db
from app.models import Expediente
from app.queue import encolar_trabajo

router = APIRouter()


@router.post("/trabajos/ping")
def crear_trabajo_ping(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    trabajo = encolar_trabajo(db, tipo="ping")
    return {"id": trabajo.id, "estado": trabajo.estado}


@router.post("/expedientes/{expediente_id}/descargar")
def lanzar_descarga_expediente(
    expediente_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Encola el scraping de este expediente en la Plataforma. El worker lo
    recoge, descarga los documentos y los registra (app/scraping/job.py)."""
    expediente = db.get(Expediente, expediente_id)
    if expediente is None:
        raise HTTPException(status_code=404, detail="expediente no encontrado")
    trabajo = encolar_trabajo(db, tipo="descargar_expediente", expediente_id=expediente.id)
    return {"id": trabajo.id, "estado": trabajo.estado, "expediente_id": expediente.id}
