from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Usuario, get_current_user
from app.db import get_db
from app.extraccion.cruce_codigos import asegurar_cruce_codigos
from app.models import Expediente
from app.schemas import ExpedienteCreate, ExpedienteOut

router = APIRouter()


@router.get("/expedientes", response_model=list[ExpedienteOut])
def listar_expedientes(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    expedientes = db.execute(select(Expediente).order_by(Expediente.id)).scalars().all()
    # Backfill perezoso (CLAUDE.md sección 7 y docstring de
    # `asegurar_cruce_codigos`): expedientes procesados antes de que
    # existiera el cruce con el Excel de códigos no se reprocesan enteros
    # solo para rellenar tres columnas.
    cambios = False
    for expediente in expedientes:
        antes = expediente.codigos_cruzados
        asegurar_cruce_codigos(db, expediente)
        cambios = cambios or expediente.codigos_cruzados != antes
    if cambios:
        db.commit()
    return expedientes


@router.post("/expedientes", response_model=ExpedienteOut)
def crear_expediente(
    datos: ExpedienteCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Idempotente por codigo_expediente: reintentar el alta de un expediente
    ya en la lista no lo duplica (CLAUDE.md sección 9.9)."""
    existente = db.execute(
        select(Expediente).where(Expediente.codigo_expediente == datos.codigo_expediente)
    ).scalar_one_or_none()
    if existente is not None:
        if datos.codigo_matriz and not existente.codigo_matriz:
            existente.codigo_matriz = datos.codigo_matriz
            db.commit()
        return existente

    expediente = Expediente(
        codigo_expediente=datos.codigo_expediente,
        codigo_matriz=datos.codigo_matriz,
    )
    db.add(expediente)
    db.commit()
    db.refresh(expediente)
    return expediente
