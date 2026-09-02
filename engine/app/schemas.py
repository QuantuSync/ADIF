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
    importe_licitacion: Optional[Decimal] = None
    importe_adjudicacion: Optional[Decimal] = None
    baja_global: Optional[Decimal] = None
    estado: str
    error: Optional[str] = None
    created_at: datetime


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
