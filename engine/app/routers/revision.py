from decimal import Decimal

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import Usuario, get_current_user
from app.catalogo import buscar_posible_duplicado_huerfana
from app.catalogo_consulta import fila_a_dict
from app.db import get_db
from app.extraccion.cruce_codigos import AutoreferenciaMatrizError, asignar_matriz
from app.models import Documento, EstadoExpediente, EstadoRevisionLinea, Expediente, LineaCatalogo, Lote
from app.schemas import (
    ColaRevisionRespuesta,
    ExpedienteCorreccion,
    ExpedienteOut,
    ExpedienteRevisionOut,
    LineaCatalogoCorreccion,
    LineaCatalogoDescartar,
    LineaCatalogoOut,
    LineaCatalogoPendiente,
    LineaCatalogoPosibleDuplicado,
)

router = APIRouter()

_TAMANO_PAGINA_MAX = 200


def _acumular_comentario(comentarios: str | None, nuevo: str) -> str:
    """Añade una nota nueva sin perder las que ya hubiera (CONTEXTO.md sección
    7: `comentarios` es la única columna de notas humanas, y varias
    acciones de la cola de revisión -- descartar, dejar pendiente, una
    corrección con nota -- pueden escribir en ella para la misma línea a lo
    largo del tiempo)."""
    return f"{comentarios}\n{nuevo}" if comentarios else nuevo


@router.get("/revision", response_model=ColaRevisionRespuesta)
def listar_cola_revision(
    pagina: int = Query(default=1, ge=1),
    tamano_pagina: int = Query(default=50, ge=1, le=_TAMANO_PAGINA_MAX),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """CONTEXTO.md, encargo de esta sesión, punto 3: casos marcados como
    `pendiente_revision`, con el motivo real (`expediente.error`) — el
    documento al lado y la confirmación/corrección se piden por expediente
    en `/expedientes/{id}/revision`.

    Paginado desde la sesión de paginación de la cola de revisión
    (2026-09-08, mismo criterio que `GET /catalogo`): antes devolvía los
    `pendiente_revision` completos de una vez -- con 303 casos reales eran
    400 KB por respuesta, sondeados cada 3 segundos por la web
    (`RevisionPanel.tsx`)."""
    base = select(Expediente).where(Expediente.estado == EstadoExpediente.pendiente_revision)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    filas = db.execute(
        base.order_by(Expediente.updated_at.desc())
        .offset((pagina - 1) * tamano_pagina)
        .limit(tamano_pagina)
    ).scalars().all()
    return ColaRevisionRespuesta(
        total=total, pagina=pagina, tamano_pagina=tamano_pagina,
        expedientes=[ExpedienteOut.model_validate(e) for e in filas],
    )


def _linea_out_con_posible_duplicado(db: Session, linea: LineaCatalogo, fila: tuple) -> LineaCatalogoOut:
    """Bloque 4 (2026-09-07): añade la señal de "posible duplicado" a una
    huérfana antes de construir la salida -- ver docstring de
    `buscar_posible_duplicado_huerfana` para por qué es solo informativa."""
    datos = fila_a_dict(*fila)
    encontrado = buscar_posible_duplicado_huerfana(db, linea)
    if encontrado is not None:
        linea_resuelta, lote_resuelto = encontrado
        datos["posible_duplicado_de"] = LineaCatalogoPosibleDuplicado(
            linea_id=linea_resuelta.id,
            identificador_lote=lote_resuelto.identificador_lote,
            codigo_precio=linea_resuelta.codigo_precio,
            matricula=linea_resuelta.matricula,
            descripcion=linea_resuelta.descripcion,
            precio_unitario=linea_resuelta.precio_unitario,
        )
    return LineaCatalogoOut(**datos)


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
        lineas=[_linea_out_con_posible_duplicado(db, fila[0], fila) for fila in filas],
    )


@router.post("/expedientes/{expediente_id}/revision/confirmar", response_model=ExpedienteOut)
def confirmar_revision_expediente(
    expediente_id: int,
    correccion: ExpedienteCorreccion | None = Body(default=None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """CONTEXTO.md, encargo de esta sesión, punto 3: "confirmar o corregir".
    Con cuerpo vacío, confirma los datos tal cual (el caso ya estaba bien y
    el motivo era una alerta, no un error). Con campos, los corrige antes de
    confirmar y recalcula `precio_adjudicado` si cambió la baja del lote —
    la derivación de CONTEXTO.md sección 4 no puede quedar desfasada tras una
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
            try:
                asignar_matriz(expediente, correccion.codigo_matriz, sobrescribir=True)
            except AutoreferenciaMatrizError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
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
    """Corrección a nivel de línea (CONTEXTO.md, encargo de esta sesión, punto
    3): solo toca los campos que trae `correccion`, nunca borra un valor ya
    conocido con uno ausente — mismo criterio de `guardar_lineas_catalogo`
    (CONTEXTO.md sección 9.9)."""
    linea = _linea_o_404(db, linea_id)

    datos = correccion.model_dump(exclude_unset=True, exclude_none=True)
    for campo, valor in datos.items():
        setattr(linea, campo, valor)

    if datos:
        if linea.precio_unitario is not None and linea.baja_lote is not None:
            linea.precio_adjudicado = linea.precio_unitario * (Decimal("1") - linea.baja_lote)
        linea.estado_revision = EstadoRevisionLinea.corregido

    db.commit()
    return _fila_linea(db, linea_id)


@router.post("/catalogo/lineas/{linea_id}/confirmar", response_model=LineaCatalogoOut)
def confirmar_linea_catalogo(
    linea_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    linea = _linea_o_404(db, linea_id)
    linea.estado_revision = EstadoRevisionLinea.confirmado
    db.commit()
    return _fila_linea(db, linea_id)


def _linea_o_404(db: Session, linea_id: int) -> LineaCatalogo:
    linea = db.get(LineaCatalogo, linea_id)
    if linea is None:
        raise HTTPException(status_code=404, detail="línea de catálogo no encontrada")
    return linea


def _fila_linea(db: Session, linea_id: int) -> LineaCatalogoOut:
    fila = db.execute(
        select(LineaCatalogo, Lote, Expediente, Documento)
        .join(Expediente, LineaCatalogo.expediente_id == Expediente.id)
        .outerjoin(Lote, LineaCatalogo.lote_id == Lote.id)
        .outerjoin(Documento, LineaCatalogo.documento_origen_id == Documento.id)
        .where(LineaCatalogo.id == linea_id)
    ).one()
    return _linea_out_con_posible_duplicado(db, fila[0], fila)


@router.post("/catalogo/lineas/{linea_id}/descartar", response_model=LineaCatalogoOut)
def descartar_linea_catalogo(
    linea_id: int,
    cuerpo: LineaCatalogoDescartar,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """CONTEXTO.md bloque 2: una línea que no es material real o no se puede
    determinar sale del catálogo entregado (`app.exportacion.
    generar_excel_catalogo` la excluye), pero se queda en base de datos con
    su motivo -- nunca se borra, para no perder la traza de por qué el
    documento producía esta fila (CONTEXTO.md sección 9.10)."""
    linea = _linea_o_404(db, linea_id)
    linea.estado_revision = EstadoRevisionLinea.descartado
    linea.comentarios = _acumular_comentario(linea.comentarios, f"Descartada: {cuerpo.motivo}")
    db.commit()
    return _fila_linea(db, linea_id)


@router.post("/catalogo/lineas/{linea_id}/pendiente", response_model=LineaCatalogoOut)
def marcar_linea_pendiente(
    linea_id: int,
    cuerpo: LineaCatalogoPendiente,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """CONTEXTO.md bloque 2: para cuando quien revisa necesita consultarlo con
    otra persona antes de confirmar, corregir o descartar -- la línea sigue
    en el catálogo (a diferencia de `descartar_linea_catalogo`) mientras se
    resuelve."""
    linea = _linea_o_404(db, linea_id)
    linea.estado_revision = EstadoRevisionLinea.pendiente
    linea.comentarios = _acumular_comentario(linea.comentarios, f"Pendiente: {cuerpo.nota}")
    db.commit()
    return _fila_linea(db, linea_id)
