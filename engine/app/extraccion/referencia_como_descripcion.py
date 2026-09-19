"""La Descripción del material que en realidad es la referencia del documento.

Bloque 1, decisión 5 del cliente (sesión 2026-09-19, sexta parte). Tres
cuadros reales del corpus -- `2.23/28510.0098` (p.4 y p.9), `6.22/28510.0051`
y `6.22/28510.0159` (p.9), todos con la cabecera "TIPO | CANTIDAD | PRECIO
UD. | PRECIO TOTAL" -- listan insertos y fresas de mecanizado por su
referencia de fabricante ("SFT01-2388L-PH-6920", "WCMX-04 02 08-R53",
"SNC-55 R16 T03 IN6530") y no traen ninguna otra columna de texto. La quinta
guarda de la etapa 4 (`app.extraccion.tabla._tiene_columna_de_descripcion`,
sesión 2026-09-19 quinta parte) los dejaba fuera enteros, porque una
referencia no es una designación y sin designación entraban líneas de
catálogo sin descripción.

El cliente decide que **la referencia se acepta como Descripción del
material** y que esas líneas queden marcadas de forma visible, igual que las
de reconocimiento óptico. Este módulo es esa marca, y está aparte por lo
mismo que `app.extraccion.ocr` lo está: es un hecho sobre de dónde sale el
dato, no sobre el dato.

La marca va en los tres mismos sitios que la de reconocimiento óptico:
`lineas_catalogo.descripcion_desde_referencia` (migración 0040), el
`motivo_revision` de la línea y un prefijo en el fragmento que la ancla.
"""

from __future__ import annotations

MARCA_FRAGMENTO = "[descripción tomada de la referencia del documento]"
MOTIVO_DESCRIPCION_DESDE_REFERENCIA = (
    "la Descripción del material de esta línea es la referencia que el documento imprime para el "
    "artículo (su única columna de texto), no una designación en prosa: el cuadro de precios no publica "
    "ninguna descripción de este material"
)


def marcar_descripcion_desde_referencia(linea: dict) -> None:
    linea["descripcion_desde_referencia"] = True
    motivo = linea.get("motivo_revision")
    if not motivo or MOTIVO_DESCRIPCION_DESDE_REFERENCIA not in motivo:
        linea["motivo_revision"] = (
            f"{MOTIVO_DESCRIPCION_DESDE_REFERENCIA}; {motivo}"
            if motivo
            else MOTIVO_DESCRIPCION_DESDE_REFERENCIA
        )
    fragmento = linea.get("fragmento")
    if fragmento and not fragmento.startswith(MARCA_FRAGMENTO):
        linea["fragmento"] = f"{MARCA_FRAGMENTO} {fragmento}"
