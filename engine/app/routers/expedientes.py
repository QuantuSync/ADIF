from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import Usuario, get_current_user
from app.db import get_db
from app.extraccion.cruce_codigos import AutoreferenciaMatrizError, asegurar_cruce_codigos, asignar_matriz
from app.models import Expediente
from app.schemas import ExpedienteCreate, ExpedienteOut

router = APIRouter()


@router.get("/expedientes", response_model=list[ExpedienteOut])
def listar_expedientes(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    # Sesión de limpieza de catálogo (2026-09-04, encargo punto 3): antes se
    # ordenaba por `id` de creación, lo que ponía primero los pedidos de
    # acuerdo marco `esperando_matriz`/`sin_publicar` (los primeros ~14 ids
    # de esta base, CONTEXTO.md secciones 20-22) — sin baja, sin nada que
    # hacer con ellos todavía, y dando la impresión de que el catálogo
    # arranca vacío. `extraido_en`/`descargado_en` (CONTEXTO.md sección 23,
    # frescura) ya distinguen "se tocó de verdad" de "nunca se ha procesado":
    # ordenar por el más reciente de los dos pone arriba lo que tiene
    # actividad real (recién completado, o en curso ahora mismo) y hunde al
    # fondo, de forma natural, lo que nunca se ha podido procesar — sin
    # necesitar una regla aparte para "completado primero" que enterraría un
    # expediente `extrayendo` ahora mismo detrás de uno `completado` hace
    # semanas.
    orden_actividad = func.coalesce(Expediente.extraido_en, Expediente.descargado_en)
    expedientes = (
        db.execute(select(Expediente).order_by(orden_actividad.desc().nulls_last(), Expediente.id.desc()))
        .scalars()
        .all()
    )
    # Backfill perezoso (CONTEXTO.md sección 7 y docstring de
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
    ya en la lista no lo duplica (CONTEXTO.md sección 9.9)."""
    existente = db.execute(
        select(Expediente).where(Expediente.codigo_expediente == datos.codigo_expediente)
    ).scalar_one_or_none()
    try:
        if existente is not None:
            if asignar_matriz(existente, datos.codigo_matriz):
                db.commit()
            return existente

        expediente = Expediente(codigo_expediente=datos.codigo_expediente)
        asignar_matriz(expediente, datos.codigo_matriz)
    except AutoreferenciaMatrizError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(expediente)
    db.commit()
    db.refresh(expediente)
    return expediente
