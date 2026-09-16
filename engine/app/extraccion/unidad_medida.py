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
"m3xkm", "UD/día", "Ton*mes"). El prefijo de la base del precio ("€/") y las
llamadas de nota al pie ("dm3**") se quitan antes (`limpiar_unidad`). La lista son las
unidades del corpus, las del maestro de materiales de SAP y las usuales de
longitud, superficie, volumen, masa y tiempo; no se amplía sin un caso real.

Sesión 2026-09-16 (noche), encargo del cliente: la misma unidad llega escrita
de varias formas ("UD.", "UN", "ud", "Ud." son todas unidad; "t", "T", "Ton";
"t x km", "Txkm", "Ton*km"). `normalizar_unidad` las lleva a una forma única;
el valor tal como venía se guarda aparte (`unidad_medida_original`). Solo se
unifica lo que es claramente lo mismo -- verificado contra el catálogo real
que "M" es metro (cable, carril) y "T" tonelada (balasto) --; lo que no, se
deja como viene: "PA" (partida alzada) no es "ud", "P" (del maestro de SAP,
sin nombre completo) no es ninguna de las dos, "ml" puede ser metro lineal o
mililitro, "pieza" no se da por "ud".
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

# Forma única de cada unidad que llega escrita de varias maneras, por la clave
# de `_clave` (minúsculas, sin acentos ni puntos). Una parte que no está aquí
# se deja tal cual.
_FORMA_UNICA = {
    "u": "ud", "ud": "ud", "uds": "ud", "un": "ud", "und": "ud", "unid": "ud", "unidad": "ud", "unidades": "ud",
    "m": "m", "metro": "m", "metros": "m",
    "m2": "m2", "m3": "m3", "dm3": "dm3", "cm3": "cm3", "km": "km", "cm": "cm", "mm": "mm",
    "l": "l", "litro": "l", "litros": "l",
    "kg": "kg", "g": "g",
    "t": "t", "tn": "t", "ton": "t", "tonelada": "t", "toneladas": "t",
    "h": "h", "hora": "h", "horas": "h",
    "dia": "día", "dias": "día", "jornada": "jornada", "jornadas": "jornada",
    "semana": "semana", "semanas": "semana", "mes": "mes", "meses": "mes", "ano": "año", "anos": "año",
    "elemento": "elemento", "elementos": "elemento",
    "transporte": "transporte", "transportes": "transporte", "viaje": "viaje", "viajes": "viaje",
    "par": "par", "pares": "par", "juego": "juego", "juegos": "juego", "jgo": "juego",
    "conjunto": "conjunto", "conjuntos": "conjunto",
    "pa": "PA",
}

_PREFIJO_PRECIO_RE = re.compile(r"^€\s*/\s*")
_SEPARADOR_CAPTURA_RE = re.compile(r"\s*([xX*/·])\s*")
_SEPARADOR_RE = re.compile(r"\s*[x*/·]\s*")


def limpiar_unidad(valor: str) -> str | None:
    """Decisión del cliente (sesión 2026-09-15, quinta parte): lo que se
    guarda es la unidad, sin el prefijo de la base del precio ("€/UD" ->
    "UD", "€/Ton*km" -> "Ton*km": 4.084 líneas de `6.21/28510.0108`-`0113`)
    ni la llamada de nota al pie ("dm3**" -> "dm3": 15 líneas de
    `6.24/28510.0088`/`0114`, `6.25/28510.0221`)."""
    limpio = _PREFIJO_PRECIO_RE.sub("", valor.strip()).rstrip("*").strip()
    return limpio or None


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


def _clave(parte: str) -> str:
    return _sin_acentos(parte.strip().lower()).replace(".", "")


def normalizar_unidad(valor: str) -> str:
    """Forma única de una unidad ya aceptada por `es_unidad_conocida`: "UD." ->
    "ud", "Ton" -> "t", "Txkm"/"t x km"/"Ton*km" -> "t·km", "UD/día" ->
    "ud/día", "m³" -> "m3". Una compuesta se normaliza parte a parte, con "·"
    para el producto y "/" para el cociente. Si alguna parte no tiene forma
    única conocida, el valor se devuelve tal cual (sin espacios de los
    extremos): nunca se inventa una equivalencia."""
    texto = valor.strip()
    trozos = _SEPARADOR_CAPTURA_RE.split(texto)
    partes, separadores = trozos[0::2], trozos[1::2]
    formas = [_FORMA_UNICA.get(_clave(parte)) for parte in partes]
    if not all(formas):
        return texto
    resultado = formas[0]
    for separador, forma in zip(separadores, formas[1:]):
        resultado += ("/" if separador == "/" else "·") + forma
    return resultado
