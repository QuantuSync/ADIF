"""Etapa 4 de la cascada de extracción (CLAUDE.md sección 5): extraer el
cuadro de precios de una página candidata con `pdfplumber`, nunca con el
texto plano de esa página — sale entrelazado e inservible (CLAUDE.md sección
3 y docstring de `app.extraccion.texto`).

Hallazgo de esta sesión sobre el corpus real que CLAUDE.md todavía no recoge:
`pdfplumber` no siempre da una cabecera limpia en la primera fila. Cuando la
cabecera envuelve a varias líneas visuales anchas, `find_tables()` puede
devolver esas líneas como filas de tabla independientes — vacías a trozos,
con el nombre de cada columna repartido entre varias de ellas — antes de la
primera fila de datos real. No hay forma fiable de saber por adelantado
cuántas filas ocupa la cabecera, así que se localiza la primera fila de
*datos* (la que trae un código de precio con la forma `P-NNN`, CLAUDE.md
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
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.extraccion.normalizacion import normalizar_guiones

CELDA = str | None
FILA = list[CELDA]

_CODIGO_PRECIO_RE = re.compile(r"^P-\d+$")


@dataclass(frozen=True)
class TablaExtraida:
    cabecera: FILA
    filas: list[FILA]
    pagina: int
    # (x0, top, x1, bottom) en coordenadas de página de pdfplumber. Etapa 3.5
    # (`app.extraccion.lote_tabla`) la usa para saber qué franja de la
    # página precede a esta tabla y buscar ahí su cabecera "LOTE N" — nunca
    # por proximidad textual global, que en una página con varias tablas de
    # lote (CLAUDE.md sección 3: un lote pequeño cabe entero en una página
    # junto a otro) confundiría una tabla con la cabecera de la siguiente.
    bbox: tuple[float, float, float, float]


def _es_fila_de_datos(fila: FILA) -> bool:
    return any(
        celda and _CODIGO_PRECIO_RE.match(normalizar_guiones(re.sub(r"\s+", "", celda)))
        for celda in fila
    )


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
