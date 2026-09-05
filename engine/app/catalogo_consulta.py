"""Lado de lectura del catálogo (CLAUDE.md, encargo de esta sesión, punto 1
y 2): explorar el catálogo con filtros y **búsqueda por matrícula a través
de todos los expedientes**, y la trazabilidad de cada línea. `app.catalogo`
es el lado de escritura (construir y guardar líneas); este módulo solo
consulta, nunca escribe.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models import Documento, EstadoRevisionLinea, Expediente, LineaCatalogo, Lote


def _aplicar_filtros(
    stmt: Select,
    expediente: Optional[str],
    lote: Optional[str],
    matricula: Optional[str],
    q: Optional[str],
    excluir_descartadas: bool = False,
) -> Select:
    if excluir_descartadas:
        # CLAUDE.md bloque 2: una línea descartada en la cola de revisión
        # (no es material real, o no se pudo determinar) sale del catálogo
        # entregado al cliente -- pero sigue en base de datos con su
        # motivo, y sigue apareciendo en `/catalogo` y en la propia cola de
        # revisión, para no perder la traza de por qué el documento la
        # produjo (CLAUDE.md sección 9.10).
        stmt = stmt.where(LineaCatalogo.estado_revision != EstadoRevisionLinea.descartado)
    if expediente:
        stmt = stmt.where(Expediente.codigo_expediente.ilike(f"%{expediente}%"))
    if lote:
        stmt = stmt.where(Lote.identificador_lote == lote)
    if matricula:
        # Búsqueda por matrícula a través de todos los expedientes (CLAUDE.md,
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
    filas: list[tuple[LineaCatalogo, Optional[Lote], Expediente, Optional[Documento]]]


def consultar_catalogo(
    db: Session,
    expediente: Optional[str] = None,
    lote: Optional[str] = None,
    matricula: Optional[str] = None,
    q: Optional[str] = None,
    pagina: int = 1,
    tamano_pagina: int = 50,
    excluir_descartadas: bool = False,
) -> PaginaCatalogo:
    # `Lote` es outerjoin: una línea huérfana (CLAUDE.md, encargo de esta
    # sesión, punto 3 — su tabla de origen no se pudo asociar a un lote sin
    # ambigüedad) tiene `lote_id=None` pero sigue teniendo que aparecer en
    # el catálogo/cola de revisión. El join a `Expediente` ya no depende de
    # `Lote` (antes `lineas_catalogo -> lotes -> expedientes` era el único
    # camino; ahora `LineaCatalogo.expediente_id` es directo).
    base = (
        select(LineaCatalogo, Lote, Expediente, Documento)
        .join(Expediente, LineaCatalogo.expediente_id == Expediente.id)
        .outerjoin(Lote, LineaCatalogo.lote_id == Lote.id)
        .outerjoin(Documento, LineaCatalogo.documento_origen_id == Documento.id)
    )
    base = _aplicar_filtros(base, expediente, lote, matricula, q, excluir_descartadas)

    conteo_stmt = _aplicar_filtros(
        select(func.count(LineaCatalogo.id))
        .join(Expediente, LineaCatalogo.expediente_id == Expediente.id)
        .outerjoin(Lote, LineaCatalogo.lote_id == Lote.id),
        expediente, lote, matricula, q, excluir_descartadas,
    )
    total = db.execute(conteo_stmt).scalar_one()

    listado_stmt = (
        base.order_by(Expediente.codigo_expediente, Lote.identificador_lote, LineaCatalogo.orden_aparicion)
        .offset((pagina - 1) * tamano_pagina)
        .limit(tamano_pagina)
    )
    filas = db.execute(listado_stmt).all()
    return PaginaCatalogo(total=total, filas=[tuple(f) for f in filas])


def fila_a_dict(
    linea: LineaCatalogo, lote: Optional[Lote], expediente: Expediente, documento: Optional[Documento]
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
        "documento_origen_nombre": documento.nombre_archivo if documento else None,
        "pagina": linea.pagina,
        "fragmento": linea.fragmento,
    }
