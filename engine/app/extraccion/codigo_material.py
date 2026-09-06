"""`Código del material` (CONTEXTO.md sección 6 y 7): "el sustantivo principal
de la descripción [...] más un vocabulario controlado que crece con el uso.
El modelo solo se invoca si no casa nada, y su respuesta amplía el
vocabulario."

Esta función cubre solo la parte determinista (sin modelo): buscar el
sustantivo principal contra el vocabulario ya conocido. Si no casa nada, hoy
devuelve `None` en vez de llamar al modelo — la ampliación del vocabulario
vía modelo queda fuera de esta sesión (no hay ningún caso real sin casar
todavía contra el corpus de prueba, CONTEXTO.md sección 13); cuando aparezca
uno, este es el sitio a tocar, sin cambiar la firma de
`construir_linea_catalogo`.
"""
from __future__ import annotations

import re

# Vocabulario inicial (CONTEXTO.md sección 6, ejemplos literales: "BRIDA",
# "PLACA", "JUNTA", "SUPLEMENTO") ampliado con los sustantivos que sí
# aparecen en el corpus de prueba fijo (CONTEXTO.md sección 13: guantes,
# traviesas, balasto). Ordenado de más a menos específico para que un
# sustantivo compuesto ("TIRAFONDO") no lo capture antes uno genérico que
# aparezca como substring.
VOCABULARIO_CODIGO_MATERIAL = (
    "BRIDA",
    "PLACA",
    "JUNTA",
    "SUPLEMENTO",
    "GUANTE",
    "TRAVIESA",
    "BALASTO",
    "TIRAFONDO",
    "TORNILLO",
    "ARANDELA",
    "GRAPA",
)

_PRIMERA_PALABRA_RE = re.compile(r"^\s*([A-ZÁÉÍÓÚÑ]+)")


def derivar_codigo_material(descripcion: str) -> str | None:
    if not descripcion:
        return None
    m = _PRIMERA_PALABRA_RE.match(descripcion.upper())
    if m is None:
        return None
    primera_palabra = m.group(1)
    return primera_palabra if primera_palabra in VOCABULARIO_CODIGO_MATERIAL else None
