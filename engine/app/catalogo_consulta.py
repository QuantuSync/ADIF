"""Lado de lectura del catálogo (CONTEXTO.md, encargo de esta sesión, punto 1
y 2): explorar el catálogo con filtros y **búsqueda por matrícula a través
de todos los expedientes**, y la trazabilidad de cada línea. `app.catalogo`
es el lado de escritura (construir y guardar líneas); este módulo solo
consulta, nunca escribe.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from app.models import Documento, DocumentoExpediente, EstadoRevisionLinea, Expediente, LineaCatalogo, Lote

# Órdenes disponibles para `/catalogo` (encargo de esta sesión, 2026-09-07):
# el cliente ve esta pantalla sin filtrar, y "alfabetico" (el único orden
# que existía) aterriza siempre en los mismos expedientes -- alfabéticamente
# primeros ("6.20/..." antes que "6.23/...") y, por pura coincidencia del
# corpus, justo los que tienen las tablas de origen más escasas (sin columna
# de código de precio ni de unidad en el documento real, verificado contra
# el PDF -- no un fallo de extracción). La primera pantalla daba la
# impresión de un catálogo roto cuando el 94,6% de las líneas sí traen
# unidad de medida y el 96,9% código de precio.
ORDENES_VALIDOS = ("completitud", "alfabetico")
_ORDEN_POR_DEFECTO = "completitud"


def _puntuacion_completitud():
    """Cuenta, de 0 a 4, cuántas de las columnas que de verdad varían de
    una línea a otra están rellenas: un identificador propio (código de
    precio O matrícula -- una tabla puede traer solo uno de los dos sin que
    eso sea un defecto, CONTEXTO.md sección 2: la matrícula "no es clave" y
    falta en buena parte del corpus por diseño), cantidad, unidad de medida
    y precio unitario. Descripción no cuenta -- está al 100%, no distingue
    nada. Ordenar por esto DESC pone primero las líneas que de verdad tienen
    algo que enseñar, sin fingir que el catálogo es más completo de lo que
    es: sigue siendo una cifra real por línea, solo cambia qué se ve
    primero."""
    tiene_identificador = case(
        (LineaCatalogo.codigo_precio.is_not(None), 1),
        (LineaCatalogo.matricula.is_not(None), 1),
        else_=0,
    )
    return (
        tiene_identificador
        + case((LineaCatalogo.cantidad.is_not(None), 1), else_=0)
        + case((LineaCatalogo.unidad_medida.is_not(None), 1), else_=0)
        + case((LineaCatalogo.precio_unitario.is_not(None), 1), else_=0)
    )


def _aplicar_filtros(
    stmt: Select,
    expediente: Optional[str],
    lote: Optional[str],
    matricula: Optional[str],
    q: Optional[str],
    excluir_descartadas: bool = False,
) -> Select:
    if excluir_descartadas:
        # CONTEXTO.md bloque 2: una línea descartada en la cola de revisión
        # (no es material real, o no se pudo determinar) sale del catálogo
        # entregado al cliente -- pero sigue en base de datos con su
        # motivo, y sigue apareciendo en `/catalogo` y en la propia cola de
        # revisión, para no perder la traza de por qué el documento la
        # produjo (CONTEXTO.md sección 9.10).
        stmt = stmt.where(LineaCatalogo.estado_revision != EstadoRevisionLinea.descartado)
    if expediente:
        stmt = stmt.where(Expediente.codigo_expediente.ilike(f"%{expediente}%"))
    if lote:
        stmt = stmt.where(Lote.identificador_lote == lote)
    if matricula:
        # Búsqueda por matrícula a través de todos los expedientes (CONTEXTO.md,
        # encargo de esta sesión, punto 1): sin filtro de expediente, esto ya
        # responde "cómo evoluciona el precio de un material" por sí solo.
        stmt = stmt.where(LineaCatalogo.matricula.ilike(f"%{matricula}%"))
    if q:
        patron = f"%{q}%"
        stmt = stmt.where(
            or_(
                LineaCatalogo.descripcion.ilike(patron),
                LineaCatalogo.codigo_material.ilike(patron),
                LineaCatalogo.codigo_precio.ilike(patron),
            )
        )
    return stmt


@dataclass(frozen=True)
class PaginaCatalogo:
    total: int
    filas: list[tuple[LineaCatalogo, Optional[Lote], Expediente, Optional[Documento], Optional[str]]]


def consultar_catalogo(
    db: Session,
    expediente: Optional[str] = None,
    lote: Optional[str] = None,
    matricula: Optional[str] = None,
    q: Optional[str] = None,
    pagina: int = 1,
    tamano_pagina: int = 50,
    excluir_descartadas: bool = False,
    orden: str = _ORDEN_POR_DEFECTO,
) -> PaginaCatalogo:
    # `Lote` es outerjoin: una línea huérfana (CONTEXTO.md, encargo de esta
    # sesión, punto 3 — su tabla de origen no se pudo asociar a un lote sin
    # ambigüedad) tiene `lote_id=None` pero sigue teniendo que aparecer en
    # el catálogo/cola de revisión. El join a `Expediente` ya no depende de
    # `Lote` (antes `lineas_catalogo -> lotes -> expedientes` era el único
    # camino; ahora `LineaCatalogo.expediente_id` es directo).
    # Sesión de colisión de hash entre expedientes hermanos (2026-09-08,
    # migración 0021): `Documento` ya no tiene `nombre_archivo` propio -- se
    # trae aparte desde `DocumentoExpediente`, acotado al mismo expediente
    # de la línea (así se ve el nombre que ESE expediente le dio, aunque el
    # fichero físico esté compartido con otro).
    base = (
        select(LineaCatalogo, Lote, Expediente, Documento, DocumentoExpediente.nombre_archivo)
        .join(Expediente, LineaCatalogo.expediente_id == Expediente.id)
        .outerjoin(Lote, LineaCatalogo.lote_id == Lote.id)
        .outerjoin(Documento, LineaCatalogo.documento_origen_id == Documento.id)
        .outerjoin(
            DocumentoExpediente,
            (DocumentoExpediente.documento_id == Documento.id)
            & (DocumentoExpediente.expediente_id == LineaCatalogo.expediente_id),
        )
    )
    base = _aplicar_filtros(base, expediente, lote, matricula, q, excluir_descartadas)

    conteo_stmt = _aplicar_filtros(
        select(func.count(LineaCatalogo.id))
        .join(Expediente, LineaCatalogo.expediente_id == Expediente.id)
        .outerjoin(Lote, LineaCatalogo.lote_id == Lote.id),
        expediente, lote, matricula, q, excluir_descartadas,
    )
    total = db.execute(conteo_stmt).scalar_one()

    # Orden estable en los dos casos (mismo desempate de siempre) para que
    # paginar no salte filas ni las repita: "completitud" solo antepone el
    # criterio nuevo, nunca sustituye el desempate por expediente/lote/orden
    # de aparición.
    desempate = (Expediente.codigo_expediente, Lote.identificador_lote, LineaCatalogo.orden_aparicion)
    if orden == "alfabetico":
        criterio = desempate
    else:
        criterio = (_puntuacion_completitud().desc(), *desempate)

    listado_stmt = base.order_by(*criterio).offset((pagina - 1) * tamano_pagina).limit(tamano_pagina)
    filas = db.execute(listado_stmt).all()
    return PaginaCatalogo(total=total, filas=[tuple(f) for f in filas])


def fila_a_dict(
    linea: LineaCatalogo,
    lote: Optional[Lote],
    expediente: Expediente,
    documento: Optional[Documento],
    nombre_archivo: Optional[str] = None,
) -> dict:
    return {
        "id": linea.id,
        "lote_id": lote.id if lote else None,
        "expediente_id": expediente.id,
        "codigo_expediente": expediente.codigo_expediente,
        "codigo_matriz": expediente.codigo_matriz,
        "nombre_proyecto": expediente.nombre_proyecto,
        "codigo_interno": expediente.codigo_interno,
        "codigos_cruzados": expediente.codigos_cruzados,
        "identificador_lote": lote.identificador_lote if lote else None,
        "codigo_precio": linea.codigo_precio,
        "matricula": linea.matricula,
        "descripcion": linea.descripcion,
        "codigo_material": linea.codigo_material,
        "cantidad": linea.cantidad,
        "precio_unitario": linea.precio_unitario,
        "unidad_medida": linea.unidad_medida,
        "baja_lote": linea.baja_lote,
        "precio_adjudicado": linea.precio_adjudicado,
        "comentarios": linea.comentarios,
        "motivo_revision": linea.motivo_revision,
        "heredado_de_matriz": linea.heredado_de_matriz,
        "estado_revision": linea.estado_revision.value,
        "documento_origen_id": linea.documento_origen_id,
        "documento_origen_nombre": nombre_archivo,
        "pagina": linea.pagina,
        "fragmento": linea.fragmento,
    }
