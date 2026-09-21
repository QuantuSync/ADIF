"""La primera fila de una página de continuación que la tabla deja fuera
(sesión 2026-09-21, tercera parte, bloque 3 del encargo: las líneas que
faltan).

El caso real, tres veces: un cuadro que sigue en la página siguiente, y la
primera fila de esa página queda por encima de la caja que `pdfplumber` da a
la tabla, así que no llega a ser fila -- "Horas Técnico especializado … Hora
608 81,25 € 49.400,00 €" (`2.26/28510.0006` ANEJO_1.pdf p.4), "3 Precintos
verdes (1000 unidades) 450,00 € 1350,00 €" (`2.24/28510.0118` p.8), "4 Bandeja
(acero inoxidable) 60x60x5 cm 140,00 € 560,00 €" (`2.23/28510.0138` p.7). El
texto está en la página, justo encima de la tabla y alineado con sus columnas.

Se recompone la fila por **geometría, nunca por proximidad textual**: las
palabras del bloque de renglones pegado a la tabla por arriba se reparten en
las columnas de la propia tabla (`TablaExtraida.columnas_x`) por la posición
de su centro. Y solo vale si la fila **se demuestra por su aritmética**: la
cantidad y el precio que da el mapeo de la tabla multiplican exactamente otra
cifra de la misma fila (su importe), al céntimo, y trae letras en la columna
de la descripción. La línea sale marcada como recuperada y, como toda
recuperación del bloque 3, **solo se queda si con ella el lote cuadra con su
presupuesto publicado** (`app.extraccion.partida_alzada_del_lote.
descartar_recuperadas_que_no_cuadran`).
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Optional

from app.extraccion.normalizacion import parsear_importe_es
from app.extraccion.tabla import TablaExtraida

MARCA_FRAGMENTO = "[fila leída encima de la tabla, que la dejaba fuera]"
_MARGEN_X = 2.0
_TOLERANCIA_RENGLON = 2.0
# Separación máxima entre dos renglones de la misma fila, y entre la fila y la
# tabla, en múltiplos de la altura de un renglón.
_HUECO_MAXIMO = 1.6
_LETRAS_RE = re.compile(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}")


def _numero(celda: Optional[str]) -> Optional[Decimal]:
    if not celda:
        return None
    try:
        return parsear_importe_es(celda.replace("€", "").strip())
    except (ValueError, ArithmeticError):
        return None


def _renglones(palabras: list[dict]) -> list[list[dict]]:
    renglones: list[list[dict]] = []
    for palabra in sorted(palabras, key=lambda p: (p["top"], p["x0"])):
        if renglones and abs(renglones[-1][0]["top"] - palabra["top"]) <= _TOLERANCIA_RENGLON:
            renglones[-1].append(palabra)
        else:
            renglones.append([palabra])
    return renglones


def fila_encima_de_la_tabla(pagina_pdf, tabla: TablaExtraida) -> Optional[list[Optional[str]]]:
    """La fila recompuesta, con una celda por columna de la tabla, o `None`."""
    if not tabla.columnas_x or any(c is None for c in tabla.columnas_x):
        return None
    x0, techo, x1, _ = tabla.bbox
    if techo <= 1:
        return None
    try:
        palabras = pagina_pdf.crop((x0, 0, x1, techo)).extract_words()
    except ValueError:
        return None
    renglones = _renglones(palabras)
    if not renglones:
        return None
    # El bloque de renglones pegado a la tabla, de abajo arriba, mientras no
    # haya un hueco mayor que un renglón y medio.
    bloque: list[list[dict]] = []
    limite = techo
    for renglon in reversed(renglones):
        alto = max(p["bottom"] - p["top"] for p in renglon)
        fondo = max(p["bottom"] for p in renglon)
        if limite - fondo > _HUECO_MAXIMO * alto:
            break
        bloque.insert(0, renglon)
        limite = min(p["top"] for p in renglon)
    if not bloque:
        return None
    celdas: list[list[str]] = [[] for _ in tabla.columnas_x]
    for renglon in bloque:
        for palabra in renglon:
            centro = (palabra["x0"] + palabra["x1"]) / 2
            columnas = [
                j for j, (c0, c1) in enumerate(tabla.columnas_x) if c0 - _MARGEN_X <= centro <= c1 + _MARGEN_X
            ]
            if len(columnas) != 1:
                return None  # una palabra fuera de las columnas: no es una fila de esta tabla
            celdas[columnas[0]].append(palabra["text"])
    return [" ".join(c) if c else None for c in celdas]


def fila_demostrada_por_su_aritmetica(fila: list[Optional[str]], mapeo: dict[str, Optional[int]]) -> bool:
    indices = {campo: mapeo.get(campo) for campo in ("cantidad", "precio_unitario", "descripcion")}
    if any(i is None or i >= len(fila) for i in indices.values()):
        return False
    cantidad, precio = _numero(fila[indices["cantidad"]]), _numero(fila[indices["precio_unitario"]])
    if cantidad is None or precio is None or not _LETRAS_RE.search(fila[indices["descripcion"]] or ""):
        return False
    otras = [
        _numero(celda) for j, celda in enumerate(fila)
        if j not in (indices["cantidad"], indices["precio_unitario"], indices["descripcion"])
    ]
    return any(v is not None and abs(v - cantidad * precio) <= Decimal("0.01") for v in otras)
