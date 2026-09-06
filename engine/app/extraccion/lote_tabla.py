"""Etapa 3.5: a qué lote pertenece cada tabla de precios localizada, cuando
el expediente declara varios (CONTEXTO.md, encargo de esta sesión, punto 3 —
"es la parte difícil"). Aprobado explícitamente por el usuario: se decide
por la **posición de la tabla en la página** (la caja delimitadora que ya da
`pdfplumber`), nunca por proximidad textual ni por adivinación.

Una página puede traer más de una tabla de lote (verificado contra el
expediente real 6.25/28510.0027: los lotes pequeños caben enteros y dos
tablas de "LOTE N" distintas comparten página), así que "la página menciona
LOTE N" no es señal suficiente — hace falta saber a cuál de sus tablas
pertenece cada mención.

La regla: cada tabla tiene una franja vertical propia y exclusiva, desde el
fondo de la tabla anterior en la misma página (o el principio de la página,
si es la primera) hasta su propio techo. Si en esa franja —y solo ahí—
aparece una única cabecera "LOTE N", esa tabla es de ese lote: es la
cabecera de sección que la introduce, con certeza estructural, no una
suposición. Si aparecen cero o varias, la tabla es ambigua y no se le asigna
lote por defecto ni por cercanía: sus líneas quedan huérfanas (CONTEXTO.md,
`app.models.LineaCatalogo.lote_id` admite NULL para esto) y van a la cola de
revisión.

**Herencia de lote entre páginas: deliberadamente sin implementar todavía**
(ajuste 2 del usuario a este plan). Cuando la franja está vacía de texto
—posible continuación de una tabla partida entre dos páginas, sin ninguna
otra cosa a la que pudiera pertenecer— sería técnicamente inequívoco heredar
el lote de la tabla anterior, pero es la única regla de este módulo que
infiere en vez de leer directamente el documento, y una regla así puede
fallar de formas silenciosas. Se deja como huérfana, con un motivo distinto
("banda vacía") para poder medir cuántas líneas caen en este caso concreto
sobre el corpus real antes de decidir si vale la pena implementarla.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_LOTE_CABECERA_RE = re.compile(r"\bLOTE\s*[Nº°]?\.?\s*(\d{1,2})\b", re.IGNORECASE)


@dataclass(frozen=True)
class ResultadoAsociacionLote:
    identificador_lote: Optional[str]
    # None solo cuando `identificador_lote` no es None. Cuando es ambiguo,
    # distingue el caso "banda vacía" (ver docstring del módulo) de "banda
    # con texto pero sin cabecera reconocible" y de "varias cabeceras en la
    # banda" — necesario para poder contar cada caso por separado.
    motivo_ambiguo: Optional[str]


def asociar_lote_tabla(
    pagina_pdfplumber,
    banda_top: float,
    tabla_bbox: tuple[float, float, float, float],
    identificadores_validos: Optional[set[str]] = None,
) -> ResultadoAsociacionLote:
    """`banda_top`: fondo (en coordenadas de página) de la tabla anterior en
    esta misma página, o 0 si `tabla_bbox` es la primera tabla de la
    página — la llama el orquestador de la búsqueda de banda (ver
    `app.extraccion.pipeline_anejo`), que es quien recorre las tablas de una
    página en orden y sabe cuál es "la anterior"."""
    _x0, techo_tabla, _x1, _bottom = tabla_bbox
    banda = pagina_pdfplumber.crop((0, banda_top, pagina_pdfplumber.width, techo_tabla))
    texto_banda = banda.extract_text() or ""

    identificadores = sorted(set(_LOTE_CABECERA_RE.findall(texto_banda)))

    if len(identificadores) == 1:
        identificador = identificadores[0]
        if identificadores_validos is not None and identificador not in identificadores_validos:
            # Red de seguridad: la tabla apunta a un lote que ningún
            # documento de etiqueta fija declaró. No se adivina cuál de los
            # lotes conocidos "debía" ser — huérfana también.
            return ResultadoAsociacionLote(
                identificador_lote=None,
                motivo_ambiguo=(
                    f"la tabla se asocia al LOTE {identificador}, que no está entre los lotes "
                    "declarados del expediente"
                ),
            )
        return ResultadoAsociacionLote(identificador_lote=identificador, motivo_ambiguo=None)

    if not identificadores:
        if not texto_banda.strip():
            return ResultadoAsociacionLote(
                identificador_lote=None,
                motivo_ambiguo="banda vacía: posible continuación de tabla partida entre páginas, sin inferir",
            )
        return ResultadoAsociacionLote(
            identificador_lote=None,
            motivo_ambiguo="ninguna cabecera LOTE N encontrada en la franja que precede a esta tabla",
        )

    return ResultadoAsociacionLote(
        identificador_lote=None,
        motivo_ambiguo=f"varias cabeceras de lote en la franja que precede a esta tabla: {identificadores}",
    )
