"""Bloque 1, sesión 2026-09-21: la hoja "Contraste de presupuestos" del Excel,
también en la web, para quienes gestionan expedientes y presupuestos.

Las mismas dos reglas que `app.routers.conciliacion`:

1. **Las filas que se suman no se consultan aparte**: salen de
   `app.contraste_presupuestos.lineas_de_materiales_por_lote`, con los mismos
   filtros y el mismo criterio de inclusión que la hoja "Materiales".
2. **La API no decide nada**: `app.contraste_presupuestos` es el único sitio
   donde se elige el presupuesto de cada lote, qué cifra es y el resultado;
   este router solo lo llama, cuenta y filtra.

Recorre el catálogo entero: la web la pide una vez, nunca la sondea.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import Usuario, get_current_user
from app.contraste_presupuestos import (
    MOTIVOS_FUERA,
    RESULTADOS,
    construir_contraste,
    lineas_de_materiales_por_lote,
)
from app.db import get_db
from app.schemas import (
    ContrasteOut,
    FilaContrasteOut,
    LoteFueraOut,
    RecuentoContrasteOut,
    RecuentoFueraOut,
)

router = APIRouter()


@router.get("/contraste-presupuestos", response_model=ContrasteOut)
def obtener_contraste(
    resultado: Optional[str] = Query(default=None, description="Filtra por Resultado exacto"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    contraste = construir_contraste(db, lineas_de_materiales_por_lote(db))
    por_resultado = contraste.por_resultado()
    por_motivo = contraste.por_motivo_fuera()
    filtradas = [f for f in contraste.filas if resultado is None or f.resultado == resultado]
    return ContrasteOut(
        total=len(contraste.filas),
        # El recuento es siempre el del total, no el del filtro: es la cifra
        # que se compara contra el Excel.
        resultados=[RecuentoContrasteOut(resultado=r, lotes=por_resultado[r]) for r in RESULTADOS],
        filas=[FilaContrasteOut.model_validate(f, from_attributes=True) for f in filtradas],
        fuera_total=len(contraste.fuera),
        fuera=[RecuentoFueraOut(motivo=m, lotes=por_motivo[m]) for m in MOTIVOS_FUERA],
        lotes_fuera=[LoteFueraOut.model_validate(f, from_attributes=True) for f in contraste.fuera],
    )
