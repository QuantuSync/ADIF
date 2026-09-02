"""Normalización de números en formato español. CLAUDE.md sección 8: parsear
"1.234.567,89" con `float()` da 1.234 o revienta; hace falta un normalizador
propio. `Decimal`, nunca `float` — los errores de coma flotante en euros y
porcentajes salen en la tercera cifra."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_NO_DIGITO_NI_SEPARADOR = re.compile(r"[^\d,.\-]")


def parsear_numero_es(cadena: str) -> Decimal:
    """"138.000,00 €" -> Decimal("138000.00"). "145.100 EUR." ->
    Decimal("145100") (sin coma: el punto es separador de miles, no
    decimal — nunca hay más de una convención dentro del mismo documento)."""
    if cadena is None:
        raise ValueError("no hay número que parsear (cadena es None)")
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
