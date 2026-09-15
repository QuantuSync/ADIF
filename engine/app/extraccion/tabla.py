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

from app.extraccion.normalizacion import normalizar_guiones

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
_MATRICULA_DATO_RE = re.compile(r"^\d{9}$")


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


def _es_fila_de_datos(fila: FILA) -> bool:
    for celda in fila:
        if not celda:
            continue
        limpia = normalizar_guiones(re.sub(r"\s+", "", celda))
        if _CODIGO_PRECIO_RE.match(limpia) or _MATRICULA_DATO_RE.match(limpia):
            return True
    return False


def _indice_primera_fila_datos(filas: list[FILA]) -> int | None:
    for indice, fila in enumerate(filas):
        if _es_fila_de_datos(fila):
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


def _tabla_extraida(tabla, pagina) -> Optional[TablaExtraida]:
    filas = tabla.extract()
    if not filas:
        return None
    indice_datos = _indice_primera_fila_datos(filas)
    if indice_datos is None:
        return None  # tabla espuria: ninguna fila trae un código de precio
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
