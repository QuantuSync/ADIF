from decimal import Decimal

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Usuario, get_current_user
from app.catalogo_consulta import fila_a_dict
from app.db import get_db
from app.models import Documento, EstadoExpediente, EstadoRevisionLinea, Expediente, LineaCatalogo, Lote
from app.schemas import (
    ExpedienteCorreccion,
    ExpedienteOut,
    ExpedienteRevisionOut,
    LineaCatalogoCorreccion,
    LineaCatalogoOut,
)

router = APIRouter()


@router.get("/revision", response_model=list[ExpedienteOut])
def listar_cola_revision(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """CLAUDE.md, encargo de esta sesión, punto 3: casos marcados como
    `pendiente_revision`, con el motivo real (`expediente.error`) — el
    documento al lado y la confirmación/corrección se piden por expediente
    en `/expedientes/{id}/revision`."""
    return db.execute(
        select(Expediente)
        .where(Expediente.estado == EstadoExpediente.pendiente_revision)
        .order_by(Expediente.updated_at.desc())
    ).scalars().all()


def _cargar_expediente_o_404(db: Session, expediente_id: int) -> Expediente:
    expediente = db.get(Expediente, expediente_id)
    if expediente is None:
        raise HTTPException(status_code=404, detail="expediente no encontrado")
    return expediente


@router.get("/expedientes/{expediente_id}/revision", response_model=ExpedienteRevisionOut)
def detalle_revision_expediente(
    expediente_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    expediente = _cargar_expediente_o_404(db, expediente_id)
    documentos = db.execute(
        select(Documento).where(Documento.expediente_id == expediente_id).order_by(Documento.id)
    ).scalars().all()

    filas = db.execute(
        select(LineaCatalogo, Lote, Expediente, Documento)
        .join(Expediente, LineaCatalogo.expediente_id == Expediente.id)
        .outerjoin(Lote, LineaCatalogo.lote_id == Lote.id)
        .outerjoin(Documento, LineaCatalogo.documento_origen_id == Documento.id)
        .where(LineaCatalogo.expediente_id == expediente_id)
        .order_by(Lote.identificador_lote, LineaCatalogo.orden_aparicion)
    ).all()

    return ExpedienteRevisionOut(
        expediente=ExpedienteOut.model_validate(expediente),
        documentos=documentos,
        lineas=[LineaCatalogoOut(**fila_a_dict(*fila)) for fila in filas],
    )


@router.post("/expedientes/{expediente_id}/revision/confirmar", response_model=ExpedienteOut)
def confirmar_revision_expediente(
    expediente_id: int,
    correccion: ExpedienteCorreccion | None = Body(default=None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """CLAUDE.md, encargo de esta sesión, punto 3: "confirmar o corregir".
    Con cuerpo vacío, confirma los datos tal cual (el caso ya estaba bien y
    el motivo era una alerta, no un error). Con campos, los corrige antes de
    confirmar y recalcula `precio_adjudicado` si cambió la baja del lote —
    la derivación de CLAUDE.md sección 4 no puede quedar desfasada tras una
    corrección manual."""
    expediente = _cargar_expediente_o_404(db, expediente_id)

    baja_cambiada = False
    if correccion is not None:
        if correccion.importe_licitacion is not None:
            expediente.importe_licitacion = correccion.importe_licitacion
        if correccion.importe_adjudicacion is not None:
            expediente.importe_adjudicacion = correccion.importe_adjudicacion
        if correccion.baja_global is not None:
            expediente.baja_global = correccion.baja_global
            baja_cambiada = True
        if correccion.codigo_matriz is not None:
            expediente.codigo_matriz = correccion.codigo_matriz
        if correccion.codigo_interno is not None:
            expediente.codigo_interno = correccion.codigo_interno

    if baja_cambiada:
        lotes = db.execute(select(Lote).where(Lote.expediente_id == expediente_id)).scalars().all()
        for lote in lotes:
            lote.baja_lote = expediente.baja_global
            lineas = db.execute(select(LineaCatalogo).where(LineaCatalogo.lote_id == lote.id)).scalars().all()
            for linea in lineas:
                linea.baja_lote = expediente.baja_global
                if linea.precio_unitario is not None:
                    linea.precio_adjudicado = linea.precio_unitario * (Decimal("1") - expediente.baja_global)

    expediente.estado = EstadoExpediente.completado
    expediente.error = None
    db.commit()
    db.refresh(expediente)
    return expediente


@router.patch("/catalogo/lineas/{linea_id}", response_model=LineaCatalogoOut)
def corregir_linea_catalogo(
    linea_id: int,
    correccion: LineaCatalogoCorreccion,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Corrección a nivel de línea (CLAUDE.md, encargo de esta sesión, punto
    3): solo toca los campos que trae `correccion`, nunca borra un valor ya
    conocido con uno ausente — mismo criterio de `guardar_lineas_catalogo`
    (CLAUDE.md sección 9.9)."""
    linea = db.get(LineaCatalogo, linea_id)
    if linea is None:
        raise HTTPException(status_code=404, detail="línea de catálogo no encontrada")

    datos = correccion.model_dump(exclude_unset=True, exclude_none=True)
    for campo, valor in datos.items():
        setattr(linea, campo, valor)

    if datos:
        if linea.precio_unitario is not None and linea.baja_lote is not None:
            linea.precio_adjudicado = linea.precio_unitario * (Decimal("1") - linea.baja_lote)
        linea.estado_revision = EstadoRevisionLinea.corregido

    db.commit()

    fila = db.execute(
        select(LineaCatalogo, Lote, Expediente, Documento)
        .join(Expediente, LineaCatalogo.expediente_id == Expediente.id)
        .outerjoin(Lote, LineaCatalogo.lote_id == Lote.id)
        .outerjoin(Documento, LineaCatalogo.documento_origen_id == Documento.id)
        .where(LineaCatalogo.id == linea_id)
    ).one()
    return LineaCatalogoOut(**fila_a_dict(*fila))


@router.post("/catalogo/lineas/{linea_id}/confirmar", response_model=LineaCatalogoOut)
def confirmar_linea_catalogo(
    linea_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    linea = db.get(LineaCatalogo, linea_id)
    if linea is None:
        raise HTTPException(status_code=404, detail="línea de catálogo no encontrada")
    linea.estado_revision = EstadoRevisionLinea.confirmado
    db.commit()

    fila = db.execute(
        select(LineaCatalogo, Lote, Expediente, Documento)
        .join(Expediente, LineaCatalogo.expediente_id == Expediente.id)
        .outerjoin(Lote, LineaCatalogo.lote_id == Lote.id)
        .outerjoin(Documento, LineaCatalogo.documento_origen_id == Documento.id)
        .where(LineaCatalogo.id == linea_id)
    ).one()
    return LineaCatalogoOut(**fila_a_dict(*fila))
