"""Campos de etiqueta fija de la Propuesta LC.27 — hermano de
`app.extraccion.campos_pcsp` para la otra plantilla con etiquetas fijas del
corpus (CLAUDE.md sección 3: "formulario estándar con etiquetas fijas" /
"plantilla propia de ADIF").

Se añade porque el caso de aceptación de esta sesión (expediente
6.24/28510.0008: 138.000 € en licitación y en adjudicación, baja 54,00 %) no
tiene Anuncio PCSP en el corpus fijo de prueba — el importe y la baja viven
solo en la Propuesta LC.27. Sin este extractor, el caso de precios unitarios
solo se podría probar con números escritos a mano en el test, no con datos
sacados del PDF real.

Se extraen solo los campos que hacen falta para ese caso: importe de
licitación, importe adjudicado y número de expediente. Adjudicatario y
matriz de LC.27 quedan fuera de alcance de esta sesión.
"""
from __future__ import annotations

import re
from typing import Optional

from app.extraccion.campos_pcsp import CODIGO_EXPEDIENTE_RE, CampoAnclado
from app.extraccion.texto import PaginaTexto

_IMPORTE_LICITACION_RE = re.compile(
    r"Presupuesto de licitaci[oó]n:\s*\n\s*([\d.,]+)\s*€", re.IGNORECASE
)
# "Base imponible" aparece dos veces en la Propuesta: como cabecera de la
# tabla de licitación ("(A) Base Imponible IVA (21%) Total con IVA", sin
# número justo detrás) y como la línea de importe de adjudicación ("Base
# imponible 138.000,00 €" o "- Base imponible ... 1.000.000,00 €"). Solo la
# segunda casa: la cabecera nunca tiene un € inmediatamente después del hueco
# de separadores/puntos de relleno.
_IMPORTE_ADJUDICACION_RE = re.compile(r"[Bb]ase [Ii]mponible[^\d\n]{0,100}([\d.,]+)\s*€")
_NUMERO_EXPEDIENTE_RE = re.compile(
    r"EXPEDIENTE N[oº]:?\s*(" + CODIGO_EXPEDIENTE_RE.pattern + r")", re.IGNORECASE
)


def _buscar_en_paginas(paginas: list[PaginaTexto], patron: re.Pattern) -> Optional[CampoAnclado]:
    for pagina in paginas:
        m = patron.search(pagina.texto)
        if m:
            return CampoAnclado(valor=m.group(1).strip(), pagina=pagina.numero, fragmento=m.group(0).strip())
    return None


def extraer_importe_licitacion_lc27(paginas: list[PaginaTexto]) -> Optional[CampoAnclado]:
    return _buscar_en_paginas(paginas, _IMPORTE_LICITACION_RE)


def extraer_importe_adjudicacion_lc27(paginas: list[PaginaTexto]) -> Optional[CampoAnclado]:
    return _buscar_en_paginas(paginas, _IMPORTE_ADJUDICACION_RE)


def extraer_numero_expediente_lc27(paginas: list[PaginaTexto]) -> Optional[CampoAnclado]:
    return _buscar_en_paginas(paginas, _NUMERO_EXPEDIENTE_RE)
