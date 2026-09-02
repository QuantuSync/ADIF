"""Etapa 2, camino multi-lote (CLAUDE.md sección 2 y encargo de esta
sesión): un expediente puede subdividirse en varios lotes, cada uno con su
propia baja, su propio presupuesto y su propio adjudicatario — verificado
contra el expediente real 6.25/28510.0027 (Resolución de Adjudicación,
plantilla L9_AF.01-FE, LOTE 1 al 7,13 % y LOTE 3 al 1,18 %, presupuestos
distintos). `app.extraccion.baja` sigue siendo el camino de un solo lote
(ningún "LOTE N" en el texto); este módulo es el que reconoce la estructura
multi-lote cuando existe, y no toca nada si no la encuentra.

La Resolución declara cada lote en un bloque autocontenido dentro de
"RESUELVE:":

  "- En el LOTE 1. BASE EN LAS MATAS. EXPEDIENTE Nº 6.25/28510.0099, a la
  empresa: ÁRIDOS DE VILLACASTÍN, S.A., con NIF: A83964817, con una baja del
  7,13% aplicable al conjunto de precios unitarios [...] con un importe a
  adjudicar de: - Base imponible ................ 593.375,00 €"

El ancla es la frase literal "En el LOTE N", no cualquier mención suelta de
"LOTE N" — esa palabra también aparece en la cabecera "DATOS DE LA
LICITACIÓN" y en la tabla de presupuesto de licitación, sin baja cerca. Un
`.*?` sin acotar entre "En el LOTE N" y sus datos podría saltar por encima
del bloque de otro lote; se acota con un lookahead negativo que nunca cruza
la siguiente ocurrencia de "En el LOTE".

El importe de licitación por lote no está en el bloque RESUELVE (ese trae el
importe *adjudicado*): sale de la tabla "Presupuesto de licitación: BASE
IMPONIBLE IVA...", con una fila por lote ("LOTE 1 593.375,00 € ..."). Esa
fila empieza la línea con "LOTE N", a diferencia de las menciones de "En el
LOTE N" del RESUELVE — son patrones disjuntos por construcción, no hace
falta desambiguarlos entre sí.

Nota sobre LC.27 multi-lote: no se ha encontrado en el corpus completo (45
expedientes) ninguna Propuesta LC.27 con más de un lote — solo la Resolución
del expediente 6.25/28510.0027 es multi-lote. El mismo patrón ("En el LOTE
N" + baja + importe) se aplica también a LC.27 por si alguna vez aparece uno
así, pero **eso está sin verificar contra un documento real** (CLAUDE.md
sección 16): si aparece una LC.27 multi-lote con una redacción distinta,
este es el sitio a revisar.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.extraccion.normalizacion import parsear_importe_es, parsear_porcentaje_es
from app.extraccion.texto import PaginaTexto

# Icons entre "En el LOTE N" y sus datos: nunca cruza la siguiente aparición
# de "En el LOTE", así que dos lotes con el mismo texto (baja, importe) no
# se pueden confundir entre sí aunque el bloque de alguno esté incompleto.
_NO_CRUZAR_LOTE = r"(?:(?!En el LOTE).)*?"

_BLOQUE_LOTE_RE = re.compile(
    r"En el LOTE\s*(\d+)\b"
    + _NO_CRUZAR_LOTE
    + r"con una baja(?:\s+econ[oó]mica)?(?:\s+ofertada)?\s+del\s+([\d.,]+)\s*%"
    + _NO_CRUZAR_LOTE
    + r"Base imponible[^\d\n]{0,40}([\d.,]+)\s*€",
    re.IGNORECASE | re.DOTALL,
)

# El adjudicatario es un dato secundario (el Lote lo admite pero no lo exige,
# CLAUDE.md sección 7): se busca por separado dentro del propio bloque ya
# capturado, para que una redacción distinta de "a la empresa: X, con NIF:
# Y" no impida capturar la baja y el importe, que son los datos que sí exige
# la sección 4 ("se extrae, no se calcula").
_ADJUDICATARIO_RE = re.compile(r"a la empresa:\s*(.+?),?\s*con\s+NIF", re.IGNORECASE | re.DOTALL)

# Fila de la tabla "Presupuesto de licitación: BASE IMPONIBLE IVA...": la
# línea empieza literalmente por "LOTE N", a diferencia de "En el LOTE N"
# del bloque RESUELVE — no hace falta desambiguar los dos patrones entre sí.
_TABLA_LICITACION_LOTE_RE = re.compile(r"^LOTE\s*(\d+)\s+([\d.,]+)\s*€", re.MULTILINE)


@dataclass(frozen=True)
class LoteDeclarado:
    identificador: str
    baja: Optional[Decimal]
    importe_licitacion: Optional[Decimal]
    importe_adjudicacion: Optional[Decimal]
    adjudicatario: Optional[str]
    pagina: int
    fragmento: str


def _importes_licitacion_por_lote(paginas: list[PaginaTexto]) -> dict[str, Decimal]:
    importes: dict[str, Decimal] = {}
    for pagina in paginas:
        for m in _TABLA_LICITACION_LOTE_RE.finditer(pagina.texto):
            identificador = m.group(1)
            if identificador not in importes:  # primera aparición gana, igual que el resto de la cascada
                importes[identificador] = parsear_importe_es(m.group(2))
    return importes


def extraer_lotes_declarados(paginas: list[PaginaTexto]) -> list[LoteDeclarado]:
    """Lista vacía si el documento no declara ningún lote por su nombre
    ("En el LOTE N") — el llamador (orquestador) cae entonces al camino de
    un único lote implícito (CLAUDE.md, encargo de esta sesión, punto 1:
    "Cuando el documento no tenga lotes, un único lote implícito")."""
    importes_licitacion = _importes_licitacion_por_lote(paginas)

    declarados: list[LoteDeclarado] = []
    identificadores_vistos: set[str] = set()
    for pagina in paginas:
        for m in _BLOQUE_LOTE_RE.finditer(pagina.texto):
            identificador = m.group(1)
            if identificador in identificadores_vistos:
                continue  # el mismo bloque no se repite dentro de un documento
            identificadores_vistos.add(identificador)

            adjudicatario_match = _ADJUDICATARIO_RE.search(m.group(0))
            adjudicatario = (
                re.sub(r"\s+", " ", adjudicatario_match.group(1)).strip() if adjudicatario_match else None
            )

            declarados.append(
                LoteDeclarado(
                    identificador=identificador,
                    baja=parsear_porcentaje_es(m.group(2)),
                    importe_licitacion=importes_licitacion.get(identificador),
                    importe_adjudicacion=parsear_importe_es(m.group(3)),
                    adjudicatario=adjudicatario,
                    pagina=pagina.numero,
                    fragmento=re.sub(r"\s+", " ", m.group(0)).strip(),
                )
            )
    return declarados
