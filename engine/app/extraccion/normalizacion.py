"""Normalización de números en formato español. CLAUDE.md sección 8: parsear
"1.234.567,89" con `float()` da 1.234 o revienta; hace falta un normalizador
propio. `Decimal`, nunca `float` — los errores de coma flotante en euros y
porcentajes salen en la tercera cifra."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_NO_DIGITO_NI_SEPARADOR = re.compile(r"[^\d,.\-]")

# Sesión de arreglos pequeños (2026-09-03, ver docs/analisis-corpus.md
# hallazgo 2): `pdfplumber` extrae el guion del código de precio como uno de
# los guiones tipográficos Unicode (U+2010 HYPHEN, U+2011 NON-BREAKING
# HYPHEN, U+2012 FIGURE DASH, U+2013 EN DASH, U+2014 EM DASH) en vez del
# guion ASCII U+002D que el resto del sistema da por hecho ("P-001"). Punto
# único de normalización: cualquier código que se compare o se guarde pasa
# por aquí, para que un patrón nuevo que espere un guion no repita el mismo
# fallo (CLAUDE.md sección 8, "Normalización — errores que van a aparecer").
_TRADUCCION_GUIONES = str.maketrans({c: "-" for c in "‐‑‒–—"})


def normalizar_guiones(texto: str) -> str:
    """Sustituye los guiones tipográficos Unicode por el guion ASCII. No
    toca nada más (mayúsculas, acentos, espacios) — es un normalizador
    específico, no un sustituto de `app.extraccion.texto.normalizar`."""
    return texto.translate(_TRADUCCION_GUIONES)

# Sesión de rodaje sobre el corpus completo (2026-09-03), expediente
# 6.25/28510.0028: una fuente sin tabla ToUnicode hace que pdfplumber
# extraiga identificadores de glifo crudos, "(cid:1004)", en vez de dígitos.
# Sin esta comprobación, `_NO_DIGITO_NI_SEPARADOR` los cuela igual (los
# dígitos del propio identificador de glifo parecen dígitos válidos) y el
# resultado es un "precio" de 20+ cifras que revienta `numeric(14,4)` en
# base de datos. No se intenta parsear: mejor que la línea vaya a revisión.
_PATRON_CID = re.compile(r"\(cid:\d+\)")


def _resolver_valor_duplicado(cadena: str) -> str:
    """Una celda de cuadro de precios puede traer el mismo valor repetido
    dos veces separadas por un salto de línea — artefacto de una celda mal
    partida en la extracción, p.ej. `"306.351,49 €\\n306.351,49 €"`
    (expediente 6.23/28510.0051, sesión de rodaje 2026-09-03): dos comas en
    el mismo literal rompen el reparto entre parte entera y decimales de
    `parsear_numero_es`. Si las dos líneas coinciden, no hay ambigüedad real
    y se puede usar una; si no coinciden, no se adivina cuál es la buena —
    se devuelve la cadena tal cual para que el parseo normal falle más abajo
    y el llamador la mande a revisión."""
    lineas = [linea.strip() for linea in cadena.splitlines() if linea.strip()]
    if len(lineas) == 2 and lineas[0] == lineas[1]:
        return lineas[0]
    return cadena


def parsear_numero_es(cadena: str) -> Decimal:
    """"138.000,00 €" -> Decimal("138000.00"). "145.100 EUR." ->
    Decimal("145100") (sin coma: el punto es separador de miles, no
    decimal — nunca hay más de una convención dentro del mismo documento)."""
    if cadena is None:
        raise ValueError("no hay número que parsear (cadena es None)")
    if _PATRON_CID.search(cadena):
        raise ValueError(
            f"la celda trae identificadores de glifo sin decodificar (fuente sin ToUnicode), "
            f"no un número: {cadena!r}"
        )
    cadena = _resolver_valor_duplicado(cadena)
    limpio = _NO_DIGITO_NI_SEPARADOR.sub("", cadena.strip())
    if not limpio or limpio in ("-", "."):
        raise ValueError(f"no hay dígitos en {cadena!r}")
    if "," in limpio:
        entero, _, decimales = limpio.rpartition(",")
        limpio = f"{entero.replace('.', '')}.{decimales}"
    else:
        limpio = limpio.replace(".", "")
    try:
        return Decimal(limpio)
    except InvalidOperation as exc:
        raise ValueError(f"no se pudo parsear {cadena!r} como número") from exc


def parsear_importe_es(cadena: str) -> Decimal:
    return parsear_numero_es(cadena)


def parsear_porcentaje_es(cadena: str) -> Decimal:
    """Devuelve la baja como fracción: "54,00 %" -> Decimal("0.5400"), para
    que `precio_adjudicado = precio_licitado * (1 - baja)` (CLAUDE.md sección
    4) se pueda aplicar directamente sin volver a dividir entre 100."""
    return parsear_numero_es(cadena) / Decimal("100")


def limpiar_codigo_celda(valor: str | None) -> str | None:
    """Códigos de precio y matrículas de celda de tabla, sin ningún espacio
    ni salto de línea: "P-\\n001" -> "P-001" (CLAUDE.md sección 8, columnas
    de tabla envueltas por el ancho de columna, no por el contenido). También
    normaliza el guion (ver `normalizar_guiones`), para que el mismo código
    "P‐001"/"P-001" quede siempre igual en el catálogo, sin importar qué
    guion tipográfico trajera la extracción."""
    if valor is None:
        return None
    limpio = re.sub(r"\s+", "", valor)
    limpio = normalizar_guiones(limpio)
    return limpio or None


def limpiar_texto_celda(valor: str | None) -> str | None:
    """Descripción y unidad de celda de tabla: colapsa saltos de línea y
    espacios repetidos a un único espacio, sin perder los límites de
    palabra."""
    if valor is None:
        return None
    limpio = re.sub(r"\s+", " ", valor).strip()
    return limpio or None
