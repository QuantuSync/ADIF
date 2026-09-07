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

from app.extraccion.normalizacion import normalizar_guiones

CELDA = str | None
FILA = list[CELDA]

# Alternativas verificadas contra el corpus real (ver docstring del módulo,
# hallazgo 6): un guion opcional cubre "P-001" y "P1"/"P01" a la vez, sin
# necesitar una rama aparte para cada uno.
_CODIGO_PRECIO_RE = re.compile(r"^(?:P-?\d+|PN\d+|PA-\d+|L\d+-T\d+|COD\d+)$", re.IGNORECASE)
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


def _combinar_filas_cabecera(filas_cabecera: list[FILA]) -> FILA:
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
        cabecera.append(" ".join(trozos) if trozos else None)
    return cabecera


def extraer_tablas_pagina(pagina) -> list[TablaExtraida]:
    """`pagina` es un objeto página de `pdfplumber` (ya abierto por el
    llamador, que también es quien decide qué páginas son candidatas —
    etapa 3)."""
    resultado: list[TablaExtraida] = []
    for tabla in pagina.find_tables():
        filas = tabla.extract()
        if not filas:
            continue
        indice_datos = _indice_primera_fila_datos(filas)
        if indice_datos is None:
            continue  # tabla espuria: ninguna fila trae un código de precio
        cabecera = _combinar_filas_cabecera(filas[:indice_datos])
        resultado.append(
            TablaExtraida(
                cabecera=cabecera,
                filas=filas[indice_datos:],
                pagina=pagina.page_number,
                bbox=tuple(tabla.bbox),
            )
        )
    return resultado
