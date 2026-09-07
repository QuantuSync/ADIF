"""Campos de etiqueta fija de la Propuesta LC.27 — hermano de
`app.extraccion.campos_pcsp` para la otra plantilla con etiquetas fijas del
corpus (CONTEXTO.md sección 3: "formulario estándar con etiquetas fijas" /
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

**Adjudicatario añadido en la sesión de descubrimiento inverso, bloque 1**
(`docs/descubrimiento-inverso-matriz-pedidos.md` sección 7, "límite real, no
arreglado en esta sesión"): dos de las tres matrices de carril
(`6.23/28510.0102`, `6.25/28510.0016`) declaran su adjudicación solo en
Propuesta LC.27, sin ningún Anuncio PCSP en el expediente — sin este
extractor, el descubrimiento inverso nunca tiene adjudicatario con el que
acotar su búsqueda y se queda señalando el aviso para siempre. Verificado
contra los 21 documentos `propuesta_lc27` reales del corpus (los de camino
de lote único, sin ningún "LOTE N" en el texto — los multi-lote ya cubrían
esto con `app.extraccion.lotes._ADJUDICATARIO_RE`): misma redacción base "a
la empresa <nombre>, con NIF/CIF: <código>" en 9 de 10, y una variante real
sin "con" (`6.23/28510.0102`: "a la empresa ARCELORMITTAL ESPAÑA, S.A.–
NIF:", guion en vez de la palabra "con") que la regex de `lotes.py` no
cubría. Misma función sirve también para `resolucion_adjudicacion`
(verificado contra `6.24/28510.0185` y `6.26/28510.0016`, camino de lote
único: idéntica redacción "a la empresa: <nombre>, con NIF: <código>") — el
orquestador ya trata ambas plantillas en la misma rama por declarar los
mismos hechos (CONTEXTO.md sección 17).
"""
from __future__ import annotations

import re
from typing import Optional

from app.extraccion.campos_pcsp import CODIGO_EXPEDIENTE_RE, CampoAnclado
from app.extraccion.texto import PaginaTexto

# Bug real (encargo de esta sesión, punto 5): la versión original exigía
# `\s*\n\s*` justo entre la etiqueta y el número — solo espacios y como
# mucho un salto de línea, nada más. Un documento multi-lote (6.25/28510.0027)
# mete la cabecera de una tabla ("BASE IMPONIBLE IVA: (21%) TOTAL CON IVA")
# ahí en medio y la regex no encontraba nada. `[^\d]{0,120}` salta cualquier
# texto no numérico en medio — incluidos saltos de línea, que el caso de un
# solo lote sí necesita cruzar ("licitación:\n138.000,00 €") — hasta el
# primer dígito, sea el importe real o no.
#
# Documentos multi-lote no usan este valor de todos modos (CONTEXTO.md, punto
# 1 del encargo: el importe de licitación por lote sale de
# `app.extraccion.lotes`, que lee la tabla "LOTE N <importe> €" directamente
# con su propio patrón anclado a inicio de línea, y el del expediente se
# suma a partir de esos) — esta regex solo importa ya para el camino de un
# único lote, donde no hay cabecera de tabla de por medio en el corpus
# visto, así que no hace falta que `[^\d]` esquive el "(21%)" del multi-lote.
_IMPORTE_LICITACION_RE = re.compile(
    r"Presupuesto de licitaci[oó]n:[^\d]{0,120}([\d.,]+)\s*€", re.IGNORECASE
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
# El bloque "IDENTIFICACIÓN DEL DOCUMENTO" de la página de firmas repite el
# objeto sin el reflow a dos columnas de la portada, tanto en la Propuesta
# LC.27 ("PROPUESTA DE ADJUDICACIÓN DEL CONTRATO DE <objeto> EXPEDIENTE...")
# como en la Resolución (plantilla L9_AF.01-FE, CONTEXTO.md sección 17: misma
# estructura de firma, "RESOLUCIÓN DE ADJUDICACIÓN DEL CONTRATO DE..."). Corta
# en el primer " EXPEDIENTE" (con espacio o salto de línea delante, nunca a
# mitad de palabra como en "EXPEDIENTE PRINCIPAL").
_OBJETO_CONTRATO_RE = re.compile(
    r"(?:PROPUESTA|RESOLUCI[OÓ]N) DE ADJUDICACI[OÓ]N DEL CONTRATO DE\s+(.+?)\s+EXPEDIENTE",
    re.IGNORECASE | re.DOTALL,
)
# Mismo ancla que `app.extraccion.lotes._ADJUDICATARIO_RE` ("a la
# empresa/empresas... con NIF/CIF"), generalizada con el separador
# `[\s,–-]*(?:con\s+)?` en vez de exigir literalmente "con": cubre
# también la variante real de `6.23/28510.0102` ("...S.A.– NIF:", guion en
# vez de "con") sin dejar de casar el resto del corpus ("con NIF:"/"con
# CIF:"). `.+?` perezoso más DOTALL para cruzar el salto de línea real entre
# el nombre y el NIF/CIF (`6.23/28510.0102`: "...S.A.– NIF:\nA81046856").
_ADJUDICATARIO_RE = re.compile(
    r"a\s+la[s]?\s+empresa[s]?:?\s*(.+?)[\s,–-]*(?:con\s+)?(?:NIF|CIF):?",
    re.IGNORECASE | re.DOTALL,
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


def extraer_objeto_contrato_lc27(paginas: list[PaginaTexto]) -> Optional[CampoAnclado]:
    campo = _buscar_en_paginas(paginas, _OBJETO_CONTRATO_RE)
    if campo is None:
        return None
    return CampoAnclado(valor=re.sub(r"\s+", " ", campo.valor), pagina=campo.pagina, fragmento=campo.fragmento)


def extraer_adjudicatario_lc27(paginas: list[PaginaTexto]) -> Optional[CampoAnclado]:
    campo = _buscar_en_paginas(paginas, _ADJUDICATARIO_RE)
    if campo is None:
        return None
    return CampoAnclado(valor=re.sub(r"\s+", " ", campo.valor).strip(), pagina=campo.pagina, fragmento=campo.fragmento)
