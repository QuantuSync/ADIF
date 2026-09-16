"""Etapa 2 de la cascada de extracción (CONTEXTO.md sección 5): campos de
etiqueta fija de la familia de formularios PCSP (Anuncio de adjudicación,
Anuncio de formalización de contrato, Documento de Pliegos — ver docstring de
`app.extraccion.clasificador`). Todo lo que sea de esta familia se extrae por
posición de etiqueta, sin tablas y sin modelo.

Cada valor se ancla a la página y al fragmento de texto de los que salió
(CONTEXTO.md sección 9.10): un campo ausente es `None` en el campo y no
aparece en `campos`, nunca un valor inventado.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.extraccion.invalidado import INVALIDADO
from app.extraccion.normalizacion import parsear_importe_es
from app.extraccion.texto import PaginaTexto

CODIGO_EXPEDIENTE_RE = re.compile(r"\d+\.\d+/\d+\.\d+")

_NUMERO_EXPEDIENTE_RE = re.compile(
    r"N[uú]mero de Expediente\s+(" + CODIGO_EXPEDIENTE_RE.pattern + r")",
    re.IGNORECASE,
)
_MATRIZ_RE = re.compile(
    r"Licitaci[oó]n basada en el acuerdo marco\s*\n?\s*Expediente\s+(" + CODIGO_EXPEDIENTE_RE.pattern + r")",
    re.IGNORECASE,
)
# Forma alternativa, verificada contra un documento real (sesión de
# descubrimiento inverso, `6.26/28510.0014`): la sección "Licitación basada
# en el acuerdo marco" (arriba) no siempre se publica en el Anuncio de
# adjudicación/formalización de un pedido -- pero el campo "Identificador
# contrato original", en "Proceso de Licitación", trae el mismo dato
# (verificado también en los documentos donde SÍ aparece la forma estricta,
# p.ej. `6.24/28510.0040`: los dos campos coinciden). Solo se intenta si la
# forma estricta no encontró nada, mismo criterio que las variantes laxas de
# la baja (CONTEXTO.md sección 4).
_MATRIZ_ALTERNATIVA_RE = re.compile(
    r"Identificador contrato original\s+(" + CODIGO_EXPEDIENTE_RE.pattern + r")",
    re.IGNORECASE,
)
_IMPORTE_LICITACION_RE = re.compile(
    r"Presupuesto base de licitaci[oó]n.*?Importe \(sin impuestos\)\s*([\d.,]+)\s*EUR",
    re.IGNORECASE | re.DOTALL,
)
_IMPORTE_ADJUDICACION_RE = re.compile(
    r"Importes? de Adjudicaci[oó]n.*?Importe total ofertado \(sin impuestos\)\s*([\d.,]+)\s*EUR",
    re.IGNORECASE | re.DOTALL,
)
_ADJUDICATARIO_RE = re.compile(r"^Adjudicatario\s*$\n([^\n]+)", re.MULTILINE)
# CONTEXTO.md sección 26, criterio del cliente ("solo bajas de material por
# lotes; las de obra quedan fuera de alcance"): el mismo formulario PCSP que
# ya se lee por etiqueta fija trae este campo ("Tipo de Contrato Suministros"
# / "... Obras" / "... Servicios"), verificado en los documentos reales de
# este corpus (todos "Suministros", CONTEXTO.md sección 26) -- no hace falta
# adivinar la palabra por CPV ni por el objeto del contrato.
_TIPO_CONTRATO_RE = re.compile(r"Tipo de Contrato\s+(\S+)", re.IGNORECASE)
# "Objeto del Contrato: <texto, a veces partido en varias líneas>\nDescripción"
# — la etiqueta "Descripción" que sigue siempre repite el mismo texto sin la
# etiqueta, así que sirve de límite fiable de dónde termina el objeto.
# Sesión 2026-09-16 (noche): hay anuncios sin esa línea "Descripción" (el
# objeto va seguido directamente de "Valor estimado del contrato",
# `6.21/28510.0040` y `6.15/28510.0081`); el objeto capturado llegaba hasta
# "Descripción de Programas de Financiación", media página después, y no
# cabía en `expedientes.nombre_proyecto`, así que la extracción entera
# fallaba. El objeto termina también en la siguiente etiqueta fija del
# formulario.
_OBJETO_CONTRATO_RE = re.compile(
    r"Objeto del Contrato:\s*(.+?)\s*\n(?:Descripci[oó]n|Valor estimado del contrato|"
    r"Presupuesto base de licitaci[oó]n|Clasificaci[oó]n CPV|Tipo de Contrato)",
    re.DOTALL,
)
# Sesión de identidad de lote (CONTEXTO.md sección 27): el "Anuncio de
# adjudicación" (familia PCSP) trae este campo estructurado incluso cuando
# el expediente no tiene ninguna Propuesta LC.27 ni Resolución de la que
# sacar el bloque narrativo por lote (caso real: 6.23/28510.0139, "2 lotes"
# en el título y "Nº de Lotes: 2" aquí, sin ningún documento que declare
# baja/importe por lote) -- es la única fuente de "cuántos lotes declara la
# licitación" para ese caso.
_NUMERO_LOTES_RE = re.compile(r"N[ºo]\s*de\s+Lotes:\s*(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class CampoAnclado:
    valor: str
    pagina: int
    fragmento: str


@dataclass(frozen=True)
class CamposAnuncioPcsp:
    numero_expediente: Optional[CampoAnclado] = None
    codigo_matriz: Optional[CampoAnclado] = None
    # `importe_licitacion`/`importe_adjudicacion`/`adjudicatario` pueden
    # llevar además `app.extraccion.invalidado.INVALIDADO` (nunca lo pone
    # esta función -- solo `app.extraccion.lotes_pcsp.
    # extraer_campos_pcsp_para_expediente`, cuando el documento es
    # multi-lote y no se pudo atribuir el bloque propio de este
    # expediente): "encontrado pero no fiable", distinto de `None` ("no
    # encontrado"). El resto de campos de este documento son genuinamente
    # del documento entero, sin ambigüedad de lote que resolver.
    importe_licitacion: Optional[CampoAnclado] = None
    importe_adjudicacion: Optional[CampoAnclado] = None
    adjudicatario: Optional[CampoAnclado] = None
    objeto_contrato: Optional[CampoAnclado] = None
    tipo_contrato: Optional[CampoAnclado] = None
    numero_lotes: Optional[CampoAnclado] = None


def _buscar_en_paginas(paginas: list[PaginaTexto], patron: re.Pattern) -> Optional[CampoAnclado]:
    for pagina in paginas:
        m = patron.search(pagina.texto)
        if m:
            return CampoAnclado(valor=m.group(1).strip(), pagina=pagina.numero, fragmento=m.group(0).strip())
    return None


def _buscar_objeto(paginas: list[PaginaTexto]) -> Optional[CampoAnclado]:
    campo = _buscar_en_paginas(paginas, _OBJETO_CONTRATO_RE)
    if campo is None:
        return None
    # El objeto puede venir partido en varias líneas de PDF (ancho de
    # columna, no puntuación) — colapsar a una sola línea como el resto de
    # texto libre normalizado (CONTEXTO.md sección 8).
    return CampoAnclado(valor=re.sub(r"\s+", " ", campo.valor), pagina=campo.pagina, fragmento=campo.fragmento)


def extraer_campos_anuncio_pcsp(paginas: list[PaginaTexto]) -> CamposAnuncioPcsp:
    codigo_matriz = _buscar_en_paginas(paginas, _MATRIZ_RE) or _buscar_en_paginas(paginas, _MATRIZ_ALTERNATIVA_RE)
    return CamposAnuncioPcsp(
        numero_expediente=_buscar_en_paginas(paginas, _NUMERO_EXPEDIENTE_RE),
        codigo_matriz=codigo_matriz,
        importe_licitacion=_buscar_en_paginas(paginas, _IMPORTE_LICITACION_RE),
        importe_adjudicacion=_buscar_en_paginas(paginas, _IMPORTE_ADJUDICACION_RE),
        adjudicatario=_buscar_en_paginas(paginas, _ADJUDICATARIO_RE),
        objeto_contrato=_buscar_objeto(paginas),
        tipo_contrato=_buscar_en_paginas(paginas, _TIPO_CONTRATO_RE),
        numero_lotes=_buscar_en_paginas(paginas, _NUMERO_LOTES_RE),
    )


def importe_como_decimal(campo):
    """El modelo (aquí, el regex) devuelve el literal; esta es la única
    frontera donde se normaliza a Decimal (CONTEXTO.md sección 8).

    `campo` puede ser `None` (no encontrado), `INVALIDADO`
    (`app.extraccion.invalidado` -- encontrado pero no atribuible, ver
    docstring de `CamposAnuncioPcsp`) o un `CampoAnclado` real; los dos
    primeros pasan tal cual, sin normalizar nada, para que el llamador siga
    distinguiéndolos.

    Bloque 3, sesión 2026-09-10: un literal encontrado por la etiqueta fija
    pero que no se puede parsear como importe (p.ej. `parsear_numero_es`
    rechazando una agrupación de miles inválida, mismo arreglo de esta
    sesión) degrada a `INVALIDADO`, nunca deja que `ValueError` escape --
    esta función se llama sin try/except alrededor
    (`app.extraccion.orquestador`, bloque "Nº Lote: NNN"), y CONTEXTO.md
    sección 12 exige que un valor no interpretable vaya a revisión, nunca
    tumbe el expediente entero. Hallazgo real: expediente `6.20/28510.0062`,
    literal `'1.10'`, reproceso completo del bloque 5."""
    if campo is None or campo is INVALIDADO:
        return campo
    try:
        return parsear_importe_es(campo.valor)
    except ValueError:
        return INVALIDADO
