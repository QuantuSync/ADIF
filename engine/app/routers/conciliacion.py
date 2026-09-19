"""Bloque 5, sesión 2026-09-19 (quinta parte): la hoja "Conciliación" del
Excel, también en la web.

Existe desde la sesión 2026-09-18 (continuación) como hoja del entregable y es
lo que contesta la pregunta del cliente "¿de cuáles de los suyos no tenemos
precios, y por qué?". La web no la tenía, así que esa pregunta solo se podía
mirar abriendo el Excel.

Dos reglas que no se rompen aquí:

1. **La columna de líneas no se consulta aparte.** Sale del mismo recuento que
   escribe la hoja "Materiales" (`app.exportacion.contar_filas_de_materiales`,
   con el mismo criterio de inclusión), para que la web y el Excel no puedan
   discrepar. Si discreparan, la vista dejaría de servir para lo único que
   existe.
2. **La API no calcula nada más que eso.** `app.conciliacion` es el único
   sitio donde se decide la Situación y el motivo de cada expediente; este
   router solo la llama, cuenta por Situación y filtra.

Es una vista de solo lectura y cara de construir (recorre el catálogo
entero): la web la pide una vez y la refresca a mano, nunca la sondea.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import Usuario, get_current_user
from app.conciliacion import SITUACIONES, construir_conciliacion, describir_registro_publicado
from app.db import get_db
from app.exportacion import contar_filas_de_materiales
from app.schemas import ConciliacionOut, FilaConciliacionOut, RecuentoSituacionOut, RegistroPublicadoOut

router = APIRouter()


@router.get("/conciliacion", response_model=ConciliacionOut)
def obtener_conciliacion(
    situacion: Optional[str] = Query(default=None, description="Filtra por Situación exacta"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    conteo = contar_filas_de_materiales(db)
    filas = construir_conciliacion(db, dict(conteo))
    registro = describir_registro_publicado(db, filas)

    # El recuento por Situación es siempre el del total, no el del filtro: es
    # la cifra que el cliente compara contra el Excel.
    por_situacion = {nombre: 0 for nombre in SITUACIONES}
    for fila in filas:
        por_situacion[fila.situacion] = por_situacion.get(fila.situacion, 0) + 1

    filtradas = [f for f in filas if situacion is None or f.situacion == situacion]
    return ConciliacionOut(
        total=len(filas),
        total_lineas=sum(f.lineas_en_catalogo for f in filas),
        situaciones=[
            RecuentoSituacionOut(situacion=nombre, expedientes=por_situacion.get(nombre, 0))
            for nombre in SITUACIONES
        ],
        filas=[FilaConciliacionOut.model_validate(f, from_attributes=True) for f in filtradas],
        registro=RegistroPublicadoOut.model_validate(registro, from_attributes=True),
    )
