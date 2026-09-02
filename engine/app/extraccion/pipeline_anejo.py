"""Encadena las etapas 3 a 6 de la cascada (CLAUDE.md sección 5) sobre un
documento completo: localizar páginas candidatas, extraer sus tablas, mapear
cada cabecera (con caché) y normalizar las filas a líneas de catálogo listas
para `app.catalogo.guardar_lineas_catalogo`. No persiste nada por sí mismo —
el llamador decide el `lote_id` y hace la escritura, esta función solo sabe
de un documento."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import pdfplumber
from sqlalchemy.orm import Session

from app.catalogo import construir_lineas_desde_tabla
from app.extraccion.localizador import ResultadoLocalizacion, localizar_paginas_candidatas
from app.extraccion.mapeo_cabecera import mapear_cabecera
from app.extraccion.tabla import extraer_tablas_pagina
from app.extraccion.texto import PaginaTexto
from app.interfaces.model_provider import ModelProvider


@dataclass(frozen=True)
class ResultadoProcesamientoAnejo:
    lineas: list[dict]
    localizacion: ResultadoLocalizacion
    tablas_procesadas: int
    llamadas_modelo: int
    firmas_cabecera: set[str] = field(default_factory=set)


def procesar_anejo(
    ruta_pdf,
    documento_origen_id: Optional[int],
    baja_lote: Optional[Decimal],
    db: Session,
    model_provider: Optional[ModelProvider] = None,
) -> ResultadoProcesamientoAnejo:
    lineas: list[dict] = []
    tablas_procesadas = 0
    llamadas_modelo = 0
    firmas_cabecera: set[str] = set()

    with pdfplumber.open(ruta_pdf) as pdf:
        paginas_texto = [
            PaginaTexto(numero=i, texto=p.extract_text() or "") for i, p in enumerate(pdf.pages, start=1)
        ]
        localizacion = localizar_paginas_candidatas(paginas_texto)

        for candidata in localizacion.candidatas:
            pagina = pdf.pages[candidata.numero - 1]
            for tabla in extraer_tablas_pagina(pagina):
                resultado_mapeo = mapear_cabecera(tabla.cabecera, tabla.filas[:3], db, model_provider)
                firmas_cabecera.add(resultado_mapeo.firma)
                if resultado_mapeo.llamada_modelo:
                    llamadas_modelo += 1
                tablas_procesadas += 1
                lineas.extend(
                    construir_lineas_desde_tabla(
                        tabla, resultado_mapeo.mapeo, documento_origen_id, baja_lote, orden_inicial=len(lineas)
                    )
                )

    return ResultadoProcesamientoAnejo(
        lineas=lineas,
        localizacion=localizacion,
        tablas_procesadas=tablas_procesadas,
        llamadas_modelo=llamadas_modelo,
        firmas_cabecera=firmas_cabecera,
    )
