from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from app.auth import Usuario, get_current_user
from app.catalogo import buscar_posible_duplicado_huerfana
from app.catalogo_consulta import fila_a_dict
from app.db import get_db
from app.extraccion.cruce_codigos import AutoreferenciaMatrizError, asignar_matriz
from app.models import (
    CandidatoMatricula,
    Documento,
    DocumentoExpediente,
    EstadoExpediente,
    EstadoRevisionLinea,
    Expediente,
    LineaCatalogo,
    Lote,
)
from app.schemas import (
    CandidatoMatriculaAceptar,
    ColaCandidatosMatriculaRespuesta,
    ColaRevisionRespuesta,
    ExpedienteCorreccion,
    ExpedienteOut,
    ExpedienteRevisionOut,
    LineaCandidatosMatriculaOut,
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
    # Colisión de hash entre expedientes hermanos (2026-09-08, migración
    # 0021): los documentos de un expediente ya no cuelgan de
    # `Documento.expediente_id` (no existe) -- se listan por la relación,
    # que puede enlazar el mismo `Documento` físico con más de un expediente.
    # `DocumentoOut.nombre_archivo` se rellena desde `DocumentoExpediente`
    # como atributo transitorio (mismo patrón que
    # `app.extraccion.orquestador._items_documentos`): no es una columna de
    # `Documento`, así que Pydantic (`from_attributes=True`) no la vería si
    # no se asigna aquí antes de construir la respuesta.
    filas_documentos = db.execute(
        select(Documento, DocumentoExpediente.nombre_archivo)
        .join(DocumentoExpediente, DocumentoExpediente.documento_id == Documento.id)
        .where(DocumentoExpediente.expediente_id == expediente_id)
        .order_by(Documento.id)
    ).all()
    documentos = []
    for doc, nombre_archivo in filas_documentos:
        doc.nombre_archivo = nombre_archivo
        documentos.append(doc)

    filas = db.execute(
        select(LineaCatalogo, Lote, Expediente, Documento, DocumentoExpediente.nombre_archivo)
        .join(Expediente, LineaCatalogo.expediente_id == Expediente.id)
        .outerjoin(Lote, LineaCatalogo.lote_id == Lote.id)
        .outerjoin(Documento, LineaCatalogo.documento_origen_id == Documento.id)
        .outerjoin(
            DocumentoExpediente,
            (DocumentoExpediente.documento_id == Documento.id)
            & (DocumentoExpediente.expediente_id == LineaCatalogo.expediente_id),
        )
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
        select(LineaCatalogo, Lote, Expediente, Documento, DocumentoExpediente.nombre_archivo)
        .join(Expediente, LineaCatalogo.expediente_id == Expediente.id)
        .outerjoin(Lote, LineaCatalogo.lote_id == Lote.id)
        .outerjoin(Documento, LineaCatalogo.documento_origen_id == Documento.id)
        .outerjoin(
            DocumentoExpediente,
            (DocumentoExpediente.documento_id == Documento.id)
            & (DocumentoExpediente.expediente_id == LineaCatalogo.expediente_id),
        )
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


@router.get("/revision/candidatos-matricula", response_model=ColaCandidatosMatriculaRespuesta)
def listar_cola_candidatos_matricula(
    pagina: int = Query(default=1, ge=1),
    tamano_pagina: int = Query(default=50, ge=1, le=_TAMANO_PAGINA_MAX),
    codigo_expediente: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Bloque 1, sesión 2026-09-11: cola de líneas sin matrícula con al
    menos un candidato (`app.extraccion.candidatos_matricula`), ordenada por
    confianza -- las que traen un candidato con coincidencia exacta de texto
    primero, luego por similitud descendente. Nunca incluye una línea que ya
    tiene matrícula (de documento o confirmada aquí) ni una cuyos candidatos
    ya se rechazaron todos (`matricula_candidatos_rechazados`) -- esa
    decisión saca la línea de la cola sin borrar el rastro de qué se le
    ofreció."""
    mejor_candidato = (
        select(
            CandidatoMatricula.linea_catalogo_id.label("linea_catalogo_id"),
            # `func.max` sobre un booleano no es portable entre motores
            # (SQLite lo trata como entero 0/1 sin más; PostgreSQL exige
            # `bool_or`) -- el `cast` a entero funciona igual en los dos, y
            # esta consulta corre contra SQLite en los tests de esta sesión
            # (`tests/conftest.py`) y PostgreSQL en producción.
            func.max(cast(CandidatoMatricula.exacto, Integer)).label("tiene_exacto"),
            func.max(CandidatoMatricula.similitud).label("mejor_similitud"),
        )
        .group_by(CandidatoMatricula.linea_catalogo_id)
        .subquery()
    )
    base = (
        select(LineaCatalogo, Expediente, Lote)
        .join(Expediente, LineaCatalogo.expediente_id == Expediente.id)
        .outerjoin(Lote, LineaCatalogo.lote_id == Lote.id)
        .join(mejor_candidato, mejor_candidato.c.linea_catalogo_id == LineaCatalogo.id)
        .where(
            LineaCatalogo.matricula.is_(None),
            LineaCatalogo.matricula_candidatos_rechazados.isnot(True),
        )
    )
    if codigo_expediente:
        # Encargo de esta sesión: "que se pueda filtrar por expediente, para
        # que alguien pueda revisar de golpe todo lo de un contrato" --
        # coincidencia parcial, no exacta, porque el código completo
        # ("6.24/28510.0088") es largo de teclear entero.
        base = base.where(Expediente.codigo_expediente.ilike(f"%{codigo_expediente.strip()}%"))
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    filas = db.execute(
        base.order_by(mejor_candidato.c.tiene_exacto.desc(), mejor_candidato.c.mejor_similitud.desc(), LineaCatalogo.id)
        .offset((pagina - 1) * tamano_pagina)
        .limit(tamano_pagina)
    ).all()

    lineas_out = []
    for linea, expediente, lote in filas:
        candidatos = db.execute(
            select(CandidatoMatricula)
            .where(CandidatoMatricula.linea_catalogo_id == linea.id)
            .order_by(CandidatoMatricula.exacto.desc(), CandidatoMatricula.similitud.desc())
        ).scalars().all()
        lineas_out.append(
            LineaCandidatosMatriculaOut(
                linea_id=linea.id,
                expediente_id=expediente.id,
                codigo_expediente=expediente.codigo_expediente,
                identificador_lote=lote.identificador_lote if lote else None,
                codigo_precio=linea.codigo_precio,
                descripcion=linea.descripcion,
                candidatos=list(candidatos),
            )
        )
    return ColaCandidatosMatriculaRespuesta(
        total=total, pagina=pagina, tamano_pagina=tamano_pagina, lineas=lineas_out
    )


@router.post("/revision/candidatos-matricula/{linea_id}/aceptar", response_model=LineaCatalogoOut)
def aceptar_candidato_matricula(
    linea_id: int,
    cuerpo: CandidatoMatriculaAceptar,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Bloque 1, sesión 2026-09-11: la única vía por la que una línea sin
    matrícula en el documento puede acabar con una -- nunca automático
    (CONTEXTO.md, análisis previo: "el sistema nunca inventa una matrícula").
    `matricula_candidata` tiene que ser una de las opciones VIGENTES de esta
    línea (recalculadas por última vez, no una de una pasada anterior que ya
    no aplique) -- si la cola cambió entre cargar la pantalla y aceptar, se
    rechaza con 400 en vez de asignar una matrícula que ya no está entre las
    opciones ofrecidas."""
    linea = _linea_o_404(db, linea_id)
    candidato = db.execute(
        select(CandidatoMatricula).where(
            CandidatoMatricula.linea_catalogo_id == linea_id,
            CandidatoMatricula.matricula_candidata == cuerpo.matricula_candidata,
        )
    ).scalar_one_or_none()
    if candidato is None:
        raise HTTPException(
            status_code=400,
            detail=f"'{cuerpo.matricula_candidata}' no es un candidato vigente de esta línea",
        )
    linea.matricula = candidato.matricula_candidata
    linea.matricula_confirmada_manualmente = True
    linea.matricula_candidatos_rechazados = None
    db.commit()
    return _fila_linea(db, linea_id)


@router.post("/revision/candidatos-matricula/{linea_id}/rechazar", response_model=LineaCatalogoOut)
def rechazar_candidatos_matricula(
    linea_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Ninguno de los candidatos ofrecidos es el material correcto -- saca
    la línea de la cola sin tocar `matricula` (sigue sin ella, como antes)
    ni borrar sus `candidatos_matricula` (siguen contando para "líneas con
    al menos un candidato" en el resumen de `app.extraccion.
    candidatos_matricula`)."""
    linea = _linea_o_404(db, linea_id)
    linea.matricula_candidatos_rechazados = True
    db.commit()
    return _fila_linea(db, linea_id)


@router.post("/revision/candidatos-matricula/{linea_id}/pendiente", response_model=LineaCatalogoOut)
def marcar_candidatos_matricula_pendiente(
    linea_id: int,
    cuerpo: LineaCatalogoPendiente,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Ni se acepta ni se rechaza todavía -- deja una nota (p.ej. "consultar
    con almacén") y la línea sigue en la cola tal cual, para retomarla más
    tarde."""
    linea = _linea_o_404(db, linea_id)
    linea.comentarios = _acumular_comentario(linea.comentarios, f"Candidatos de matrícula pendientes: {cuerpo.nota}")
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
