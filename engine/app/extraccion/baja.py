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

Todas comparten la forma "baja [económica] [ofertada] del N %  ... precios
unitarios": un único patrón laxo basta para las tres, sin necesitar una regla
por plantilla.
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

# Prioridad al elegir entre varios documentos del mismo hecho para el mismo
# expediente/lote (CLAUDE.md sección 17: "preferir la Resolución cuando
# existan las dos" porque es el acto posterior y definitivo).
_PRIORIDAD_BAJA = {
    TipoDocumento.resolucion_adjudicacion: 0,
    TipoDocumento.contrato: 1,
    TipoDocumento.propuesta_lc27: 2,
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
