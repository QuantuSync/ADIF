"""Etapas 3 y 4 de la sesión (CLAUDE.md sección 4): la baja es un dato
declarado en texto, nunca una tabla que calcular. Se busca en la Propuesta
LC.27, en la Resolución de Adjudicación y en el contrato — las tres plantillas
declaran la misma frase con redacciones distintas:

  - LC.27 (individual): "con una baja económica del 54,00 % a precios
    unitarios licitados"
  - LC.27 (UTE): "con una baja del 0,50% al conjunto de precios unitarios
    de los artículos que componen el objeto del contrato"
  - Resolución: "con una baja del 4,50% aplicable al conjunto de precios
    unitarios de los artículos que componen el objeto del contrato"
  - Contrato: "La baja económica ofertada del 54,00% será aplicable a
    todos los precios unitarios licitados."
  - Propuesta de Dirección Técnica (L9_CM.32-FE, docs/analisis-corpus.md
    hallazgo 4): "con una baja del 20% a todos los precios unitarios"

Todas comparten la forma "baja [económica] [ofertada] del N %  ... precios
unitarios": un único patrón laxo basta para las cuatro, sin necesitar una
regla por plantilla — verificado contra los dos documentos reales de
Dirección Técnica sin tener que tocar `_BAJA_RE`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.extraccion.normalizacion import parsear_porcentaje_es
from app.extraccion.texto import PaginaTexto
from app.models import TipoDocumento

# La distancia entre "% " y "precios unitarios" varía (de un espacio a una
# subordinada entera) pero nunca cruza a la frase siguiente en los ejemplos
# vistos; 160 caracteres da margen sin arriesgarse a saltar de párrafo.
_BAJA_RE = re.compile(
    r"baja(?:\s+econ[oó]mica)?(?:\s+ofertada)?\s+del\s+([\d.,]+)\s*%[^.]{0,160}?precios unitarios",
    re.IGNORECASE | re.DOTALL,
)

# Redacciones alternativas de la misma baja (sesión de expedientes sin
# publicar, CLAUDE.md sección 22), verificadas contra un caso real que no
# viene del corpus de PDFs de este proyecto sino de otra fuente: una etiqueta
# de campo, no una frase en prosa, y sin la subordinada "precios unitarios"
# que exige `_BAJA_RE`. Solo se intenta si `_BAJA_RE` no encontró nada en
# ningún documento del expediente (ver `extraer_baja_declarada`), nunca antes
# — es un patrón más laxo y solo debe ganar cuando el estricto no sirve.
#
# El caso que dispara esto: "% de baja:    12,5" — el símbolo de porcentaje
# va pegado a la etiqueta, no al número ("% de baja", no "baja del 12,5%").
# Esa variante concreta ("de baja") exige el "%" delante a propósito: sin
# esa ancla, "de baja" también aparece en cláusulas laborales de boilerplate
# ajenas a la baja del expediente ("el trabajador que se encuentre de
# baja..."), y el símbolo de porcentaje pegado a la etiqueta es la señal que
# distingue el campo de adjudicación de esa prosa. Las otras variantes
# ("% baja adjudicado", "% total de baja", "baja ofertada", "porcentaje de
# baja") son frases lo bastante específicas para no necesitar esa misma
# ancla.
_BAJA_ETIQUETA_RE = re.compile(
    r"(?:"
    r"%\s*de\s+baja"
    r"|%?\s*porcentaje\s+de\s+baja"
    r"|%?\s*total\s+de\s+baja"
    r"|%?\s*baja\s+adjudicad[oa]"
    r"|%?\s*baja\s+ofertada"
    r")\b[:=\s]*([\d]+(?:[.,]\d+)?)\s*%?",
    re.IGNORECASE,
)

# Prioridad al elegir entre varios documentos del mismo hecho para el mismo
# expediente/lote (CLAUDE.md sección 17: "preferir la Resolución cuando
# existan las dos" porque es el acto posterior y definitivo).
# `propuesta_dt` (docs/analisis-corpus.md hallazgo 4) es al mismo tipo de
# hecho que propuesta_lc27 — una propuesta previa a la Resolución, nunca
# vista junto a una LC.27 en el mismo expediente — misma prioridad.
_PRIORIDAD_BAJA = {
    TipoDocumento.resolucion_adjudicacion: 0,
    TipoDocumento.contrato: 1,
    TipoDocumento.propuesta_lc27: 2,
    TipoDocumento.propuesta_dt: 2,
}


@dataclass(frozen=True)
class BajaDeclarada:
    baja: Decimal  # fracción, p.ej. Decimal("0.5400") para 54,00 %
    pagina: int
    fragmento: str
    tipo_documento: Optional[TipoDocumento] = None


def extraer_baja_declarada(
    paginas: list[PaginaTexto], tipo_documento: Optional[TipoDocumento] = None
) -> Optional[BajaDeclarada]:
    """Primera aparición, en orden de página, de la frase de baja declarada.
    No busca todas las apariciones: en los documentos vistos la baja se
    declara una sola vez por lote/expediente y las siguientes menciones (si
    las hay) repiten el mismo valor."""
    for pagina in paginas:
        m = _BAJA_RE.search(pagina.texto)
        if m:
            return BajaDeclarada(
                baja=parsear_porcentaje_es(m.group(1)),
                pagina=pagina.numero,
                fragmento=m.group(0).strip(),
                tipo_documento=tipo_documento,
            )
    # Ningún documento trajo la frase estricta "baja ... del N% ... precios
    # unitarios": antes de rendirse, se prueban las etiquetas de campo
    # alternativas (ver docstring de `_BAJA_ETIQUETA_RE`) — más laxas a
    # propósito, por eso solo se intentan como segunda pasada, nunca antes.
    for pagina in paginas:
        m = _BAJA_ETIQUETA_RE.search(pagina.texto)
        if m:
            return BajaDeclarada(
                baja=parsear_porcentaje_es(m.group(1)),
                pagina=pagina.numero,
                fragmento=m.group(0).strip(),
                tipo_documento=tipo_documento,
            )
    return None


def elegir_baja_preferida(candidatas: list[BajaDeclarada]) -> Optional[BajaDeclarada]:
    """Cuando el mismo expediente trae baja declarada en más de un documento
    (p.ej. Propuesta y Resolución, CLAUDE.md sección 17), se queda con la del
    documento de mayor prioridad. No decide si los valores discrepan entre
    sí — eso es una incoherencia y va a la cola de revisión (sección 12), no
    algo que este selector deba resolver en silencio."""
    if not candidatas:
        return None
    return min(
        candidatas,
        key=lambda c: _PRIORIDAD_BAJA.get(c.tipo_documento, len(_PRIORIDAD_BAJA)),
    )
