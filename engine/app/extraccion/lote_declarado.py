"""El lote del acuerdo marco que un pedido derivado declara en su propio
título publicado (bloque 6, sesión 2026-09-18 continuación).

**El problema que resuelve.** `app.extraccion.herencia_matriz` sabe heredar el
cuadro de precios de un acuerdo marco de un solo lote, pero se planta cuando la
matriz tiene varios: *"la matriz X es multi-lote (N lotes) y este pedido no
declara a cuál pertenece; no se puede heredar sin adivinar"*. Esa cautela es
correcta -- CONTEXTO.md sección 2 avisa de que en un pedido derivado "Lote N"
es una categoría de producto del catálogo del acuerdo marco, y atribuir el
lote equivocado metería en el catálogo precios de otro material.

**Lo que cambia.** Muchos pedidos **sí** declaran su lote, en el propio
"Objeto del Contrato" que publica la Plataforma: *"...Lote 2: Base en
Sanchidrián."*, *"...expediente principal 4.23/04110.0256 lote 4: guantes de
protección contra riesgos mecánicos..."*. Eso es una declaración estructural
-- un número escrito por el órgano de contratación en un campo fijo del
anuncio --, no un parecido de texto entre la descripción del pedido y la de un
lote de la matriz. La diferencia importa: emparejar por parecido es
exactamente lo que este módulo **no** hace.

**Reglas, deliberadamente estrechas.** Se devuelve un lote solo cuando no hay
nada que interpretar:

- El número va **detrás** de la palabra "lote" ("Lote 4", "lote nº 4",
  "LOTE 4:"). *"(8 LOTES)"* es el número de lotes de la licitación, no un lote
  concreto, y va delante: no dispara.
- Si el título nombra **más de un lote distinto**, no se devuelve ninguno. Un
  pedido que cita dos lotes no declara el suyo, los menciona.
- El número se devuelve tal cual lo escribe el documento, sin ceros a la
  izquierda ("Lote 04" -> "4"), porque es así como
  `Lote.identificador_lote` guarda los lotes de la matriz.

Quien lo use tiene que exigir además que **exista exactamente un lote con ese
identificador** en la matriz: si el número declarado no casa con ninguno, no
hay herencia -- se manda a revisión diciendo qué se leyó y qué lotes hay.
"""
from __future__ import annotations

import re
from typing import Optional

# "lote" / "lotes" / "Lote nº" / "LOTE Nº" seguido del número. El `\b` final
# evita casar el "4" de "lote 4110" (un código de expediente pegado).
_LOTE_DECLARADO = re.compile(
    r"\blotes?\s*(?:n[ºo°\.]*\s*)?(\d{1,3})\b",
    re.IGNORECASE,
)

# El número de expediente principal que algunos pedidos declaran en el mismo
# título ("expediente principal 4.23/04110.0256", "exp.4.23/04110.0256"). No se
# usa para heredar -- la matriz sigue siendo la del campo fijo del anuncio --,
# pero sirve para explicar el enlace en la columna "Motivo" y para poder
# decirlo en el registro de la sesión sin tener que abrir el PDF.
_EXPEDIENTE_PRINCIPAL = re.compile(
    r"(?:expediente\s+principal|exp\.?)\s*[:\s]*((?:\d+\.)?\d{1,2}/\d{4,5}\.\d{3,4})",
    re.IGNORECASE,
)


def extraer_lote_declarado(titulo: Optional[str]) -> Optional[str]:
    """El identificador del lote que el título declara, o `None` si no declara
    exactamente uno. Ver las reglas en el docstring del módulo."""
    if not titulo:
        return None
    numeros = {m.group(1).lstrip("0") or "0" for m in _LOTE_DECLARADO.finditer(titulo)}
    if len(numeros) != 1:
        return None
    return next(iter(numeros))


def extraer_expediente_principal_declarado(titulo: Optional[str]) -> Optional[str]:
    """El expediente principal que el título declara, o `None` si no declara
    exactamente uno. Solo informativo (ver el comentario de
    `_EXPEDIENTE_PRINCIPAL`)."""
    if not titulo:
        return None
    codigos = {m.group(1) for m in _EXPEDIENTE_PRINCIPAL.finditer(titulo)}
    if len(codigos) != 1:
        return None
    return next(iter(codigos))
