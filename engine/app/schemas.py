from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


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
    estado: str
    error: Optional[str] = None
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
    lote_id: int
    expediente_id: int
    codigo_expediente: str
    codigo_matriz: Optional[str] = None
    nombre_proyecto: Optional[str] = None
    codigo_interno: Optional[str] = None
    codigos_cruzados: Optional[bool] = None
    identificador_lote: str
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
    resultado: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
