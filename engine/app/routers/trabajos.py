from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Usuario, get_current_user
from app.db import get_db
from app.models import Expediente, TrabajoCola
from app.queue import encolar_trabajo
from app.schemas import TrabajoOut

router = APIRouter()


@router.post("/trabajos/ping")
def crear_trabajo_ping(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    trabajo = encolar_trabajo(db, tipo="ping")
    return {"id": trabajo.id, "estado": trabajo.estado}


@router.get("/trabajos/{trabajo_id}", response_model=TrabajoOut)
def consultar_trabajo(
    trabajo_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    trabajo = db.get(TrabajoCola, trabajo_id)
    if trabajo is None:
        raise HTTPException(status_code=404, detail="trabajo no encontrado")
    return trabajo


@router.get("/expedientes/{expediente_id}/trabajos", response_model=list[TrabajoOut])
def listar_trabajos_expediente(
    expediente_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Historial de trabajos de este expediente, más reciente primero — lo
    que consulta la web para explicar en qué está y, si algo falló, por qué
    (CLAUDE.md, encargo de esta sesión, punto 2)."""
    if db.get(Expediente, expediente_id) is None:
        raise HTTPException(status_code=404, detail="expediente no encontrado")
    return db.execute(
        select(TrabajoCola)
        .where(TrabajoCola.expediente_id == expediente_id)
        .order_by(TrabajoCola.created_at.desc())
    ).scalars().all()


@router.post("/expedientes/{expediente_id}/descargar")
def lanzar_descarga_expediente(
    expediente_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Encola el scraping de este expediente en la Plataforma. El worker lo
    recoge, descarga los documentos y los registra (app/scraping/job.py),
    que a su vez encola la extracción al terminar."""
    expediente = db.get(Expediente, expediente_id)
    if expediente is None:
        raise HTTPException(status_code=404, detail="expediente no encontrado")
    trabajo = encolar_trabajo(db, tipo="descargar_expediente", expediente_id=expediente.id)
    return {"id": trabajo.id, "estado": trabajo.estado, "expediente_id": expediente.id}


@router.post("/expedientes/{expediente_id}/extraer")
def lanzar_extraccion_expediente(
    expediente_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Encola la extracción sola, sin repetir la descarga — para reintentar
    un expediente cuyos documentos ya están en disco (p.ej. tras corregir
    algo y querer reprocesar, o si la extracción automática encadenada
    falló)."""
    expediente = db.get(Expediente, expediente_id)
    if expediente is None:
        raise HTTPException(status_code=404, detail="expediente no encontrado")
    trabajo = encolar_trabajo(db, tipo="extraer_expediente", expediente_id=expediente.id)
    return {"id": trabajo.id, "estado": trabajo.estado, "expediente_id": expediente.id}
