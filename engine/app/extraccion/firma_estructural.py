"""Firma estructural de una tabla sin cabecera propia (Bloque 3, sesión de
auditoría 2026-09-09): a diferencia de `firma_cabecera` (que hashea texto de
cabecera y solo sirve cuando hay cabecera real), esta firma se calcula sobre
el CONTENIDO de todas las filas de datos de la tabla -- es lo único
disponible cuando `app.extraccion.mapeo_cabecera.cabecera_sin_senal` es
verdadero.

Un intento anterior (ver el docstring retirado de `mapeo_cabecera.py`,
sección "Bloque 5") comparaba tablas sin cabecera solo por NÚMERO de
columnas, y heredaba a ciegas el mapeo de la primera tabla vista con ese
mismo número a todas las siguientes. Falló contra `6.22/28510.0126_ANEJO_
57694f5d5dacb236.pdf`: la tabla con cabecera real de la página 15 y las
tablas sin cabecera de las páginas 19/20 tienen las dos 8 columnas, pero en
posiciones distintas -- la p.15 trae una columna fantasma vacía justo antes
de la descripción (`[codigo, matricula, VACÍA, descripcion, unidad, ...]`),
mientras que en p.19/20 esa columna vacía no existe y la descripción cae un
índice antes (`[codigo, matricula, descripcion, unidad, ...]`). Heredar el
mapeo de la primera a la segunda desplaza `descripcion` sobre la columna de
`unidad` ("UD." en vez de la designación real).

La firma de aquí distingue este caso porque clasifica cada columna por su
CONTENIDO, no solo por su posición: una columna de descripción real tiene
valores casi todos distintos entre sí (alta cardinalidad) y de longitud
media/larga; una columna de unidad de medida repite un puñado de valores
cortos una y otra vez (baja cardinalidad). Con esa clasificación, la columna
3 de la p.15 (descripción, alta cardinalidad) y la columna 3 de la p.19
(unidad, baja cardinalidad) quedan con tipos distintos -- las dos tablas
nunca comparten firma, y `procesar_anejo` nunca intenta heredar el mapeo de
una a la otra."""
from __future__ import annotations

from typing import Optional

from app.catalogo import _MATRICULA_VALIDA_RE

_UMBRAL_MATRICULA = 0.5
_UMBRAL_PRECIO = 0.5
_UMBRAL_CARDINALIDAD_UNICA = 0.5
_LONGITUD_TEXTO_LARGO = 6
_UMBRAL_RELLENO_MINIMO = 0.2


def _parece_precio(valor: str) -> bool:
    # Solo el símbolo € -- CONTEXTO.md sección 8: "El símbolo € viene dentro
    # de la celda". Un patrón más laxo (p.ej. "contiene una coma decimal")
    # confunde una descripción real con forma "DS-B1-54-320/230-0,11-CR-D"
    # (verificado contra `6.22/28510.0126`) con una columna de precio de
    # verdad: la coma decimal aparece dentro del código de material, no solo
    # en importes.
    return "€" in valor


def _clasificar_columna(valores: list[str], total_filas: int) -> str:
    """`valores`: las celdas no vacías de una columna, una por fila.
    `total_filas`: filas de la tabla completa, para el umbral de relleno de
    abajo. Vacía (sin ningún valor real, o casi ninguno) es su propio tipo --
    una columna fantasma nunca debe casar por accidente con una columna de
    datos reales de otra tabla, y una sola fila con un valor suelto (fila
    fusionada u otro artefacto de extracción, verificado contra
    `6.22/28510.0126` p.20 columna 5: una sola fila trae un precio donde las
    43 restantes están vacías) tampoco debe definir el tipo de toda la
    columna."""
    if not valores or len(valores) / total_filas < _UMBRAL_RELLENO_MINIMO:
        return "vacia"

    con_forma_matricula = sum(1 for v in valores if _MATRICULA_VALIDA_RE.match(v.replace(" ", "")))
    if con_forma_matricula / len(valores) >= _UMBRAL_MATRICULA:
        return "matricula"

    con_forma_precio = sum(1 for v in valores if _parece_precio(v))
    if con_forma_precio / len(valores) >= _UMBRAL_PRECIO:
        return "precio"

    cardinalidad = len(set(valores)) / len(valores)
    longitud_media = sum(len(v) for v in valores) / len(valores)
    if cardinalidad >= _UMBRAL_CARDINALIDAD_UNICA and longitud_media > _LONGITUD_TEXTO_LARGO:
        # Alta cardinalidad + texto largo: descripción, matrícula corrompida
        # u otro campo libre por fila -- nunca un código o unidad que se
        # repite entre filas.
        return "texto_unico"

    return "codigo_repetido"


def calcular_firma_estructural(filas: list[list[Optional[str]]]) -> tuple:
    """Firma estable para comparar DOS tablas sin cabecera del MISMO
    documento (nunca entre documentos, CONTEXTO.md sección 6: el mapeo
    aprendido de una firma de cabecera real sí vale entre documentos porque
    la cabecera es una señal fuerte; el contenido de una tabla sin cabecera
    no lo es lo bastante como para arriesgarse fuera del documento que la
    vio). Incluye el número de columnas explícitamente: dos tablas con el
    mismo patrón de tipos pero distinto número de columnas nunca son "la
    misma forma"."""
    if not filas:
        return (0, ())
    num_columnas = max(len(fila) for fila in filas)
    tipos = []
    for columna in range(num_columnas):
        valores = [
            fila[columna].strip()
            for fila in filas
            if columna < len(fila) and fila[columna] and fila[columna].strip()
        ]
        tipos.append(_clasificar_columna(valores, len(filas)))
    return (num_columnas, tuple(tipos))
