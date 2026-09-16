"""Criterio del cliente sobre qué código de expediente es "nuestro".

Una sola definición para las dos vías de descubrimiento -- la sindicación
(`app.sindicacion.descubrimiento`) y la búsqueda directa en la Plataforma
(`app.scraping.descubrimiento_busqueda`) -- en vez de dos copias de la misma
regla que puedan divergir en silencio.

La regla (sesión 2026-09-15, decisión del cliente): entra todo expediente
cuyo código contenga los dígitos del departamento, en cualquier estado, sin
mirar el órgano de contratación ni la forma del resto del código.

Con una guarda que importa: **los dígitos no pueden ir pegados a otros
dígitos**. "28510" dentro de "1285107" es parte de otro número, no el
departamento. Esto no era un detalle teórico -- verificado en la sesión
2026-09-16 contra resultados reales del buscador de la Plataforma, que
busca por subcadena pura y sin esta guarda devuelve `PcPG/2026/828510` y
`EMER_HV_2020_62285100` como si fueran expedientes del departamento 28510.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from app.config import settings


def fragmento_en_codigo(codigo: Optional[str], fragmento: str) -> bool:
    """`fragmento` aparece en `codigo` sin ir pegado a otros dígitos por
    ninguno de los dos lados. Vale tanto para un departamento suelto
    ("28510") como para un fragmento con separadores ("6.26/28510")."""
    if not codigo or not fragmento:
        return False
    return re.search(rf"(?<!\d){re.escape(fragmento)}(?!\d)", codigo) is not None


def cumple_criterio(codigo: Optional[str], fragmentos: Iterable[str]) -> bool:
    return any(fragmento_en_codigo(codigo, f) for f in fragmentos)


def departamentos_configurados() -> set[str]:
    return {d.strip() for d in (settings.sindicacion_departamentos_adif or "").split(",") if d.strip()}
