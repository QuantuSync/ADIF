"""Etapa 4 de la cascada de extracción (CONTEXTO.md sección 5): extraer el
cuadro de precios de una página candidata con `pdfplumber`, nunca con el
texto plano de esa página — sale entrelazado e inservible (CONTEXTO.md sección
3 y docstring de `app.extraccion.texto`).

Hallazgo de esta sesión sobre el corpus real que CONTEXTO.md todavía no recoge:
`pdfplumber` no siempre da una cabecera limpia en la primera fila. Cuando la
cabecera envuelve a varias líneas visuales anchas, `find_tables()` puede
devolver esas líneas como filas de tabla independientes — vacías a trozos,
con el nombre de cada columna repartido entre varias de ellas — antes de la
primera fila de datos real. No hay forma fiable de saber por adelantado
cuántas filas ocupa la cabecera, así que se localiza la primera fila de
*datos* (la que trae un código de precio con la forma `P-NNN`, CONTEXTO.md
sección 2) y todo lo anterior se trata como cabecera: se fusiona columna a
columna, uniendo con un espacio los fragmentos no vacíos de cada una en el
orden en que aparecen.

Una página puede traer más de un cuadro de precios (páginas de tabla ancha
partida en dos regiones, o un pliego que reaparece por dentro con otro
Anejo) y `find_tables()` también puede devolver una tabla espuria (una
leyenda envuelta que cae fuera de cualquier tabla real): una tabla sin
ninguna fila con código de precio se descarta entera, no se fuerza un mapeo.

Hallazgo de la sesión de arreglos pequeños (2026-09-03,
docs/analisis-corpus.md hallazgo 2): en 9 expedientes / 11 documentos reales
el guion del código viene como uno de los guiones tipográficos Unicode
("P‐001", U+2010), no el guion ASCII. El filtro de fila de datos normaliza
el guion antes de comparar (`app.extraccion.normalizacion.normalizar_guiones`,
punto único de esa normalización) para no fallar en silencio y descartar la
tabla entera como espuria.

Sesión de expedientes sin publicar (2026-09-03, docs/analisis-corpus.md
hallazgo 6): "P-NNN" tampoco es el único formato real de identificador de
fila. Verificado documento a documento contra el corpus real (no inventado):
- `P1`, `P2` (sin separador, `6.24/28510.0047_ANEJO_1.pdf`, cupones de carril).
- `P01`, `P02` (sin separador, dos dígitos, `6.24/28510.0187_ANEJO_1.pdf`,
  tapas de canaleta).
- `PN001`..`PN024` (prefijo "PN", `6.24/28510.0180_ANEJO_1.pdf`, señalización).
- `PA-01`, `PA-02` (partida alzada numerada, `6.24/28510.0094`, dentro del
  Contrato — el mismo cuadro de traviesas trae también `L01-T01`..`L03-T19`,
  ver siguiente punto).
- `L01-T01`..`L03-T19` (prefijo de lote+tipo, no es semánticamente un "código
  de precio" per CONTEXTO.md sección 3, pero identifica la fila igual de bien
  dentro de su tabla — no hace falta distinguirlo aquí, solo saber que esa
  fila es una fila de datos).
- Tablas sin ninguna columna de código: la fila de datos se identifica por su
  matrícula de 9 dígitos en su lugar (`6.20/28510.0136_ANEJO_3.pdf`, hilo de
  contacto) — CONTEXTO.md sección 2, la matrícula tiene forma fija de 9 dígitos.

Sexto formato, sesión de expedientes en revisión por trabajo pendiente real
(bloque 3, 2026-09-07), `4.26/28510.0020_ANEJO_1.pdf` (instalaciones de
seguridad): `Cod0001`..`Cod0305`, prefijo "Cod" + 4 dígitos, consistente en
las 8 páginas de la tabla real. Sin esta variante, `find_tables()` sí
encontraba la tabla (13 filas limpias, cabecera "Código"/"DESCRIPCION"/
"PRECIO") pero `_indice_primera_fila_datos` no reconocía ninguna fila como
fila de datos y la tabla entera se descartaba como espuria -- el expediente
quedaba en revisión con "no se extrajo ninguna línea de catálogo de los
documentos descargados", indistinguible en el motivo de un expediente
genuinamente sin cuadro de precios publicado (CONTEXTO.md sección 16,
`6.24/28510.0025`/`0193`) aunque la tabla estuviera ahí, intacta, esperando
a leerse. `IGNORECASE` porque no hay garantía de que el corpus mantenga
siempre "Cod" con esa capitalización exacta.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.extraccion.normalizacion import normalizar_guiones, parsear_importe_es
from app.extraccion.texto import normalizar

CELDA = str | None
FILA = list[CELDA]

# Alternativas verificadas contra el corpus real (ver docstring del módulo,
# hallazgo 6): un guion opcional cubre "P-001" y "P1"/"P01" a la vez, sin
# necesitar una rama aparte para cada uno.
#
# Séptimo formato, sesión 2026-09-14 (`6.21/28510.0109_ANEJO_7bfc92005f43e68e.
# pdf` p.15-22 y `ANEJO_ce1df15b39efdb8c.pdf` p.27-36): variante de un mismo
# precio con una letra MAYÚSCULA de sufijo, pegada o separada por un espacio
# ("P-39B", "P-41 A", "P-67 A" -- aguja y contraaguja del mismo desvío). Sin
# ella, una página entera de filas así no tenía ninguna "fila de datos" y la
# tabla se descartaba como espuria. Solo mayúscula (`(?-i:...)`): una letra
# minúscula pegada al código es el sello de verificación CSV invertido que se
# cuela en la celda ("P-13\np", de "psj.adilav..."), no una variante real.
_CODIGO_PRECIO_RE = re.compile(r"^(?:P-?\d+(?-i:[A-Z])?|PN\d+|PA-\d+|L\d+-T\d+|COD\d+)$", re.IGNORECASE)
# Matrícula como identificador de fila cuando la tabla no trae ninguna
# columna de código en absoluto (CONTEXTO.md sección 2: forma fija de 9
# dígitos) — señal aparte, nunca se confunde con un código de precio.
#
# Sesión 2026-09-16 (`6.26/28510.0004`, anejo nº 1 del PPT p.7): la misma
# matrícula escrita con puntos de miles ("667.500.506"). La normalización de
# la línea ya la trataba como el mismo número desde la sesión 2026-09-14
# (`app.catalogo._MATRICULA_CON_PUNTOS_RE`, mismo patrón), pero este
# detector -- que decide si una fila es de datos y, con ello, si la tabla
# entera es un cuadro de precios o ruido -- seguía exigiendo los 9 dígitos
# seguidos. Efecto real: un cuadro de un solo artículo, sin ninguna columna
# de código de precio, se descartaba entero por espurio y el expediente se
# quedaba sin ninguna línea. Medido sobre los 117 expedientes con documentos
# y cero líneas antes del arreglo: afecta a 3 (`6.26/28510.0004`,
# `6.23/28510.0034`, `6.24/28510.0048`).
_MATRICULA_DATO_RE = re.compile(r"^(?:\d{9}|\d{3}\.\d{3}\.\d{3})$")
# Sesión 2026-09-17: la matrícula antigua de 8 cifras ("59020019"). Un número
# de 8 cifras suelto es más ambiguo, así que solo cuenta como identificador de
# fila si la cabecera nombra la matrícula o si al menos
# `_MIN_FILAS_MATRICULA_8` filas de la tabla traen uno (una página de
# continuación, sin cabecera, de un cuadro de matrículas antiguas).
_MATRICULA_8_RE = re.compile(r"^\d{8}$")
_MIN_FILAS_MATRICULA_8 = 3


@dataclass(frozen=True)
class TablaExtraida:
    cabecera: FILA
    filas: list[FILA]
    pagina: int
    # (x0, top, x1, bottom) en coordenadas de página de pdfplumber. Etapa 3.5
    # (`app.extraccion.lote_tabla`) la usa para saber qué franja de la
    # página precede a esta tabla y buscar ahí su cabecera "LOTE N" — nunca
    # por proximidad textual global, que en una página con varias tablas de
    # lote (CONTEXTO.md sección 3: un lote pequeño cabe entero en una página
    # junto a otro) confundiría una tabla con la cabecera de la siguiente.
    bbox: tuple[float, float, float, float]
    # Sesión 2026-09-14: (x0, x1) de cada columna, en el mismo orden que las
    # celdas de `filas` (`None` si pdfplumber no dio ninguna celda con
    # geometría en esa columna). `app.extraccion.mapeo_cabecera.
    # heredar_mapeo_por_geometria` la usa para que una tabla sin cabecera
    # propia que continúa otra de la página anterior herede su mapeo solo si
    # sus columnas caen en las MISMAS posiciones -- nunca por número de
    # columnas, que ya falló una vez (docstring retirado en `mapeo_cabecera`).
    columnas_x: tuple[tuple[float, float] | None, ...] = ()


def _columnas_x(tabla) -> tuple[tuple[float, float] | None, ...]:
    resultado = []
    for columna in tabla.columns:
        if not any(columna.cells):
            resultado.append(None)
            continue
        x0, _, x1, _ = columna.bbox
        resultado.append((float(x0), float(x1)))
    return tuple(resultado)


def _celdas_limpias(fila: FILA) -> list[str]:
    return [normalizar_guiones(re.sub(r"\s+", "", celda)) for celda in fila if celda]


def _es_fila_de_datos(fila: FILA, admite_matricula_8: bool = False) -> bool:
    for limpia in _celdas_limpias(fila):
        if _CODIGO_PRECIO_RE.match(limpia) or _MATRICULA_DATO_RE.match(limpia):
            return True
        if admite_matricula_8 and _MATRICULA_8_RE.match(limpia):
            return True
    return False


def _admite_matricula_8(filas: list[FILA]) -> bool:
    if any("matric" in normalizar(celda or "") for fila in filas[:3] for celda in fila):
        return True
    con_8 = sum(1 for fila in filas if any(_MATRICULA_8_RE.match(c) for c in _celdas_limpias(fila)))
    return con_8 >= _MIN_FILAS_MATRICULA_8


def _indice_primera_fila_datos(filas: list[FILA]) -> int | None:
    admite_8 = _admite_matricula_8(filas)
    for indice, fila in enumerate(filas):
        if _es_fila_de_datos(fila, admite_8):
            return indice
    return None


_GLIFO_CID_RE = re.compile(r"\(cid:\d+\)")
_PALABRA_LEGIBLE_RE = re.compile(r"[A-Za-zÀ-ÿ]{3,}")


def _celda_cabecera_ilegible(celda: str) -> bool:
    """Sesión 2026-09-14 (`6.21/28510.0016_ANEJO_e40fc4e4546ec90b.pdf`
    p.13-20): una fuente sin mapa Unicode hace que `pdfplumber` devuelva
    identificadores de glifo crudos en vez de letras -- "Nº MATRÍCULA" sale
    como "(cid:69)(cid:465)(cid:3)(cid:68)(cid:4)...". Una celda así no dice
    nada sobre qué columna es: mandada al modelo, este mapeó `codigo_precio`
    a la columna de la matrícula y `matricula` a la de "REF. ADIF", y el
    mapeo quedó cacheado bajo esa firma para siempre. Ilegible = trae
    glifos crudos y, quitándolos, no queda ni una palabra de tres letras (a
    veces se cuela un trozo de dato de la fila siguiente, "015-05", que
    tampoco es nombre de columna). Una celda legible con algún glifo suelto
    ("PRECIO UNITARIO DE REFERENCIA (cid:11)(cid:227)(cid:12)", el "(€)" en
    esa fuente) sigue siendo legible y no se toca."""
    if not _GLIFO_CID_RE.search(celda):
        return False
    return not _PALABRA_LEGIBLE_RE.search(_GLIFO_CID_RE.sub("", celda))


def _combinar_filas_cabecera(filas_cabecera: list[FILA]) -> FILA:
    """Una celda de cabecera ilegible (`_celda_cabecera_ilegible`) se deja
    en `None`, igual que una columna fantasma: si TODA la cabecera es así,
    `app.extraccion.mapeo_cabecera.cabecera_sin_senal` la trata como una
    tabla sin cabecera -- nunca se manda ese texto al modelo como si fuera
    una cabecera ni se cachea un mapeo bajo su firma."""
    if not filas_cabecera:
        return []
    num_columnas = max(len(fila) for fila in filas_cabecera)
    cabecera: FILA = []
    for columna in range(num_columnas):
        trozos = [
            fila[columna].strip()
            for fila in filas_cabecera
            if columna < len(fila) and fila[columna] and fila[columna].strip()
        ]
        texto = " ".join(trozos) if trozos else None
        cabecera.append(None if texto is not None and _celda_cabecera_ilegible(texto) else texto)
    return cabecera


# Sesión 2026-09-15 (`6.22/28510.0016`, ANEJO_1 p.21, "LOTE 6: RAM NORTE"):
# `pdfplumber` "imanta" en una sola coordenada las líneas verticales que caen a
# menos de `snap_tolerance` (3 pt) unas de otras, en toda la página. El borde
# izquierdo de la tabla del LOTE 5 (x≈96) arrastraba el del LOTE 6 (x≈99) hasta
# x=95,9, a 3,8 pt de donde empiezan sus líneas horizontales (x=99,7): ya no se
# cortaban, la primera columna -- la de los códigos P-1..P-4 -- desaparecía, y
# sin ningún código la tabla se descartaba por espuria. Sin imantar en
# horizontal (`snap_x_tolerance` 1) la tabla sale entera. Solo como segundo
# intento para una tabla que el primero descarta (medido sobre el corpus
# entero: esa es la única que recupera), nunca sustituyendo a una que ya sale.
_AJUSTES_SEGUNDO_INTENTO = {"snap_x_tolerance": 1}


def _solapan(a: tuple, b: tuple) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


# Sesión 2026-09-15 (expedientes recuperados sin líneas): un cuadro de precios
# de uno o pocos artículos no numera sus filas -- "CONCEPTO | CANTIDAD | PRECIO
# | TOTAL" / "Compresor | 1 | 18.000,00€" (`3.24/28510.0027`), "Concepto |
# Unidades | Importe" (`3.24/28510.0132`, `3.25/28510.0012`), gasóleo y AdBlue
# (`2.25/28510.0005`, `2.24/28510.0050`), un desglose de precios de servicios
# (`2.26/28510.0006`). Sin código ni matrícula no había fila de datos y la
# tabla entera se descartaba por espuria. Se acepta si su PRIMERA fila nombra
# a la vez, en columnas distintas, la descripción, la cantidad y el precio (lo
# que no trae una tabla de resumen de presupuesto, de valor estimado ni de
# criterios), y solo con las filas que la siguen y traen descripción e
# importe, hasta la primera que no (el pie de totales).
_COLUMNA_DESCRIPCION = ("descripcion", "concepto", "designacion", "denominacion")
_COLUMNA_CANTIDAD = ("cantidad", "unidades", "medicion")
_COLUMNA_CANTIDAD_EXACTA = frozenset({"ud", "ud.", "uds", "uds."})
_COLUMNA_PRECIO = ("precio", "importe")
_ETIQUETA_PIE_RE = re.compile(r"^(?:total|subtotal|suma|iva|base imponible|presupuesto|importe total)\b")
_LETRAS_RE = re.compile(r"[a-zñ]{3,}")


def _texto_celda(celda: CELDA) -> str:
    return normalizar(celda or "")


def _columna_con(cabecera: FILA, alias: tuple[str, ...], exactos: frozenset[str] = frozenset()) -> Optional[int]:
    for indice, celda in enumerate(cabecera):
        texto = _texto_celda(celda)
        if texto and (texto in exactos or any(a in texto for a in alias)):
            return indice
    return None


def _es_importe(celda: CELDA) -> bool:
    if not celda or ("," not in celda and "€" not in celda):
        return False
    try:
        return parsear_importe_es(celda) > 0
    except ValueError:
        return False


def _filas_cuadro_sin_codigo(filas: list[FILA]) -> Optional[list[FILA]]:
    cabecera = filas[0]
    descripcion = _columna_con(cabecera, _COLUMNA_DESCRIPCION)
    cantidad = _columna_con(cabecera, _COLUMNA_CANTIDAD, _COLUMNA_CANTIDAD_EXACTA)
    precio = _columna_con(cabecera, ("precio",))
    if precio is None:
        precio = _columna_con(cabecera, _COLUMNA_PRECIO)
    if None in (descripcion, cantidad, precio) or len({descripcion, cantidad, precio}) < 3:
        return None
    datos: list[FILA] = []
    for fila in filas[1:]:
        texto = _texto_celda(fila[descripcion]) if descripcion < len(fila) else ""
        if not _LETRAS_RE.search(texto) or _ETIQUETA_PIE_RE.match(texto):
            break
        if not (precio < len(fila) and _es_importe(fila[precio])):
            break
        datos.append(fila)
    return datos or None


# Bloque 6, sesión 2026-09-18 (sexta parte): el **modelo de oferta en blanco**
# que algunos pliegos de balasto imprimen justo debajo del cuadro de precios
# de verdad. Su cabecera es "Ref. | Denominación | Licitación | Oferta": la
# columna "Licitación" repite el precio de referencia que el cuadro de arriba
# ya trae, y la columna "Oferta" es la que rellena el licitador (viene con el
# hueco marcado, "P10f", "M20f"). Sus filas no son artículos: mezclan esos
# precios repetidos con **mediciones globales** ("M1 Cantidad global de
# balasto ... 27.500,00 Tn"), que entraban al catálogo como si 27.500 fueran
# euros por unidad. Es la misma familia que el "modelo de proposición
# económica en blanco" del acuerdo marco de EPIs (sesión 2026-09-18, quinta
# parte, bloque 4): una tabla para rellenar, no una tabla de datos.
#
# La señal es que la cabecera nombra las dos columnas a la vez, en columnas
# distintas: un cuadro de precios real nunca tiene una columna "Oferta"
# enfrentada a otra "Licitación" -- si las tuviera, sería precisamente eso,
# un formulario de oferta.
_COLUMNA_LICITACION = ("licitacion",)
_COLUMNA_OFERTA = ("oferta",)


def _es_modelo_de_oferta_en_blanco(filas: list[FILA]) -> bool:
    for fila in filas[:2]:
        licitacion = _columna_con(fila, _COLUMNA_LICITACION)
        oferta = _columna_con(fila, _COLUMNA_OFERTA)
        if licitacion is not None and oferta is not None and licitacion != oferta:
            return True
    return False


def _tabla_extraida(tabla, pagina) -> Optional[TablaExtraida]:
    filas = tabla.extract()
    if not filas:
        return None
    if _es_modelo_de_oferta_en_blanco(filas):
        return None
    indice_datos = _indice_primera_fila_datos(filas)
    if indice_datos is None:
        datos = _filas_cuadro_sin_codigo(filas)
        if datos is None:
            return None  # tabla espuria: ni código de precio ni cabecera de cuadro
        return TablaExtraida(
            cabecera=_combinar_filas_cabecera(filas[:1]),
            filas=datos,
            pagina=pagina.page_number,
            bbox=tuple(tabla.bbox),
            columnas_x=_columnas_x(tabla),
        )
    return TablaExtraida(
        cabecera=_combinar_filas_cabecera(filas[:indice_datos]),
        filas=filas[indice_datos:],
        pagina=pagina.page_number,
        bbox=tuple(tabla.bbox),
        columnas_x=_columnas_x(tabla),
    )


def extraer_tablas_pagina(pagina) -> list[TablaExtraida]:
    """`pagina` es un objeto página de `pdfplumber` (ya abierto por el
    llamador, que también es quien decide qué páginas son candidatas —
    etapa 3)."""
    resultado: list[TablaExtraida] = []
    descartadas: list[tuple] = []
    for tabla in pagina.find_tables():
        extraida = _tabla_extraida(tabla, pagina)
        if extraida is not None:
            resultado.append(extraida)
        elif len(tabla.rows) >= 2:
            descartadas.append(tuple(tabla.bbox))
    if not descartadas:
        return resultado
    recuperadas = [
        extraida
        for tabla in pagina.find_tables(_AJUSTES_SEGUNDO_INTENTO)
        if any(_solapan(tuple(tabla.bbox), d) for d in descartadas)
        and not any(_solapan(tuple(tabla.bbox), t.bbox) for t in resultado)
        and (extraida := _tabla_extraida(tabla, pagina)) is not None
    ]
    if not recuperadas:
        return resultado
    # En su sitio de arriba abajo: `app.extraccion.lote_tabla` busca la
    # cabecera "LOTE N" en la franja entre una tabla y la anterior.
    return sorted(resultado + recuperadas, key=lambda t: (t.bbox[1], t.bbox[0]))
