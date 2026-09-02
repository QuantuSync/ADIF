"""Etapa 2 de la cascada de extracción (CLAUDE.md sección 5): campos de
etiqueta fija de la familia de formularios PCSP (Anuncio de adjudicación,
Anuncio de formalización de contrato, Documento de Pliegos — ver docstring de
`app.extraccion.clasificador`). Todo lo que sea de esta familia se extrae por
posición de etiqueta, sin tablas y sin modelo.

Cada valor se ancla a la página y al fragmento de texto de los que salió
(CLAUDE.md sección 9.10): un campo ausente es `None` en el campo y no
aparece en `campos`, nunca un valor inventado.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

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
_IMPORTE_LICITACION_RE = re.compile(
    r"Presupuesto base de licitaci[oó]n.*?Importe \(sin impuestos\)\s*([\d.,]+)\s*EUR",
    re.IGNORECASE | re.DOTALL,
)
_IMPORTE_ADJUDICACION_RE = re.compile(
    r"Importes? de Adjudicaci[oó]n.*?Importe total ofertado \(sin impuestos\)\s*([\d.,]+)\s*EUR",
    re.IGNORECASE | re.DOTALL,
)
_ADJUDICATARIO_RE = re.compile(r"^Adjudicatario\s*$\n([^\n]+)", re.MULTILINE)
# "Objeto del Contrato: <texto, a veces partido en varias líneas>\nDescripción"
# — la etiqueta "Descripción" que sigue siempre repite el mismo texto sin la
# etiqueta, así que sirve de límite fiable de dónde termina el objeto.
_OBJETO_CONTRATO_RE = re.compile(
    r"Objeto del Contrato:\s*(.+?)\s*\nDescripci[oó]n", re.DOTALL
)


@dataclass(frozen=True)
class CampoAnclado:
    valor: str
    pagina: int
    fragmento: str


@dataclass(frozen=True)
class CamposAnuncioPcsp:
    numero_expediente: Optional[CampoAnclado] = None
    codigo_matriz: Optional[CampoAnclado] = None
    importe_licitacion: Optional[CampoAnclado] = None
    importe_adjudicacion: Optional[CampoAnclado] = None
    adjudicatario: Optional[CampoAnclado] = None
    objeto_contrato: Optional[CampoAnclado] = None


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
    # texto libre normalizado (CLAUDE.md sección 8).
    return CampoAnclado(valor=re.sub(r"\s+", " ", campo.valor), pagina=campo.pagina, fragmento=campo.fragmento)


def extraer_campos_anuncio_pcsp(paginas: list[PaginaTexto]) -> CamposAnuncioPcsp:
    return CamposAnuncioPcsp(
        numero_expediente=_buscar_en_paginas(paginas, _NUMERO_EXPEDIENTE_RE),
        codigo_matriz=_buscar_en_paginas(paginas, _MATRIZ_RE),
        importe_licitacion=_buscar_en_paginas(paginas, _IMPORTE_LICITACION_RE),
        importe_adjudicacion=_buscar_en_paginas(paginas, _IMPORTE_ADJUDICACION_RE),
        adjudicatario=_buscar_en_paginas(paginas, _ADJUDICATARIO_RE),
        objeto_contrato=_buscar_objeto(paginas),
    )


def importe_como_decimal(campo: Optional[CampoAnclado]) -> Optional[Decimal]:
    """El modelo (aquí, el regex) devuelve el literal; esta es la única
    frontera donde se normaliza a Decimal (CLAUDE.md sección 8)."""
    if campo is None:
        return None
    return parsear_importe_es(campo.valor)
