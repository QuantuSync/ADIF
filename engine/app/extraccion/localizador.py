"""Etapa 3 de la cascada de extracción (CLAUDE.md sección 5): localizar,
dentro de un documento cualquiera, las páginas que traen un cuadro de precios
unitarios — nunca por tipo de documento ni por nombre de fichero. Los
`*_ANEJO_N.pdf` del corpus son en realidad el Pliego de Prescripciones
Técnicas completo (o, en el corpus real, un pliego que a su vez concatena un
segundo Anejo de "Criterios técnicos"): el cuadro de precios es una sección
interna que hay que encontrar por contenido de página.

Dos señales, medidas sobre los fixtures fijos del proyecto:

1. **Densidad numérica.** Fracción de caracteres no-espacio que son dígitos.
   Un cuadro de precios (códigos, matrículas, cantidades, importes) satura de
   dígitos una página de forma que ningún párrafo de pliego alcanza — en los
   dos anejos de fixture, la página del cuadro pasa de 0,10 mientras que el
   texto normal del pliego se queda por debajo de 0,05.
2. **Grupos de marcadores de cabecera.** Presencia de al menos dos categorías
   distintas entre código de precio, precio, cantidad/unidad, matrícula y
   descripción. Ni matrícula ni ningún marcador aislado basta por sí solo:
   la matrícula falta por completo en algunas tablas del corpus (CLAUDE.md
   sección 3, "presente solo en ~66% de las líneas"), y una sola palabra
   suelta ("precio") aparece también en párrafos que no son tabla.

Exigir las dos señales a la vez es lo que separa una página de cuadro de
precios real de un párrafo que solo menciona "precio" o "cantidad" de pasada:
medido contra los fixtures, un umbral de densidad de 0,04 combinado con dos
grupos de marcadores descarta 91,7% de las páginas del anejo de un solo
cuadro (11 de 12) y 88,5% del anejo con tres tablas de precios repartidas en
tres cabeceras distintas (23 de 26) — del mismo orden que el 83% medido sobre
el corpus completo en CLAUDE.md sección 3.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extraccion.texto import PaginaTexto, normalizar

UMBRAL_DENSIDAD_NUMERICA = Decimal("0.04")
MIN_GRUPOS_MARCADORES = 2

_GRUPOS_MARCADORES: dict[str, tuple[str, ...]] = {
    "codigo": ("codigo de precio", "codigo del precio", "codigo del elemento", "codigo"),
    "precio": ("precio unitario", "precio de referencia", "precio"),
    "cantidad_unidad": ("cantidad", "unidad de medida", "unidades"),
    "matricula": ("matricula",),
    "descripcion": ("descripcion",),
}


@dataclass(frozen=True)
class PaginaCandidata:
    numero: int
    densidad_numerica: Decimal
    grupos_marcadores: frozenset[str]


@dataclass(frozen=True)
class ResultadoLocalizacion:
    candidatas: list[PaginaCandidata]
    total_paginas: int

    @property
    def porcentaje_descartado(self) -> Decimal:
        if self.total_paginas == 0:
            return Decimal("0")
        descartadas = self.total_paginas - len(self.candidatas)
        return Decimal(descartadas) / Decimal(self.total_paginas)


def _densidad_numerica(texto: str) -> Decimal:
    no_espacio = [c for c in texto if not c.isspace()]
    if not no_espacio:
        return Decimal("0")
    digitos = sum(1 for c in no_espacio if c.isdigit())
    return Decimal(digitos) / Decimal(len(no_espacio))


def _grupos_presentes(texto_normalizado: str) -> frozenset[str]:
    return frozenset(
        grupo
        for grupo, alias in _GRUPOS_MARCADORES.items()
        if any(a in texto_normalizado for a in alias)
    )


def localizar_paginas_candidatas(paginas: list[PaginaTexto]) -> ResultadoLocalizacion:
    candidatas = []
    for pagina in paginas:
        densidad = _densidad_numerica(pagina.texto)
        if densidad < UMBRAL_DENSIDAD_NUMERICA:
            continue
        grupos = _grupos_presentes(normalizar(pagina.texto))
        if len(grupos) < MIN_GRUPOS_MARCADORES:
            continue
        candidatas.append(PaginaCandidata(pagina.numero, densidad, grupos))
    return ResultadoLocalizacion(candidatas=candidatas, total_paginas=len(paginas))
