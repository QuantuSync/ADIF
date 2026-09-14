"""Etapa 3 de la cascada de extracción (CONTEXTO.md sección 5): localizar,
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
   la matrícula falta por completo en algunas tablas del corpus (CONTEXTO.md
   sección 3, "presente solo en ~66% de las líneas"), y una sola palabra
   suelta ("precio") aparece también en párrafos que no son tabla.

Exigir las dos señales a la vez es lo que separa una página de cuadro de
precios real de un párrafo que solo menciona "precio" o "cantidad" de pasada:
medido contra los fixtures, un umbral de densidad de 0,04 combinado con dos
grupos de marcadores descarta 91,7% de las páginas del anejo de un solo
cuadro (11 de 12) y 88,5% del anejo con tres tablas de precios repartidas en
tres cabeceras distintas (23 de 26) — del mismo orden que el 83% medido sobre
el corpus completo en CONTEXTO.md sección 3.

Umbral bajado a 0,025 en la sesión de expedientes sin publicar (2026-09-03):
`6.24/28510.0187_ANEJO_1.pdf` página 11 tiene un cuadro de precios real (dos
líneas, códigos "P01"/"P02") en una página cuya densidad cae a 0,0253 —
diluida por un párrafo largo de prosa introductoria ("El cuadro de precios
unitarios del presente expediente...") que el resto de páginas de cuadro de
precios del corpus no trae. Medido sobre el corpus real completo antes de
bajar el umbral (nunca a ciegas): con 0,025 pasan a ser candidatas 233
páginas más de las 0,04 originales, de las cuales solo 15 (6,4%) traen una
tabla real — las otras 218 no cuestan nada más que un `find_tables()` que no
encuentra nada, porque `extraer_tablas_pagina` ya descarta sin datos
cualquier tabla sin fila reconocible. Beneficio medido, no solo el caso que
disparó el cambio: además de `6.24/28510.0187`, esto también recupera un
cuadro de precios real en `6.24/28510.0116_ANEJO_1.pdf` (páginas 18 y 22,
antes sin ninguna página candidata en todo el expediente).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from app.extraccion.normalizacion import normalizar_guiones
from app.extraccion.texto import PaginaTexto, normalizar

UMBRAL_DENSIDAD_NUMERICA = Decimal("0.025")
MIN_GRUPOS_MARCADORES = 2

# Bloque 5, cambios del cliente tras revisar el catálogo (sesión 2026-09-09):
# umbral aparte, mucho más exigente, solo para aceptar una página SIN
# ningún marcador de cabecera como continuación de la anterior (ver
# docstring de `localizar_paginas_candidatas`). `UMBRAL_DENSIDAD_NUMERICA`
# (0,025) es deliberadamente bajo para no perder una tabla real diluida por
# prosa -- vale para la detección normal, que además exige marcadores, pero
# solo no basta aquí. Medido contra los dos fixtures fijos del proyecto:
# la página de prosa que sigue al cuadro de precios de guantes (0,049) y las
# páginas de relleno entre los dos cuadros de traviesas (0,051-0,062) quedan
# muy por debajo de este umbral; las 42 páginas reales de continuación de
# `6.20/28510.0047_ANEJO_abd69efbdd39b552.pdf` (el caso real que motiva este
# arreglo) están en 0,38-0,47 -- ni siquiera cerca del límite.
UMBRAL_DENSIDAD_CONTINUACION = Decimal("0.20")

# Sesión 2026-09-14 (revisión del cliente sobre el Excel, pliegos
# `6.21/28510.0109_ANEJO_7bfc92005f43e68e.pdf` y `6.21/28510.0016_ANEJO_
# e40fc4e4546ec90b.pdf`): la densidad no es una señal fiable de "esta página
# continúa la tabla de la anterior". Una tabla de repuestos de aparatos de
# vía trae descripciones de 20-40 líneas de prosa técnica por fila -- sus
# páginas de continuación caen en 0,10-0,20 de densidad, por debajo de
# `UMBRAL_DENSIDAD_CONTINUACION`, y nunca se abrían: medido sobre el corpus
# real, 246 páginas con filas reales en 30 documentos (46 expedientes), 89
# de las 148 filas del anejo 588. Lo que sí distingue una página de
# continuación de la prosa que sigue a una tabla es que trae identificadores
# de FILA -- el código de precio o la matrícula de cada línea --, nunca
# presentes en un párrafo de pliego. Formas de `app.extraccion.tabla` /
# `app.catalogo` (código de precio con guion, "COD0001", "L01-T01", matrícula
# de 9 dígitos, también con puntos "643.910.630"), más el sufijo de variante
# en mayúscula verificado en esos mismos documentos ("P-39B", "P-41 A").
# Solo formas con separador o longitud fija: "P1"/"P01" sin guion también
# existen en el corpus, pero sueltos aparecen en prosa corriente ("tipo P o
# P1 de radio 1500") y no bastan como prueba de fila.
_IDENTIFICADOR_FILA_RE = re.compile(
    r"(?<![\w.\-])"
    r"(?:(?:P|PN|PA)-\s?\d{1,4}(?:\s?[A-Z](?![a-z]))?|(?i:COD)\d{4}|L\d{1,2}-T\d{1,2}|\d{9}|\d{3}\.\d{3}\.\d{3})"
    r"(?![\w\-]|[.,]\d)"
)

# Importe con coma y exactamente dos decimales, con o sin separador de miles
# ("4.292,05" o "1262,94", las dos formas reales -- `4.26/28510.0020_ANEJO_
# 8f2a33dd634a5454.pdf` usa la segunda), buscado dentro de una línea de
# texto, no anclado a una celda.
_IMPORTE_EN_LINEA_RE = re.compile(r"(?<![\d.,])(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}(?![\d])")

# Arranque de tabla sin ningún marcador de cabecera legible (misma sesión,
# `6.21/28510.0016_ANEJO_e40fc4e4546ec90b.pdf` p.13): la cabecera de la tabla
# está en una fuente sin mapa Unicode ("(cid:69)(cid:465)..." en vez de "Nº
# MATRÍCULA") y la página no trae ningún marcador de `_GRUPOS_MARCADORES`,
# así que ni se abría ni podía encadenar las cuatro páginas de continuación
# que la siguen (69 de los 78 materiales con matrícula del Lote 1 nunca se
# leían).
# Sin cabecera legible, la señal es el propio contenido: varias líneas que
# traen A LA VEZ un identificador de fila y un importe -- la forma de una fila
# de cuadro de precios, no de un párrafo. Tres, no una: una sola línea así
# puede ser una frase de pliego que cita un precio concreto.
MIN_FILAS_DATO_SIN_CABECERA = 3


def _identificadores_fila(texto: str) -> int:
    return len(_IDENTIFICADOR_FILA_RE.findall(normalizar_guiones(texto)))


def _lineas_con_fila_de_datos(texto: str) -> int:
    return sum(
        1
        for linea in normalizar_guiones(texto).splitlines()
        if _IDENTIFICADOR_FILA_RE.search(linea) and _IMPORTE_EN_LINEA_RE.search(linea)
    )

_GRUPOS_MARCADORES: dict[str, tuple[str, ...]] = {
    "codigo": (
        "codigo de precio",
        "codigo del precio",
        "codigo del elemento",
        "codificacion del precio",
        "codigo",
    ),
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
    # Bloque 5, cambios del cliente tras revisar el catálogo (sesión
    # 2026-09-09): `True` cuando esta página entró solo por continuar a la
    # anterior (ver docstring de `localizar_paginas_candidatas`), nunca
    # porque ella misma repita ningún marcador de cabecera -- `grupos_
    # marcadores` viene vacío en ese caso, no es un error.
    continuacion: bool = False
    # Sesión 2026-09-14: `True` cuando la página entró sin marcadores de
    # cabecera y sin continuar a ninguna candidata, solo por traer
    # `MIN_FILAS_DATO_SIN_CABECERA` o más líneas con forma de fila de cuadro
    # de precios (ver `_lineas_con_fila_de_datos`) -- el arranque de una
    # tabla cuya cabecera no se puede leer.
    sin_cabecera_legible: bool = False


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
    """Bloque 5, cambios del cliente tras revisar el catálogo (sesión
    2026-09-09): dato verificado por el cliente contra la Plataforma --
    "hay tablas sin encabezado que sí traen matrícula y cantidad", y en
    efecto no pasaban esta etapa. Confirmado contra el PDF real
    (`6.20/28510.0047_ANEJO_abd69efbdd39b552.pdf`, cuadro de precios por
    matrícula de 61 páginas): la cabecera solo se imprime una vez, en la
    primera página del cuadro; las 42 páginas de continuación siguientes
    no repiten ninguna palabra de cabecera ("matrícula", "precio",
    "cantidad"...) -- 0 de los 5 grupos de marcadores, aunque su densidad
    numérica sea altísima (0,38-0,47, muy por encima del umbral) porque son
    fila tras fila de matrícula/descripción/precio. Sin este arreglo, esas
    42 páginas nunca llegaban ni a `extraer_tablas_pagina`: no es que la
    tabla se descartara después por no tener cabecera reconocible, es que
    la página entera nunca se abría.

    Una página que NO trae marcadores propios se acepta igual, como
    continuación, cuando la página INMEDIATAMENTE anterior sí es candidata
    (por marcadores propios o por ser ella misma una continuación ya
    aceptada) Y su propia densidad numérica supera `UMBRAL_DENSIDAD_
    CONTINUACION` -- un umbral aparte y mucho más exigente que el de la
    detección normal, nunca a ciegas: verificado contra los fixtures fijos
    del proyecto que la prosa/relleno entre tablas reales (0,05-0,10) queda
    muy por debajo, mientras que las páginas de continuación reales
    (0,38-0,47) ni se acercan al límite. La cadena se corta en cuanto una
    página no llega a ese umbral, así que nunca se cuela en páginas
    posteriores no relacionadas. `etapa 5` (`app.extraccion.mapeo_cabecera`
    vía `app.extraccion.pipeline_anejo`) es quien decide qué mapeo de
    columnas usar para una tabla sin cabecera propia -- esto solo decide
    que la página se ABRA.

    Sesión 2026-09-14: la continuación ya no depende solo de la densidad.
    Una página que continúa una tabla ya abierta se acepta también si trae
    al menos un identificador de fila (`_IDENTIFICADOR_FILA_RE`) -- una
    página de continuación con descripciones largas en prosa técnica tiene
    la densidad de un párrafo, no la de una tabla que empieza, y aun así es
    fila tras fila del mismo cuadro. Y una página sin marcadores que no
    continúa nada se acepta si trae `MIN_FILAS_DATO_SIN_CABECERA` líneas con
    identificador de fila e importe a la vez (tabla cuya cabecera no se
    puede leer, ver el comentario de esa constante)."""
    candidatas: list[PaginaCandidata] = []
    anterior_es_candidata = False
    for pagina in paginas:
        densidad = _densidad_numerica(pagina.texto)
        if densidad < UMBRAL_DENSIDAD_NUMERICA:
            anterior_es_candidata = False
            continue
        grupos = _grupos_presentes(normalizar(pagina.texto))
        if len(grupos) >= MIN_GRUPOS_MARCADORES:
            candidatas.append(PaginaCandidata(pagina.numero, densidad, grupos))
            anterior_es_candidata = True
        elif anterior_es_candidata and (
            densidad >= UMBRAL_DENSIDAD_CONTINUACION or _identificadores_fila(pagina.texto) >= 1
        ):
            candidatas.append(PaginaCandidata(pagina.numero, densidad, grupos, continuacion=True))
            # anterior_es_candidata ya es True: se deja igual, la cadena sigue.
        elif _lineas_con_fila_de_datos(pagina.texto) >= MIN_FILAS_DATO_SIN_CABECERA:
            candidatas.append(PaginaCandidata(pagina.numero, densidad, grupos, sin_cabecera_legible=True))
            anterior_es_candidata = True
        else:
            anterior_es_candidata = False
    return ResultadoLocalizacion(candidatas=candidatas, total_paginas=len(paginas))
