"""Vocabulario de unidades de medida conocidas (sesión 2026-09-15, cuarta
parte, aviso del cliente: la columna de unidad de medida trae conceptos que
no son unidades).

Las reglas de forma de `app.catalogo` (solo dígitos y puntos, tres o más
dígitos, empieza por dígito) ya descartan planos, normas y valores
desplazados, pero no un texto sin cifras de otra columna: barrido del
catálogo real, 40 valores distintos, cuatro que no son unidades --
"Fibra monomodo" (51 líneas, `6.24/28510.0125`: el modelo mapeó la columna
"CARACTERÍSTICAS" como unidad), "Precio mensual" (6, `4.26/28510.0020`: el
propio documento lo escribe en la columna "Ud."), "UNIDAD" (5, la cabecera
repetida en mitad de la tabla de `4.26/28510.0031`) y "ud ud ud" (1, tres
filas fundidas en `6.21/28510.0152`).

Regla: un valor se acepta como unidad solo si, en minúsculas y sin acentos
ni puntos, es una unidad de la lista o una compuesta de ellas ("t x km",
"m3xkm", "UD/día", "€/Ton*mes": el prefijo "€/" dice a qué unidad va el
precio). Las llamadas de nota al pie ("dm3**") no cuentan. La lista son las
unidades del corpus, las del maestro de materiales de SAP y las usuales de
longitud, superficie, volumen, masa y tiempo; no se amplía sin un caso real.
"""

import re
import unicodedata

_UNIDADES = frozenset({
    # Recuento
    "u", "ud", "uds", "un", "und", "unid", "unidad", "unidades",
    "elemento", "elementos", "pieza", "piezas", "pza", "pzas",
    "par", "pares", "juego", "juegos", "jgo", "conjunto", "conjuntos",
    "transporte", "transportes", "viaje", "viajes",
    # Partida alzada
    "pa",
    # Longitud, superficie, volumen
    "m", "ml", "metro", "metros", "km", "cm", "mm",
    "m2", "ha",
    "m3", "dm3", "cm3", "l", "litro", "litros",
    # Masa
    "kg", "g", "t", "tn", "ton", "tonelada", "toneladas",
    # Tiempo
    "h", "hora", "horas", "dia", "dias", "jornada", "jornadas",
    "semana", "semanas", "mes", "meses", "ano", "anos",
    # Unidades base del maestro de materiales de SAP (`maestro_materiales`)
    # que no están ya arriba: el código propio de ADIF, aunque su nombre
    # completo no conste en el fichero.
    "paa", "p", "cj", "bto", "lc", "rol", "ca", "ts", "car", "m-2", "utr",
})

_PREFIJO_PRECIO_RE = re.compile(r"^€\s*/\s*")
_SEPARADOR_RE = re.compile(r"\s*[x*/·]\s*")


def _sin_acentos(texto: str) -> str:
    # NFKD, no NFD: convierte también los superíndices ("m²" -> "m2").
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if unicodedata.category(c) != "Mn")


def es_unidad_conocida(valor: str) -> bool:
    texto = _sin_acentos(valor.strip().lower()).rstrip("*").strip()
    texto = _PREFIJO_PRECIO_RE.sub("", texto)
    if not texto:
        return False
    partes = [parte.replace(".", "") for parte in _SEPARADOR_RE.split(texto)]
    return all(parte in _UNIDADES for parte in partes)
