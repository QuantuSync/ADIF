"""Encadena las etapas 3 a 6 de la cascada (CONTEXTO.md sección 5) sobre un
documento completo: localizar páginas candidatas, extraer sus tablas, mapear
cada cabecera (con caché) y normalizar las filas a líneas de catálogo listas
para `app.catalogo.guardar_lineas_catalogo`. No persiste nada por sí mismo —
el llamador decide el `lote_id` y hace la escritura, esta función solo sabe
de un documento.

Etapa 3.5 (asociación tabla -> lote, `app.extraccion.lote_tabla`) solo se
ejercita cuando `lotes` trae más de una entrada: con un único lote no hay
ambigüedad que resolver, y buscar cabeceras "LOTE N" en cada página sería
trabajo — y riesgo de falso positivo— sin ningún propósito (CONTEXTO.md
sección 6, el mismo principio de "no hacer trabajo que el caso no pide" que
rige cuándo se llama al modelo)."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import pdfplumber
from sqlalchemy.orm import Session

from app.catalogo import construir_lineas_desde_tabla
from app.extraccion.localizador import ResultadoLocalizacion, localizar_paginas_candidatas
from app.extraccion.lote_tabla import asociar_lote_tabla
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
    # Motivo por tabla que no se pudo asociar a un lote sin ambigüedad (ver
    # `app.extraccion.lote_tabla`), en el mismo orden en que aparecieron.
    # Vacía siempre que `lotes` traiga un único lote. El orquestador la usa
    # para componer el motivo de revisión del expediente; el script de
    # medición del corpus la usa para contar cuántas líneas caen en cada
    # caso de ambigüedad.
    tablas_sin_lote: list[str] = field(default_factory=list)
    # Líneas cuyo valor de cantidad/precio/matrícula no se pudo interpretar
    # (CONTEXTO.md, sesión de rodaje 2026-09-03) — `linea["motivo_revision"]`
    # ya lo explica por línea; este contador es solo para que el orquestador
    # sepa si tiene que avisar a nivel de expediente sin releer todas las
    # líneas.
    lineas_con_aviso: int = 0


def procesar_anejo(
    ruta_pdf,
    documento_origen_id: Optional[int],
    expediente_id: int,
    lotes: dict[str, Optional[Decimal]],
    db: Session,
    model_provider: Optional[ModelProvider] = None,
) -> ResultadoProcesamientoAnejo:
    """`lotes`: identificador de lote -> su baja (None si aún no se conoce).
    Con un solo lote (el caso de siempre hasta esta sesión: `{LOTE_UNICO:
    baja}`), todas las líneas se etiquetan con ese único identificador, sin
    pasar por la búsqueda de banda. Con varios, cada tabla localizada se
    asocia a su lote por posición (etapa 3.5); las que resulten ambiguas
    quedan con `identificador_lote=None` en cada línea — el orquestador las
    guarda con `lote_id=None` (huérfanas, CONTEXTO.md encargo de esta sesión
    punto 3: nunca por proximidad ni adivinando)."""
    lineas: list[dict] = []
    tablas_procesadas = 0
    llamadas_modelo = 0
    firmas_cabecera: set[str] = set()
    tablas_sin_lote: list[str] = []
    lineas_con_aviso = 0

    multi_lote = len(lotes) > 1
    identificador_unico = next(iter(lotes)) if len(lotes) == 1 else None

    with pdfplumber.open(ruta_pdf) as pdf:
        paginas_texto = [
            PaginaTexto(numero=i, texto=p.extract_text() or "") for i, p in enumerate(pdf.pages, start=1)
        ]
        localizacion = localizar_paginas_candidatas(paginas_texto)

        for candidata in localizacion.candidatas:
            pagina = pdf.pages[candidata.numero - 1]
            tablas_pagina = sorted(extraer_tablas_pagina(pagina), key=lambda t: t.bbox[1])
            banda_top = 0.0
            for tabla in tablas_pagina:
                if multi_lote:
                    resultado_asociacion = asociar_lote_tabla(
                        pagina, banda_top, tabla.bbox, identificadores_validos=set(lotes)
                    )
                    identificador_lote = resultado_asociacion.identificador_lote
                    motivo_ambiguo = resultado_asociacion.motivo_ambiguo
                    if motivo_ambiguo is not None:
                        tablas_sin_lote.append(
                            f"página {tabla.pagina}: {motivo_ambiguo}"
                        )
                else:
                    identificador_lote = identificador_unico
                    motivo_ambiguo = None
                banda_top = tabla.bbox[3]

                baja_lote = lotes.get(identificador_lote) if identificador_lote is not None else None

                resultado_mapeo = mapear_cabecera(tabla.cabecera, tabla.filas[:3], db, model_provider)
                firmas_cabecera.add(resultado_mapeo.firma)
                if resultado_mapeo.llamada_modelo:
                    llamadas_modelo += 1
                tablas_procesadas += 1
                lineas_tabla = construir_lineas_desde_tabla(
                    tabla, resultado_mapeo.mapeo, documento_origen_id, expediente_id, baja_lote,
                    orden_inicial=len(lineas),
                )
                for linea in lineas_tabla:
                    linea["identificador_lote"] = identificador_lote
                    # `construir_linea_catalogo` (CONTEXTO.md, sesión de rodaje
                    # 2026-09-03) ya puede haber puesto su propio
                    # `motivo_revision` (un valor de cantidad/precio/matrícula
                    # ilegible): se cuenta aparte de la ambigüedad de lote
                    # (que ya se resume en `tablas_sin_lote`) para que el
                    # orquestador sepa si hay algo nuevo que avisar. La
                    # ambigüedad de lote nunca pisa este motivo, se combina.
                    if linea.get("motivo_revision"):
                        lineas_con_aviso += 1
                    if motivo_ambiguo is not None:
                        linea["motivo_revision"] = motivo_ambiguo
                    if identificador_lote is None:
                        # Hallazgo real (expediente 6.25/28510.0027): varias
                        # tablas ambiguas del mismo documento pueden compartir
                        # codigo_precio — el mismo cuadro de precios se repite
                        # por lote (CONTEXTO.md sección 3), así que LOTE 2, 4, 5
                        # y 6 traen todos un "P-1".."P-6" propio. Sin lote que
                        # las separe, `clave_linea` a secas fundiría en una
                        # sola fila los datos de lotes distintos entre sí —
                        # justo lo que hace huérfana a la línea es no saber a
                        # qué lote pertenece, no que sea la misma línea vista
                        # dos veces. Se desambigua por la posición de la
                        # tabla de origen (página + franja vertical), no por
                        # lote.
                        linea["clave_linea"] = f"{linea['clave_linea']}@p{tabla.pagina}y{int(tabla.bbox[1])}"
                lineas.extend(lineas_tabla)

    return ResultadoProcesamientoAnejo(
        lineas=lineas,
        localizacion=localizacion,
        tablas_procesadas=tablas_procesadas,
        llamadas_modelo=llamadas_modelo,
        firmas_cabecera=firmas_cabecera,
        tablas_sin_lote=tablas_sin_lote,
        lineas_con_aviso=lineas_con_aviso,
    )
