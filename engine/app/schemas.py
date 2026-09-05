from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models import ModeloPrecio


class LoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identificador_lote: str
    baja_lote: Optional[Decimal] = None
    importe_licitacion: Optional[Decimal] = None
    importe_adjudicacion: Optional[Decimal] = None
    adjudicatario: Optional[str] = None
    # True cuando `baja_lote` vino de la matriz de un pedido derivado de
    # acuerdo marco, no de los propios documentos de este expediente
    # (app.extraccion.herencia_matriz).
    baja_heredada_de_matriz: Optional[bool] = None
    # Migración 0016 (sesión de trabajo pendiente real, 2026-09-05, ver
    # docs/identidad-expediente.md sección 28): `indexado_por_pedido` explica
    # por qué `baja_lote` es `None` a propósito, no por fallo -- ese modelo
    # fija la baja en cada pedido futuro contra un Acuerdo Marco, no en la
    # licitación. Sin exponer todavía en la web (mismo pendiente menor que
    # `aviso_sindicacion`, `docs/decisiones-cliente.md` sección 26).
    modelo_precio: ModeloPrecio = ModeloPrecio.fijo
    coeficiente_transformacion: Optional[Decimal] = None


class ExpedienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo_expediente: str
    codigo_matriz: Optional[str] = None
    nombre_proyecto: Optional[str] = None
    codigo_interno: Optional[str] = None
    codigos_cruzados: Optional[bool] = None
    importe_licitacion: Optional[Decimal] = None
    importe_adjudicacion: Optional[Decimal] = None
    baja_global: Optional[Decimal] = None
    # CLAUDE.md, encargo de esta sesión, punto 4 (ajuste 3): True cuando hay
    # 2+ lotes con baja distinta entre sí — `baja_global` queda en None a
    # propósito y la web tiene que decir explícitamente "varía por lote", no
    # dejar el campo vacío sin explicación.
    baja_variable_por_lote: Optional[bool] = None
    # True cuando la matriz declarada en el Anuncio PCSP propio y la columna
    # MATRIZ del Excel de códigos no coinciden entre sí (CLAUDE.md sección 7
    # y app.extraccion.cruce_codigos): el sistema no elige una en silencio.
    matriz_conflicto: Optional[bool] = None
    lotes: list[LoteOut] = []
    estado: str
    error: Optional[str] = None
    # CLAUDE.md sección 26: desajuste con la instantánea de sindicación,
    # nunca bloqueante (el PDF es el acto administrativo, la sindicación no
    # tiene su misma autoridad) — informativo, distinto de `error`.
    aviso_sindicacion: Optional[str] = None
    created_at: datetime


class DocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo_documento: str
    nombre_archivo: str
    paginas: Optional[int] = None
    procesado_en: Optional[datetime] = None


class LineaCatalogoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # None cuando la tabla de origen no se pudo asociar a un único lote sin
    # ambigüedad (CLAUDE.md, encargo de esta sesión, punto 3): la línea
    # existe y se puede revisar, pero no cuelga de ningún lote.
    lote_id: Optional[int] = None
    expediente_id: int
    codigo_expediente: str
    codigo_matriz: Optional[str] = None
    nombre_proyecto: Optional[str] = None
    codigo_interno: Optional[str] = None
    codigos_cruzados: Optional[bool] = None
    identificador_lote: Optional[str] = None
    codigo_precio: Optional[str] = None
    matricula: Optional[str] = None
    descripcion: str
    codigo_material: Optional[str] = None
    cantidad: Optional[Decimal] = None
    precio_unitario: Optional[Decimal] = None
    unidad_medida: Optional[str] = None
    baja_lote: Optional[Decimal] = None
    precio_adjudicado: Optional[Decimal] = None
    comentarios: Optional[str] = None
    # Por qué esta línea no tiene lote (siempre None si `lote_id` no es
    # None) — distinto de `comentarios`, que son notas humanas.
    motivo_revision: Optional[str] = None
    # True cuando esta línea se copió del cuadro de precios de la matriz de
    # un pedido derivado de acuerdo marco (app.extraccion.herencia_matriz).
    # `documento_origen_id`/`pagina`/`fragmento` de abajo siguen apuntando al
    # documento real de origen (el de la matriz): la trazabilidad no cambia.
    heredado_de_matriz: Optional[bool] = None
    estado_revision: str
    # Trazabilidad (CLAUDE.md sección 9.10 y encargo de esta sesión, punto 2):
    # de qué documento, página y fragmento salió esta línea.
    documento_origen_id: Optional[int] = None
    documento_origen_nombre: Optional[str] = None
    pagina: Optional[int] = None
    fragmento: Optional[str] = None


class CatalogoRespuesta(BaseModel):
    total: int
    pagina: int
    tamano_pagina: int
    lineas: list[LineaCatalogoOut]


class LineaCatalogoCorreccion(BaseModel):
    matricula: Optional[str] = None
    descripcion: Optional[str] = None
    codigo_material: Optional[str] = None
    cantidad: Optional[Decimal] = None
    precio_unitario: Optional[Decimal] = None
    unidad_medida: Optional[str] = None
    comentarios: Optional[str] = None


class ExpedienteCorreccion(BaseModel):
    importe_licitacion: Optional[Decimal] = None
    importe_adjudicacion: Optional[Decimal] = None
    baja_global: Optional[Decimal] = None
    codigo_matriz: Optional[str] = None
    codigo_interno: Optional[str] = None


class ExpedienteRevisionOut(BaseModel):
    expediente: ExpedienteOut
    documentos: list[DocumentoOut]
    lineas: list[LineaCatalogoOut]


class ExpedienteCreate(BaseModel):
    codigo_expediente: str
    codigo_matriz: Optional[str] = None


class TrabajoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    estado: str
    intentos: int
    max_intentos: int
    expediente_id: Optional[int] = None
    payload: Optional[dict] = None
    resultado: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class EstadoMantenimientoOut(BaseModel):
    ultima_ejecucion: Optional[TrabajoOut] = None
    en_curso: bool
    proxima_ejecucion: datetime
    intervalo_segundos: float
    programado_activo: bool
