"""Etapa 4 de la cascada de extracción (CONTEXTO.md sección 5): extraer el
cuadro de precios de una página candidata con `pdfplumber`, nunca con el
texto plano de esa página — sale entrelazado e inservible (CONTEXTO.md sección
3 y docstring de `app.extraccion.texto`).

Hallazgo de esta sesión sobre el corpus real que CONTEXTO.md todavía no recoge:
`pdfplumber` no siempre da una cabecera limpia en la primera fila. Cuando la
cabecera envuelve a varias líneas visuales anchas, `find_tables()` puede
devolver esas líneas como filas de tabla independientes — vacías a trozos,
con el nombre de cada columna repartido entre varias de ellas — antes de la
primera fila de datos real. No hay forma fiable de saber por adelantado
cuántas filas ocupa la cabecera, así que se localiza la primera fila de
*datos* (la que trae un código de precio con la forma `P-NNN`, CONTEXTO.md
sección 2) y todo lo anterior se trata como cabecera: se fusiona columna a
columna, uniendo con un espacio los fragmentos no vacíos de cada una en el
orden en que aparecen.

Una página puede traer más de un cuadro de precios (páginas de tabla ancha
partida en dos regiones, o un pliego que reaparece por dentro con otro
Anejo) y `find_tables()` también puede devolver una tabla espuria (una
leyenda envuelta que cae fuera de cualquier tabla real): una tabla sin
ninguna fila con código de precio se descarta entera, no se fuerza un mapeo.

Hallazgo de la sesión de arreglos pequeños (2026-09-03,
docs/analisis-corpus.md hallazgo 2): en 9 expedientes / 11 documentos reales
el guion del código viene como uno de los guiones tipográficos Unicode
("P‐001", U+2010), no el guion ASCII. El filtro de fila de datos normaliza
el guion antes de comparar (`app.extraccion.normalizacion.normalizar_guiones`,
punto único de esa normalización) para no fallar en silencio y descartar la
tabla entera como espuria.

Sesión de expedientes sin publicar (2026-09-03, docs/analisis-corpus.md
hallazgo 6): "P-NNN" tampoco es el único formato real de identificador de
fila. Verificado documento a documento contra el corpus real (no inventado):
- `P1`, `P2` (sin separador, `6.24/28510.0047_ANEJO_1.pdf`, cupones de carril).
- `P01`, `P02` (sin separador, dos dígitos, `6.24/28510.0187_ANEJO_1.pdf`,
  tapas de canaleta).
- `PN001`..`PN024` (prefijo "PN", `6.24/28510.0180_ANEJO_1.pdf`, señalización).
- `PA-01`, `PA-02` (partida alzada numerada, `6.24/28510.0094`, dentro del
  Contrato — el mismo cuadro de traviesas trae también `L01-T01`..`L03-T19`,
  ver siguiente punto).
- `L01-T01`..`L03-T19` (prefijo de lote+tipo, no es semánticamente un "código
  de precio" per CONTEXTO.md sección 3, pero identifica la fila igual de bien
  dentro de su tabla — no hace falta distinguirlo aquí, solo saber que esa
  fila es una fila de datos).
- Tablas sin ninguna columna de código: la fila de datos se identifica por su
  matrícula de 9 dígitos en su lugar (`6.20/28510.0136_ANEJO_3.pdf`, hilo de
  contacto) — CONTEXTO.md sección 2, la matrícula tiene forma fija de 9 dígitos.

Sexto formato, sesión de expedientes en revisión por trabajo pendiente real
(bloque 3, 2026-09-07), `4.26/28510.0020_ANEJO_1.pdf` (instalaciones de
seguridad): `Cod0001`..`Cod0305`, prefijo "Cod" + 4 dígitos, consistente en
las 8 páginas de la tabla real. Sin esta variante, `find_tables()` sí
encontraba la tabla (13 filas limpias, cabecera "Código"/"DESCRIPCION"/
"PRECIO") pero `_indice_primera_fila_datos` no reconocía ninguna fila como
fila de datos y la tabla entera se descartaba como espuria -- el expediente
quedaba en revisión con "no se extrajo ninguna línea de catálogo de los
documentos descargados", indistinguible en el motivo de un expediente
genuinamente sin cuadro de precios publicado (CONTEXTO.md sección 16,
`6.24/28510.0025`/`0193`) aunque la tabla estuviera ahí, intacta, esperando
a leerse. `IGNORECASE` porque no hay garantía de que el corpus mantenga
siempre "Cod" con esa capitalización exacta.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Optional

from app.extraccion.normalizacion import normalizar_guiones, parsear_importe_es
from app.extraccion.texto import normalizar

CELDA = str | None
FILA = list[CELDA]

# Alternativas verificadas contra el corpus real (ver docstring del módulo,
# hallazgo 6): un guion opcional cubre "P-001" y "P1"/"P01" a la vez, sin
# necesitar una rama aparte para cada uno.
#
# Séptimo formato, sesión 2026-09-14 (`6.21/28510.0109_ANEJO_7bfc92005f43e68e.
# pdf` p.15-22 y `ANEJO_ce1df15b39efdb8c.pdf` p.27-36): variante de un mismo
# precio con una letra MAYÚSCULA de sufijo, pegada o separada por un espacio
# ("P-39B", "P-41 A", "P-67 A" -- aguja y contraaguja del mismo desvío). Sin
# ella, una página entera de filas así no tenía ninguna "fila de datos" y la
# tabla se descartaba como espuria. Solo mayúscula (`(?-i:...)`): una letra
# minúscula pegada al código es el sello de verificación CSV invertido que se
# cuela en la celda ("P-13\np", de "psj.adilav..."), no una variante real.
_CODIGO_PRECIO_RE = re.compile(r"^(?:P-?\d+(?-i:[A-Z])?|PN\d+|PA-\d+|L\d+-T\d+|COD\d+)$", re.IGNORECASE)
# Matrícula como identificador de fila cuando la tabla no trae ninguna
# columna de código en absoluto (CONTEXTO.md sección 2: forma fija de 9
# dígitos) — señal aparte, nunca se confunde con un código de precio.
#
# Sesión 2026-09-16 (`6.26/28510.0004`, anejo nº 1 del PPT p.7): la misma
# matrícula escrita con puntos de miles ("667.500.506"). La normalización de
# la línea ya la trataba como el mismo número desde la sesión 2026-09-14
# (`app.catalogo._MATRICULA_CON_PUNTOS_RE`, mismo patrón), pero este
# detector -- que decide si una fila es de datos y, con ello, si la tabla
# entera es un cuadro de precios o ruido -- seguía exigiendo los 9 dígitos
# seguidos. Efecto real: un cuadro de un solo artículo, sin ninguna columna
# de código de precio, se descartaba entero por espurio y el expediente se
# quedaba sin ninguna línea. Medido sobre los 117 expedientes con documentos
# y cero líneas antes del arreglo: afecta a 3 (`6.26/28510.0004`,
# `6.23/28510.0034`, `6.24/28510.0048`).
_MATRICULA_DATO_RE = re.compile(r"^(?:\d{9}|\d{3}\.\d{3}\.\d{3})$")
# Sesión 2026-09-17: la matrícula antigua de 8 cifras ("59020019"). Un número
# de 8 cifras suelto es más ambiguo, así que solo cuenta como identificador de
# fila si la cabecera nombra la matrícula o si al menos
# `_MIN_FILAS_MATRICULA_8` filas de la tabla traen uno (una página de
# continuación, sin cabecera, de un cuadro de matrículas antiguas).
_MATRICULA_8_RE = re.compile(r"^\d{8}$")
_MIN_FILAS_MATRICULA_8 = 3


@dataclass(frozen=True)
class TablaExtraida:
    cabecera: FILA
    filas: list[FILA]
    pagina: int
    # (x0, top, x1, bottom) en coordenadas de página de pdfplumber. Etapa 3.5
    # (`app.extraccion.lote_tabla`) la usa para saber qué franja de la
    # página precede a esta tabla y buscar ahí su cabecera "LOTE N" — nunca
    # por proximidad textual global, que en una página con varias tablas de
    # lote (CONTEXTO.md sección 3: un lote pequeño cabe entero en una página
    # junto a otro) confundiría una tabla con la cabecera de la siguiente.
    bbox: tuple[float, float, float, float]
    # Sesión 2026-09-14: (x0, x1) de cada columna, en el mismo orden que las
    # celdas de `filas` (`None` si pdfplumber no dio ninguna celda con
    # geometría en esa columna). `app.extraccion.mapeo_cabecera.
    # heredar_mapeo_por_geometria` la usa para que una tabla sin cabecera
    # propia que continúa otra de la página anterior herede su mapeo solo si
    # sus columnas caen en las MISMAS posiciones -- nunca por número de
    # columnas, que ya falló una vez (docstring retirado en `mapeo_cabecera`).
    columnas_x: tuple[tuple[float, float] | None, ...] = ()
    # Bloque 3, sesión 2026-09-19 (quinta parte): texto propio de esta tabla
    # que NO forma parte de su cabecera de columnas y que la etapa 3.5 debe
    # ver para asociarla a su lote -- la fila "LOTE N" que el cuadro imprime
    # por encima de cada bloque, dentro de la misma caja de tabla (ver
    # `_bloques_por_fila_de_lote`). Se pasa aparte de `cabecera` a propósito:
    # la firma de cabecera (y con ella la caché del mapeo, CONTEXTO.md sección
    # 6) tiene que seguir siendo la misma para los N bloques de un cuadro que
    # repite la misma cabecera de columnas en cada lote.
    titulo_propio: str = ""
    # Sesión 2026-09-21 (tercera parte), bloque 2 del encargo: el rótulo
    # «LOTE N» que una tabla YA ACEPTADA trae en una de sus propias filas --
    # como primera fila, encima de la cabecera de columnas (`3.22/28510.0048`),
    # o en medio de los datos, abriendo el bloque de cada lote
    # (`3.23/28510.0135`, lotes 2 a 8 en la misma caja). Lo lee la etapa 3.5
    # igual que `titulo_propio`, y por la misma razón va aparte de `cabecera`.
    # A diferencia de `titulo_propio` no marca las filas para la comprobación
    # aritmética de `descartar_bloques_de_lote_que_no_cuadran`: esas filas ya
    # salían antes, solo se decide a qué lote pertenecen (ver
    # `_partir_tabla_aceptada_por_rotulos`).
    rotulo_de_lote: str = ""
    # Sesión 2026-09-21 (tercera parte), bloque 3 del encargo: códigos de
    # precio de filas que la tabla dejaba en su cabecera y que se han
    # recuperado como datos (`_fila_con_el_codigo_en_la_cabecera`). Sus líneas
    # solo se quedan si con ellas el lote cuadra con su presupuesto publicado
    # (`app.extraccion.pipeline_anejo.descartar_recuperadas_que_no_cuadran`).
    codigos_recuperados: tuple[str, ...] = ()
    # Misma sesión y misma prueba: el texto literal de la celda de referencia
    # de filas recuperadas por `_referencia_sin_palabras` (ver ahí).
    referencias_recuperadas: tuple[str, ...] = ()
    # Bloque 1, decisión 5 del cliente (sesión 2026-09-19, sexta parte): el
    # índice de la columna que hace de descripción en un cuadro cuya ÚNICA
    # columna de texto es la referencia de la herramienta ("SFT01-2388L-PH-6920",
    # "WCMX-04 02 08-R53"). El cliente acepta la referencia como Descripción del
    # material, con la línea marcada. Se pasa aparte porque lo decide esta etapa
    # -- es la que ya ha comprobado, para aceptar la tabla, que ninguna columna
    # es una designación de verdad (ver `_tiene_columna_de_descripcion`) -- y
    # la etapa 5 no puede saberlo mirando solo la cabecera.
    columna_referencia: Optional[int] = None


def _columnas_x(tabla) -> tuple[tuple[float, float] | None, ...]:
    resultado = []
    for columna in tabla.columns:
        if not any(columna.cells):
            resultado.append(None)
            continue
        x0, _, x1, _ = columna.bbox
        resultado.append((float(x0), float(x1)))
    return tuple(resultado)


def _celdas_limpias(fila: FILA) -> list[str]:
    return [normalizar_guiones(re.sub(r"\s+", "", celda)) for celda in fila if celda]


def _es_fila_de_datos(fila: FILA, admite_matricula_8: bool = False) -> bool:
    for limpia in _celdas_limpias(fila):
        if _CODIGO_PRECIO_RE.match(limpia) or _MATRICULA_DATO_RE.match(limpia):
            return True
        if admite_matricula_8 and _MATRICULA_8_RE.match(limpia):
            return True
    return False


def _admite_matricula_8(filas: list[FILA]) -> bool:
    if any("matric" in normalizar(celda or "") for fila in filas[:3] for celda in fila):
        return True
    con_8 = sum(1 for fila in filas if any(_MATRICULA_8_RE.match(c) for c in _celdas_limpias(fila)))
    return con_8 >= _MIN_FILAS_MATRICULA_8


_CODIGO_AL_FINAL_RE = re.compile(r"\s([A-Za-z]{1,4})-?(\d{1,4})$")
_CODIGO_PARTES_RE = re.compile(r"^([A-Za-z]{1,4})-?(\d{1,4})$")


def _fila_con_el_codigo_en_la_cabecera(filas: list[FILA], indice_datos: int) -> Optional[tuple[int, int, str]]:
    """Sesión 2026-09-21 (tercera parte), bloque 3 del encargo: la extracción
    puede pegar el código de precio de la PRIMERA fila a la celda de la
    cabecera que tiene encima -- "CODIFICACIÓN DEL PRECIO P-1" --, y dejar la
    fila con esa celda vacía (`6.25/28510.0141` ANEJO_1.pdf p.23, el cuadro
    del LOTE 2). Como la tabla empieza a leer en la primera fila con código,
    esa fila se quedaba en la cabecera y el lote perdía su P-1 (61.000 t ×
    10,85 € = 661.850,00 €).

    Solo cuando todo esto se cumple a la vez: la celda de cabecera de la
    columna del código termina en un código; ese código es el ANTERIOR al de
    la primera fila con código (mismo prefijo, número uno menos: "P-1" antes
    de "P-2"); y justo encima de esa primera fila hay UNA fila con esa celda
    vacía y el resto rellenas como las filas de datos. Devuelve (índice de la
    fila, columna del código, código). La línea que sale de ahí pasa además la
    prueba del presupuesto del lote (`codigos_recuperados`)."""
    primera = filas[indice_datos]
    columna = next(
        (i for i, celda in enumerate(primera) if celda and _CODIGO_PARTES_RE.match(re.sub(r"\s+", "", celda))),
        None,
    )
    if columna is None or indice_datos < 1:
        return None
    prefijo, numero = _CODIGO_PARTES_RE.match(re.sub(r"\s+", "", primera[columna])).groups()
    anterior = int(numero) - 1
    if anterior < 1:
        return None
    candidata = indice_datos - 1
    fila = filas[candidata]
    rellenas = lambda f: sum(1 for i, c in enumerate(f) if i != columna and (c or "").strip())  # noqa: E731
    if rellenas(fila) < rellenas(primera) or rellenas(fila) < 2:
        return None
    # Segunda forma, `6.24/28510.0185` p.22: la fila trae su propio código,
    # pero con un sufijo en minúscula ("P-030b", el anterior a "P-031") que no
    # cuenta como código de fila de datos, así que se quedaba de cabecera.
    propio = re.sub(r"\s+", "", fila[columna] or "")
    if propio:
        sufijo = re.match(r"^([A-Za-z]{1,4})-?0*(\d{1,4})([a-z])$", propio)
        if sufijo and sufijo.group(1).upper() == prefijo.upper() and int(sufijo.group(2)) == anterior:
            return candidata, columna, propio
        return None
    if indice_datos < 2:
        return None
    for cabecera in filas[:candidata]:
        texto = re.sub(r"\s+", " ", cabecera[columna] or "").strip() if columna < len(cabecera) else ""
        final = _CODIGO_AL_FINAL_RE.search(texto)
        if final and final.group(1).upper() == prefijo.upper() and int(final.group(2)) == anterior:
            codigo = f"{final.group(1)}-{final.group(2)}" if "-" in primera[columna] else final.group(1) + final.group(2)
            return candidata, columna, codigo
    return None


def _indice_primera_fila_datos(filas: list[FILA]) -> int | None:
    admite_8 = _admite_matricula_8(filas)
    for indice, fila in enumerate(filas):
        if _es_fila_de_datos(fila, admite_8):
            return indice
    return None


_GLIFO_CID_RE = re.compile(r"\(cid:\d+\)")
_PALABRA_LEGIBLE_RE = re.compile(r"[A-Za-zÀ-ÿ]{3,}")


def _celda_cabecera_ilegible(celda: str) -> bool:
    """Sesión 2026-09-14 (`6.21/28510.0016_ANEJO_e40fc4e4546ec90b.pdf`
    p.13-20): una fuente sin mapa Unicode hace que `pdfplumber` devuelva
    identificadores de glifo crudos en vez de letras -- "Nº MATRÍCULA" sale
    como "(cid:69)(cid:465)(cid:3)(cid:68)(cid:4)...". Una celda así no dice
    nada sobre qué columna es: mandada al modelo, este mapeó `codigo_precio`
    a la columna de la matrícula y `matricula` a la de "REF. ADIF", y el
    mapeo quedó cacheado bajo esa firma para siempre. Ilegible = trae
    glifos crudos y, quitándolos, no queda ni una palabra de tres letras (a
    veces se cuela un trozo de dato de la fila siguiente, "015-05", que
    tampoco es nombre de columna). Una celda legible con algún glifo suelto
    ("PRECIO UNITARIO DE REFERENCIA (cid:11)(cid:227)(cid:12)", el "(€)" en
    esa fuente) sigue siendo legible y no se toca."""
    if not _GLIFO_CID_RE.search(celda):
        return False
    return not _PALABRA_LEGIBLE_RE.search(_GLIFO_CID_RE.sub("", celda))


def _combinar_filas_cabecera(filas_cabecera: list[FILA]) -> FILA:
    """Una celda de cabecera ilegible (`_celda_cabecera_ilegible`) se deja
    en `None`, igual que una columna fantasma: si TODA la cabecera es así,
    `app.extraccion.mapeo_cabecera.cabecera_sin_senal` la trata como una
    tabla sin cabecera -- nunca se manda ese texto al modelo como si fuera
    una cabecera ni se cachea un mapeo bajo su firma."""
    if not filas_cabecera:
        return []
    num_columnas = max(len(fila) for fila in filas_cabecera)
    cabecera: FILA = []
    for columna in range(num_columnas):
        trozos = [
            fila[columna].strip()
            for fila in filas_cabecera
            if columna < len(fila) and fila[columna] and fila[columna].strip()
        ]
        texto = " ".join(trozos) if trozos else None
        cabecera.append(None if texto is not None and _celda_cabecera_ilegible(texto) else texto)
    return cabecera


# Sesión 2026-09-15 (`6.22/28510.0016`, ANEJO_1 p.21, "LOTE 6: RAM NORTE"):
# `pdfplumber` "imanta" en una sola coordenada las líneas verticales que caen a
# menos de `snap_tolerance` (3 pt) unas de otras, en toda la página. El borde
# izquierdo de la tabla del LOTE 5 (x≈96) arrastraba el del LOTE 6 (x≈99) hasta
# x=95,9, a 3,8 pt de donde empiezan sus líneas horizontales (x=99,7): ya no se
# cortaban, la primera columna -- la de los códigos P-1..P-4 -- desaparecía, y
# sin ningún código la tabla se descartaba por espuria. Sin imantar en
# horizontal (`snap_x_tolerance` 1) la tabla sale entera. Solo como segundo
# intento para una tabla que el primero descarta (medido sobre el corpus
# entero: esa es la única que recupera), nunca sustituyendo a una que ya sale.
_AJUSTES_SEGUNDO_INTENTO = {"snap_x_tolerance": 1}


def _solapan(a: tuple, b: tuple) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


# Sesión 2026-09-15 (expedientes recuperados sin líneas): un cuadro de precios
# de uno o pocos artículos no numera sus filas -- "CONCEPTO | CANTIDAD | PRECIO
# | TOTAL" / "Compresor | 1 | 18.000,00€" (`3.24/28510.0027`), "Concepto |
# Unidades | Importe" (`3.24/28510.0132`, `3.25/28510.0012`), gasóleo y AdBlue
# (`2.25/28510.0005`, `2.24/28510.0050`), un desglose de precios de servicios
# (`2.26/28510.0006`). Sin código ni matrícula no había fila de datos y la
# tabla entera se descartaba por espuria. Se acepta si su PRIMERA fila nombra
# a la vez, en columnas distintas, la descripción, la cantidad y el precio (lo
# que no trae una tabla de resumen de presupuesto, de valor estimado ni de
# criterios), y solo con las filas que la siguen y traen descripción e
# importe, hasta la primera que no (el pie de totales).
_COLUMNA_DESCRIPCION = ("descripcion", "concepto", "designacion", "denominacion")
_COLUMNA_CANTIDAD = ("cantidad", "unidades", "medicion")
_COLUMNA_CANTIDAD_EXACTA = frozenset({"ud", "ud.", "uds", "uds."})
_COLUMNA_PRECIO = ("precio", "importe")
_ETIQUETA_PIE_RE = re.compile(r"^(?:total|subtotal|suma|iva|base imponible|presupuesto|importe total)\b")
_LETRAS_RE = re.compile(r"[a-zñ]{3,}")


def _texto_celda(celda: CELDA) -> str:
    return normalizar(celda or "")


def _columna_con(cabecera: FILA, alias: tuple[str, ...], exactos: frozenset[str] = frozenset()) -> Optional[int]:
    for indice, celda in enumerate(cabecera):
        texto = _texto_celda(celda)
        if texto and (texto in exactos or any(a in texto for a in alias)):
            return indice
    return None


def _es_importe(celda: CELDA) -> bool:
    if not celda or ("," not in celda and "€" not in celda):
        return False
    try:
        return parsear_importe_es(celda) > 0
    except ValueError:
        return False


# Bloque 3, sesión 2026-09-19 (tercera parte), decisión del cliente sobre los
# 15 expedientes de documentos escaneados: **la columna de cantidad deja de
# ser obligatoria** para aceptar un cuadro sin código de precio ni matrícula.
#
# Por qué se exigía, y por qué ya no: la regla original (sesión 2026-09-15)
# pedía descripción + cantidad + precio porque las tres juntas distinguen un
# cuadro de precios de una tabla de resumen de presupuesto o de criterios. El
# corpus de escaneados demuestra que hay cuadros de precios reales que **no
# publican cantidad en absoluto**, y no por un fallo de lectura: los "Pedido
# Abierto" declaran en su propio texto que no hay compromiso de compra en
# firme ("al ser estas cantidades estimadas"), así que su anexo de precios es
# una lista de designación, plano y precio. Casos medidos:
# `6.18/28510.0071` ("DESIGNACIÓN | PLANO | PRECIO", 6 páginas, ~68
# artículos), `3.16/28510.0156` p.19 ("REF. | DENOMINACIÓN | PRECIO") y
# `3.19/28510.0201` p.10 ("CONCEPTO | PRECIO").
#
# Lo que sustituye a la cantidad como garantía, por condición explícita del
# cliente: **cuando el cuadro trae su propia columna de IMPORTE además de la
# de precio, cada fila tiene que cuadrar** (cantidad × precio = importe). Es
# la misma prueba aritmética que ya autoriza `app.catalogo.
# corregir_precio_con_importe_del_documento` y la descodificación de glifos
# (CONTEXTO.md secciones 7 y 16): no se escribe un número que la aritmética
# del propio documento contradiga. Una fila que no cuadra no entra, y con
# ella se corta la tabla -- nunca se corrige nada aquí.
#
# Las demás guardas siguen intactas y son las que impiden que entre una tabla
# de resumen: la descripción tiene que traer letras de verdad, el precio tiene
# que ser un importe, y la primera fila con etiqueta de pie
# ("Total", "Suma", "IVA", "Presupuesto"...) corta la tabla.
_TOLERANCIA_IMPORTE = Decimal("0.01")
_MIN_FILAS_CUADRO_SIN_CANTIDAD = 3


def _importe_de(celda: CELDA) -> Optional[Decimal]:
    if not celda:
        return None
    try:
        return parsear_importe_es(celda)
    except ValueError:
        return None


def _fila_cuadra_con_su_importe(
    fila: FILA, cantidad: Optional[int], precio: int, importe: Optional[int]
) -> bool:
    """`True` si no hay nada que comprobar (el cuadro no trae importe, o no
    trae cantidad, o esta fila deja alguno de los dos en blanco) o si la
    cuenta sale. Nunca inventa ni corrige un valor."""
    if importe is None or cantidad is None:
        return True
    valor_importe = _importe_de(fila[importe]) if importe < len(fila) else None
    valor_precio = _importe_de(fila[precio]) if precio < len(fila) else None
    valor_cantidad = _importe_de(fila[cantidad]) if cantidad < len(fila) else None
    if None in (valor_importe, valor_precio, valor_cantidad):
        return True
    return abs(valor_cantidad * valor_precio - valor_importe) <= _TOLERANCIA_IMPORTE


# Bloque 1, sesión 2026-09-19 (quinta parte), condición del cliente sobre
# `6.17/28510.0116`: **un precio escrito sin decimales y sin símbolo --
# "5.400" -- solo se acepta si la aritmética del propio documento lo
# demuestra.**
#
# `_es_importe` lo rechaza a propósito y con razón: "5.400" no se distingue
# por sí solo de una cantidad, de una referencia de plano o de una medición.
# El cuadro de ese expediente ("MATRÍCULA | DESIGNACIÓN | PRECIO DE
# REFERENCIA € / ud", 3 artículos, leído por reconocimiento óptico) no
# publica ni columna de cantidad ni columna de importe, así que no hay nada
# DENTRO de la tabla con lo que contrastar cada fila -- lo que sí hay es el
# total del conjunto: su propio `ANEJO_1` declara en la p.3 las cantidades a
# suministrar ("2 CELDAS DE LÍNEA, 2 CELDAS DE MEDIDA Y 2 CELDAS DE LÍNEA CON
# TRANSFORMADOR") y el presupuesto ("se eleva a un total de 49.560 € sIn
# IVA"), y 2 × (5.400 + 9.480 + 9.900) = 49.560,00 € **al céntimo**.
#
# La regla, por tanto: los precios sin decimales de un cuadro solo entran si
# existe **exactamente un** presupuesto publicado de los que el sistema ya
# tiene trazados (el importe de licitación del lote o del expediente, ver
# `app.extraccion.orquestador`) que sea un múltiplo entero exacto de la suma
# de esos precios, con el multiplicador dentro de
# `_MAX_UNIDADES_DEMOSTRACION`. Es el mismo patrón de prueba que la
# verificación del reparto por lotes (sesión 2026-09-18, sexta parte): suma
# del cuadro contra el presupuesto publicado. Tres cautelas:
#
# - **La tabla no puede mezclar.** Si unas filas traen importe de verdad y
#   otras una cifra pelada, la cifra pelada no es un precio sin demostrar: es
#   otra cosa (una medición, un plano), y la tabla entera se descarta.
# - **Sin presupuesto publicado no hay demostración**, y el cuadro se queda
#   fuera -- literalmente lo que pidió el cliente.
# - **Dos presupuestos que cuadren a la vez no demuestran nada**: si la suma
#   divide exactamente a más de uno, el multiplicador es ambiguo y se
#   descarta.
_CIFRA_SIN_DECIMALES_RE = re.compile(r"^\d{1,3}(?:\.\d{3})+$")
_MAX_UNIDADES_DEMOSTRACION = 100


def _cifra_sin_decimales(celda: CELDA) -> Optional[Decimal]:
    """La celda es una cifra con separador de miles, sin parte decimal y sin
    símbolo de moneda ("5.400"). Se exige al menos un grupo de miles: un
    entero corto y suelto ("16", "2") es indistinguible de una cantidad y
    nunca entra por esta vía."""
    if not celda:
        return None
    texto = celda.strip()
    if not _CIFRA_SIN_DECIMALES_RE.match(texto):
        return None
    try:
        valor = parsear_importe_es(texto)
    except ValueError:
        return None
    return valor if valor > 0 else None


def _precios_demostrados_por_un_total(
    precios: list[Decimal], presupuestos: tuple[Decimal, ...]
) -> bool:
    suma = sum(precios, Decimal("0"))
    if suma <= 0:
        return False
    cuadran = set()
    for presupuesto in presupuestos:
        if presupuesto is None or presupuesto <= 0:
            continue
        unidades = Decimal(presupuesto) / suma
        if unidades != unidades.to_integral_value():
            continue
        if not (1 <= unidades <= _MAX_UNIDADES_DEMOSTRACION):
            continue
        cuadran.add(int(unidades))
    return len(cuadran) == 1


def _filas_cuadro_sin_codigo(
    filas: list[FILA], presupuestos_declarados: tuple[Decimal, ...] = ()
) -> Optional[list[FILA]]:
    cabecera = filas[0]
    descripcion = _columna_con(cabecera, _COLUMNA_DESCRIPCION)
    cantidad = _columna_con(cabecera, _COLUMNA_CANTIDAD, _COLUMNA_CANTIDAD_EXACTA)
    precio = _columna_con(cabecera, ("precio",))
    if precio is None:
        precio = _columna_con(cabecera, _COLUMNA_PRECIO)
    if descripcion is None or precio is None or descripcion == precio:
        return None
    if cantidad is not None and cantidad in (descripcion, precio):
        cantidad = None
    # La columna de importes, solo si es una TERCERA columna distinta de la de
    # precio: "PRECIO | IMPORTE" es un cuadro con las dos, "IMPORTE" a secas
    # es el precio de la fila y no hay nada con qué contrastarlo.
    importe = _columna_con(cabecera, ("importe",))
    if importe is not None and importe in (descripcion, precio, cantidad):
        importe = None
    datos: list[FILA] = []
    # Precios aceptados por la vía "cifra sin decimales" (ver el comentario de
    # arriba): si hay alguno, al final se exige la demostración aritmética.
    sin_decimales: list[Decimal] = []
    for fila in filas[1:]:
        texto = _texto_celda(fila[descripcion]) if descripcion < len(fila) else ""
        if not _LETRAS_RE.search(texto) or _ETIQUETA_PIE_RE.match(texto):
            break
        if not (precio < len(fila) and _es_importe(fila[precio])):
            pelada = _cifra_sin_decimales(fila[precio]) if precio < len(fila) else None
            if pelada is None:
                break
            sin_decimales.append(pelada)
        if not _fila_cuadra_con_su_importe(fila, cantidad, precio, importe):
            break
        datos.append(fila)
    if sin_decimales:
        if len(sin_decimales) != len(datos):
            return None  # tabla mixta: la cifra pelada no es un precio
        if not _precios_demostrados_por_un_total(sin_decimales, presupuestos_declarados):
            return None
    # Sin columna de cantidad la señal es más débil, así que se exige un
    # mínimo de filas: un cuadro de precios de verdad lista artículos, y con
    # una o dos filas de "descripción + importe" no se distingue de un
    # resumen de presupuesto. Con cantidad se mantiene el criterio de la
    # sesión 2026-09-15, que aceptaba el cuadro de un solo artículo.
    if cantidad is None and len(datos) < _MIN_FILAS_CUADRO_SIN_CANTIDAD:
        return None
    return datos or None


# Bloque 6, sesión 2026-09-18 (sexta parte): el **modelo de oferta en blanco**
# que algunos pliegos de balasto imprimen justo debajo del cuadro de precios
# de verdad. Su cabecera es "Ref. | Denominación | Licitación | Oferta": la
# columna "Licitación" repite el precio de referencia que el cuadro de arriba
# ya trae, y la columna "Oferta" es la que rellena el licitador (viene con el
# hueco marcado, "P10f", "M20f"). Sus filas no son artículos: mezclan esos
# precios repetidos con **mediciones globales** ("M1 Cantidad global de
# balasto ... 27.500,00 Tn"), que entraban al catálogo como si 27.500 fueran
# euros por unidad. Es la misma familia que el "modelo de proposición
# económica en blanco" del acuerdo marco de EPIs (sesión 2026-09-18, quinta
# parte, bloque 4): una tabla para rellenar, no una tabla de datos.
#
# La señal es que la cabecera nombra las dos columnas a la vez, en columnas
# distintas: un cuadro de precios real nunca tiene una columna "Oferta"
# enfrentada a otra "Licitación" -- si las tuviera, sería precisamente eso,
# un formulario de oferta.
_COLUMNA_LICITACION = ("licitacion",)
_COLUMNA_OFERTA = ("oferta",)


def _es_modelo_de_oferta_en_blanco(filas: list[FILA]) -> bool:
    for fila in filas[:2]:
        licitacion = _columna_con(fila, _COLUMNA_LICITACION)
        oferta = _columna_con(fila, _COLUMNA_OFERTA)
        if licitacion is not None and oferta is not None and licitacion != oferta:
            return True
    return False


# Bloque 1, sesión 2026-09-19 (quinta parte), relectura de `3.16/28510.0044`:
# un cuadro de precios real **sin ningún identificador de fila y con rótulos de
# columna que no están en el vocabulario de esta etapa** ("MEDICIÓN
# PRESUPUESTADA | P.UNITARIO | TOTAL", y la columna de descripción rotulada con
# el título del propio cuadro). `_indice_primera_fila_datos` no ve ninguna fila
# de datos y `_filas_cuadro_sin_codigo` no encuentra ni descripción ni precio,
# así que la tabla se descartaba entera como espuria aunque esté intacta.
#
# La evidencia que sí trae es la que el cliente puso como condición: **la
# aritmética de sus propias filas**. Si existen tres columnas (cantidad,
# precio, importe), en ese orden de izquierda a derecha, tales que TODA fila
# que las trae rellenas cumple cantidad × precio = importe al céntimo, y hay al
# menos `_MIN_FILAS_CUADRAN_TABLA` de esas filas, la tabla es un cuadro de
# precios: ninguna tabla de resumen, de criterios ni de plazos produce esa
# identidad fila a fila.
#
# Cinco guardas, y son las que hacen que esto no pueda tragarse otra cosa:
#
# - **Una sola tripleta.** Si dos combinaciones distintas de columnas cumplen
#   la identidad, el mapeo es ambiguo y no se adivina: se descarta.
# - **Ni una fila que la contradiga.** Una fila con las tres celdas rellenas
#   que no cuadra invalida la tripleta entera (no se ignora la fila: se
#   descarta la tripleta).
#   La tripleta NO dice cuál columna es la cantidad y cuál el precio: la
#   multiplicación es conmutativa, y el corpus trae las dos formas ("Concepto |
#   Precio unitario | Cantidad | Presupuesto" en `2.19/28510.0214`, y "Concepto
#   | Unidades | Precio | Importe" en la mayoría). Eso lo decide la etapa 5 con
#   la cabecera, no esta comprobación: aquí solo se decide si la tabla es un
#   cuadro de precios. Exigir el orden se probó y se retiró: quitaba 9 líneas
#   buenas para excluir 4 dudosas.
# - **Al menos una fila con cantidad distinta de 1.** Sin esta guarda la
#   identidad es gratis: "1 × X = X" la cumple cualquier tabla de conceptos a
#   tanto alzado, y también un resumen de presupuesto de dos líneas. Con ella,
#   lo que se exige es una multiplicación de verdad -- que es lo que un cuadro
#   de precios hace y un resumen no.
# - **Alguna columna tiene que ser una descripción de verdad.** Ver
#   `_tiene_columna_de_descripcion`: sin ella entraban líneas de catálogo sin
#   descripción, que es lo que nunca debe pasar.
# - **La tabla se devuelve por el camino NORMAL**, con su cabecera y sus filas,
#   no con un mapeo inventado aquí: la etapa 5 sigue siendo la que traduce
#   "P.UNITARIO" a `precio_unitario`, con su caché de firma de cabecera. Esto
#   solo decide que la tabla no es espuria.
_MIN_FILAS_CUADRAN_TABLA = 2


def _numero_de_celda(celda: CELDA) -> Optional[Decimal]:
    if not celda:
        return None
    texto = celda.replace("\n", " ").replace("€", "").strip()
    if not texto:
        return None
    try:
        return parsear_importe_es(texto)
    except (ValueError, ArithmeticError):
        return None


def _tripleta_que_cuadra(filas: list[FILA]) -> Optional[tuple[int, int, int]]:
    columnas = max((len(f) for f in filas), default=0)
    if columnas < 3:
        return None
    # Los números de la tabla, una sola vez: probar cada combinación de tres
    # columnas vuelve a mirar las mismas celdas cientos de veces, y parsear un
    # importe no es gratis (esto corre sobre cada tabla de cada página
    # candidata de todo el corpus).
    numeros = [[_numero_de_celda(_valor_celda(fila, i)) for i in range(columnas)] for fila in filas]
    numericas = [i for i in range(columnas) if any(fila[i] is not None for fila in numeros)]
    validas: list[tuple[int, int, int]] = []
    for pos_q, q in enumerate(numericas):
        for pos_p, p in enumerate(numericas[pos_q + 1:], start=pos_q + 1):
            for t in numericas[pos_p + 1:]:
                cuadran = 0
                multiplicacion_real = False
                for fila in numeros:
                    cantidad, precio, importe = fila[q], fila[p], fila[t]
                    if cantidad is None or precio is None or importe is None:
                        continue
                    if cantidad <= 0 or precio <= 0 or importe <= 0:
                        cuadran = -1
                        break
                    if abs(cantidad * precio - importe) > _TOLERANCIA_IMPORTE:
                        cuadran = -1
                        break
                    cuadran += 1
                    if cantidad != 1:
                        multiplicacion_real = True
                if cuadran >= _MIN_FILAS_CUADRAN_TABLA and multiplicacion_real:
                    validas.append((q, p, t))
                if len(validas) > 1:
                    return None
    return validas[0] if len(validas) == 1 else None


def _valor_celda(fila: FILA, indice: int) -> CELDA:
    return fila[indice] if indice < len(fila) else None


# Quinta guarda, encontrada con la auditoría del reproceso completo: la
# aritmética por sí sola acepta una tabla que **no tiene columna de
# descripción**. Caso real medido, `2.23/28510.0098`/`6.22/28510.0051`/`0159`
# (`ANEJO_1` p.9): "SFT01-2388L-PH-6920 | 20 | 24,00 € | 480,00 €" -- código,
# cantidad, precio e importe, y ni una designación. Sus filas cuadran (20 ×
# 24,00 = 480,00) y entraron como 45 líneas de catálogo **sin descripción**,
# que es exactamente lo que la comprobación permanente de
# `construir_linea_catalogo` existe para impedir (sesión 2026-09-06, bloque 2):
# una línea sin descripción no sirve en almacenes.
#
# La guarda, en dos mitades:
#
# - **A nivel de tabla**: alguna columna fuera de la tripleta tiene que ser una
#   columna de DESIGNACIÓN, no de referencia. La distinción, medida contra el
#   corpus: una designación son varias palabras con letras de verdad ("Armario
#   ETSI 2200*600*300 mm. Para alojamiento de equipo SDH", "Instalación y
#   puesta a punto de equipo SDH"); una referencia de herramienta es un código,
#   aunque lleve espacios ("WCMX-04 02 08-R53", "SNC-55 R16 T03 IN6530",
#   "SFT01-2388L-PH-6920"). Se exige que **al menos la mitad** de las filas que
#   cuadran tengan designación en esa misma columna: en el cuadro "TIPO |
#   CANTIDAD | PRECIO UD. | PRECIO TOTAL" de `2.23/28510.0098` solo la cumplen
#   1 de 19, y en un cuadro de verdad la cumplen todas.
# - **A nivel de fila**: una fila solo llega a ser línea si trae letras en
#   alguna columna fuera de la tripleta. Así nunca sale una línea sin
#   descripción, aunque su tabla sí sea un cuadro -- la fila "12.01 | | 1 |
#   1.980,50 | 1.980,50 €" de `3.16/28510.0044` p.19 (el rótulo "Seguridad y
#   Salud" cae en la fila de arriba) cuadra y no es un material.
_PALABRA_CON_LETRAS_RE = re.compile(r"[a-zñ]{3,}")
_MIN_PALABRAS_DESIGNACION = 2


def _parece_designacion(texto: str) -> bool:
    palabras = sum(1 for p in texto.split() if _PALABRA_CON_LETRAS_RE.search(p))
    return palabras >= _MIN_PALABRAS_DESIGNACION


# Bloque 1, decisión 5 del cliente (sesión 2026-09-19, sexta parte): la guarda
# de arriba dejaba fuera **tres cuadros reales** cuya única columna de texto es
# la referencia del inserto o de la fresa ("TIPO | CANTIDAD | PRECIO UD. |
# PRECIO TOTAL", `2.23/28510.0098` p.4 y p.9, `6.22/28510.0051` y
# `6.22/28510.0159` p.9). El cliente decide que esa referencia **se acepta como
# Descripción del material**, y que esas líneas queden marcadas de forma
# visible, igual que las de reconocimiento óptico, diciendo que la descripción
# es la referencia del documento.
#
# Lo que NO cambia: la tabla sigue teniendo que traer una columna de texto
# fuera de la tripleta, y cada fila sigue teniendo que traer letras en ella
# (`_fila_trae_descripcion`). Una tabla de puras cifras sigue sin entrar, y una
# fila sin nada de texto sigue sin llegar a ser línea -- que es lo que esta
# guarda existe para impedir. Lo único que se acepta ahora es que ese texto sea
# un código en vez de una designación en prosa.
@dataclass(frozen=True)
class ColumnaDeTexto:
    indice: int
    # `True` cuando la columna es una designación de verdad (varias palabras
    # con letras) en la mayoría de las filas que cuadran; `False` cuando es una
    # columna de referencias.
    es_designacion: bool


def _tiene_columna_de_descripcion(
    filas: list[FILA], tripleta: tuple[int, int, int], fuera: list[int]
) -> Optional[ColumnaDeTexto]:
    """La columna que hace de descripción de la tabla, o `None` si no hay
    ninguna columna de texto fuera de la tripleta."""
    con_datos = [
        fila for fila in filas
        if all(_numero_de_celda(_valor_celda(fila, i)) is not None for i in tripleta)
    ]
    if not con_datos:
        return None
    referencia: Optional[int] = None
    for indice in fuera:
        con_texto = [
            _texto_celda(_valor_celda(fila, indice)) for fila in con_datos
        ]
        designaciones = sum(1 for texto in con_texto if _parece_designacion(texto))
        if designaciones * 2 >= len(con_datos):
            return ColumnaDeTexto(indice, True)
        if referencia is None:
            con_letras = sum(1 for texto in con_texto if _LETRAS_RE.search(texto))
            if con_letras * 2 >= len(con_datos):
                referencia = indice
    return ColumnaDeTexto(referencia, False) if referencia is not None else None


# Sesión 2026-09-21 (tercera parte), bloque 3 del encargo: en un cuadro de
# REFERENCIAS (`ColumnaDeTexto.es_designacion` falso), una referencia puede no
# tener ninguna secuencia de tres letras -- "R-245-12T3-M-PH-4340",
# "RC-12-WK-H1X" (`2.23/28510.0098` p.9, cuatro filas que cuadran y sin las
# que el cuadro no llega a su "Total 35.760,00 €"). Una referencia de verdad
# mezcla letras y cifras: al menos dos letras y una cifra, y ni una celda de
# puras cifras ni un texto sin cifras. Estas filas salen marcadas
# (`referencias_recuperadas`) y solo se quedan si con ellas el lote cuadra.
_LETRA_RE = re.compile(r"[a-zñ]")
_CIFRA_RE = re.compile(r"\d")


# Misma sesión, `6.22/28510.0051`/`0159` p.9: el cuadro escribe los miles con
# punto ("2.160") y los decimales también con punto ("12.5", "8.5"), y una
# celda "12.5" no se lee. La aritmética de la propia fila lo decide: la celda
# se reescribe con coma solo si así la fila cuadra al céntimo (140 × 12,5 =
# 1.750). Estas filas también salen marcadas (`referencias_recuperadas`).
_DECIMAL_CON_PUNTO_RE = re.compile(r"^\s*(\d{1,3})\.(\d{1,2})\s*$")


def _con_decimal_con_punto(fila: FILA, tripleta: tuple[int, int, int]) -> Optional[FILA]:
    nueva = list(fila)
    cambiada = False
    for i in tripleta:
        celda = _valor_celda(fila, i)
        if _numero_de_celda(celda) is None and celda and _DECIMAL_CON_PUNTO_RE.match(celda):
            nueva[i] = celda.strip().replace(".", ",")
            cambiada = True
    if not cambiada:
        return None
    valores = [_numero_de_celda(_valor_celda(nueva, i)) for i in tripleta]
    if any(v is None for v in valores):
        return None
    cantidad, precio, importe = valores
    return nueva if abs(cantidad * precio - importe) <= Decimal("0.01") else None


def _referencia_sin_palabras(texto: str) -> bool:
    return len(_LETRA_RE.findall(texto)) >= 2 and bool(_CIFRA_RE.search(texto))


def _fila_trae_descripcion(fila: FILA, fuera: list[int]) -> bool:
    return any(_LETRAS_RE.search(_texto_celda(_valor_celda(fila, i))) for i in fuera)


# Bloque 1, decisión 4 del cliente (sesión 2026-09-19, sexta parte), primer
# caso: la cuarta fila del cuadro del lote 1 de `3.21/28510.0096` p.6
# ("Potenciómetro rotatorio, componente 20299800", 10 x 150,00 = 1.500,00).
# Sus tres celdas numéricas caen **una columna a la derecha** de las de las
# otras tres filas de su misma tabla, así que la fila no cuadraba en las
# columnas de la tripleta y se descartaba entera.
#
# Entra solo porque la aritmética del documento la demuestra, que es la
# condición que puso el cliente: el desplazamiento es el MISMO para las tres
# celdas (nunca una a una, que sería recomponer la fila a gusto), las tres
# celdas de la tripleta están vacías -- no es que traigan otra cosa -- y las
# tres desplazadas cumplen cantidad x precio = importe al céntimo. La fila se
# devuelve **sin tocar**: quien lee sus valores después es la recuperación de
# columna fantasma que ya existe (`app.catalogo._recuperar_cantidad_columna_
# fantasma` y `_recuperar_precio_columna_fantasma`), que solo mira la columna
# vecina libre y deja su propio motivo en la línea. Aquí no se reescribe
# ninguna celda: el fragmento de traza sigue siendo la fila tal y como la
# imprime el documento.
_DESPLAZAMIENTO_FILA = 1


def _fila_cuadra_desplazada(fila: FILA, tripleta: tuple[int, int, int]) -> bool:
    if any(_texto_celda(_valor_celda(fila, i)) for i in tripleta):
        return False
    valores = [_numero_de_celda(_valor_celda(fila, i + _DESPLAZAMIENTO_FILA)) for i in tripleta]
    if any(v is None or v <= 0 for v in valores):
        return False
    cantidad, precio, importe = valores
    return abs(cantidad * precio - importe) <= _TOLERANCIA_IMPORTE


# Bloque 1, decisión 4 del cliente, segundo caso: la fila `12.01` del
# presupuesto de `3.16/28510.0044` p.19, releído con reconocimiento óptico.
#
#   ["12",    "Seguridad y Salud", "",  "",         ""]
#   ["12.01", "",                  "1", "1.980,50", "1.980,50 EUR"]
#
# La fila cuadra (1 x 1.980,50 = 1.980,50) y **es la que cierra el TOTAL que el
# documento declara**: las 14 líneas que ya entran suman 822.343,17 EUR y con
# ella suman 824.323,67 EUR, el presupuesto de licitación que el propio pliego
# escribe en letra. Lo único que le falta es la descripción, y el documento la
# imprime: es el rótulo de su sección, en la fila inmediatamente anterior, cuyo
# número (`12`) es el prefijo del suyo (`12.01`).
#
# No se inventa ningún texto ni se busca parecido: la prueba es la numeración
# del propio cuadro. Guardas: la fila de sección no trae ni una cifra en las
# columnas de la tripleta (es solo un rótulo), su número es prefijo ESTRICTO
# del de la fila, separado por un punto, y la fila no tiene texto propio en
# ninguna columna fuera de la tripleta -- si lo tuviera, la descripción sería
# la suya y no habría nada que heredar.
_NUMERO_DE_SECCION_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3})*$")


def _hereda_de_la_fila_de_seccion(
    filas: list[FILA], indice: int, tripleta: tuple[int, int, int], fuera: list[int]
) -> Optional[FILA]:
    """La fila `indice`, con la descripción que el documento imprime en el
    rótulo de su sección, o `None` si no hay tal rótulo."""
    if indice == 0:
        return None
    fila = filas[indice]
    numeros = [
        _texto_celda(_valor_celda(fila, i)) for i in fuera
        if _NUMERO_DE_SECCION_RE.match(_texto_celda(_valor_celda(fila, i)))
    ]
    if len(numeros) != 1:
        return None
    propio = numeros[0]
    seccion = filas[indice - 1]
    if any(_numero_de_celda(_valor_celda(seccion, i)) is not None for i in tripleta):
        return None
    columnas_rotulo = [
        i for i in fuera
        if _NUMERO_DE_SECCION_RE.match(_texto_celda(_valor_celda(seccion, i)))
        and propio.startswith(_texto_celda(_valor_celda(seccion, i)) + ".")
    ]
    if len(columnas_rotulo) != 1:
        return None
    textos = [
        i for i in fuera
        if i not in columnas_rotulo and _LETRAS_RE.search(_texto_celda(_valor_celda(seccion, i)))
    ]
    if len(textos) != 1:
        return None
    nueva = list(fila) + [None] * max(0, len(seccion) - len(fila))
    nueva[textos[0]] = _valor_celda(seccion, textos[0])
    return nueva


def _cuadro_demostrado_por_aritmetica(
    filas: list[FILA],
) -> Optional[tuple[int, list[FILA], "ColumnaDeTexto", tuple[str, ...]]]:
    """(dónde acaba la cabecera, filas de datos) de una tabla que se demuestra
    sola por la aritmética de sus filas, o `None`.

    **Solo salen las filas que pasan la comprobación de su propia fila**, que
    es la condición que puso el cliente para aceptar estas líneas: las filas de
    sección de un presupuesto ("Obra civil", "Energía", "Gestión de Red") no
    traen ni cantidad ni precio y no son materiales, y el pie de totales
    tampoco. Sin este filtro entraban como líneas de catálogo sin precio."""
    tripleta = _tripleta_que_cuadra(filas)
    if tripleta is None:
        return None
    fuera = [i for i in range(max((len(f) for f in filas), default=0)) if i not in tripleta]
    columna_texto = _tiene_columna_de_descripcion(filas, tripleta, fuera)
    if columna_texto is None:
        return None

    def cuadra(fila: FILA) -> bool:
        valores = [_numero_de_celda(_valor_celda(fila, i)) for i in tripleta]
        return all(v is not None for v in valores)

    def es_dato(fila: FILA) -> bool:
        return (cuadra(fila) or _fila_cuadra_desplazada(fila, tripleta)) and _fila_trae_descripcion(
            fila, fuera
        )

    inicio: Optional[int] = None
    if cuadra(filas[0]):
        inicio = 0  # la tabla arranca en datos: es una continuación sin cabecera
    else:
        for indice, fila in enumerate(filas[1:], start=1):
            if cuadra(fila) or any(
                _LETRAS_RE.search(_texto_celda(_valor_celda(fila, i))) for i in fuera
            ):
                # Primera fila con datos o con texto propio fuera de las
                # columnas numéricas: lo de arriba es la cabecera (una o
                # varias líneas).
                inicio = indice
                break
    if inicio is None:
        return None
    datos: list[FILA] = []
    recuperadas: list[str] = []
    for indice in range(inicio, len(filas)):
        fila = filas[indice]
        if es_dato(fila):
            datos.append(fila)
            continue
        con_decimal = None if cuadra(fila) else _con_decimal_con_punto(fila, tripleta)
        candidata = con_decimal if con_decimal is not None else fila
        if con_decimal is not None and es_dato(con_decimal):
            datos.append(con_decimal)
            recuperadas.append(_valor_celda(con_decimal, columna_texto.indice))
            continue
        if (
            not columna_texto.es_designacion
            and cuadra(candidata)
            and _referencia_sin_palabras(_texto_celda(_valor_celda(candidata, columna_texto.indice)))
        ):
            datos.append(candidata)
            recuperadas.append(_valor_celda(candidata, columna_texto.indice))
            continue
        # Decisión 4 del cliente: la fila que cuadra y a la que solo le falta
        # la descripción, cuando el rótulo de su sección la imprime justo
        # encima y su numeración lo demuestra (ver `_hereda_de_la_fila_de_seccion`).
        if cuadra(fila) or _fila_cuadra_desplazada(fila, tripleta):
            heredada = _hereda_de_la_fila_de_seccion(filas, indice, tripleta, fuera)
            if heredada is not None and _fila_trae_descripcion(heredada, fuera):
                datos.append(heredada)
    return (inicio, datos, columna_texto, tuple(recuperadas)) if datos else None


# Bloque 3, sesión 2026-09-19 (quinta parte), los 14 de "cobertura parcial de
# lotes": el cuadro de precios de las compras multi-lote del Laboratorio
# Central de ADIF mete **todos sus lotes en una sola tabla**, cada uno
# encabezado por una fila cuya única celda es la etiqueta del lote:
#
#   ['LOTE 1', '', '']
#   ['Concepto', 'Unidades', 'Importe']
#   ['Calibrador multiproducto...', '3', '210.000,00 €']
#   ['LOTE 2', '', '']
#   ['Concepto', 'Unidades', 'Importe']
#   ['Calibrador de comprobadores...', '1', '23.000,00 €']
#
# La tabla entera se descartaba como espuria porque su PRIMERA fila
# ("LOTE 1") no es una cabecera de columnas, y ni el código de precio ni la
# matrícula existen aquí. Y aunque se aceptara, las líneas de los dos lotes
# quedarían mezcladas o huérfanas: la etapa 3.5 busca el "LOTE N" en la franja
# de página que precede a la tabla, y aquí las etiquetas van DENTRO.
#
# Esto es certeza estructural por geometría, no por parecido: el documento
# pone cada bloque debajo de su propia etiqueta de lote, en orden de lectura.
# Se parte la tabla en un bloque por etiqueta, cada uno con su propia cabecera
# de columnas, y la etiqueta viaja en `TablaExtraida.titulo_propio` para que
# la etapa 3.5 la resuelva por la vía que ya existe (`texto_titulo_tabla`).
#
# Guardas:
# - Esta vía solo se prueba cuando ninguna de las de siempre acepta la tabla
#   (ver `_tablas_extraidas`): no puede quitar una fila que ya salía.
# - Cada bloque tiene que ser un cuadro de precios por sí mismo
#   (`_filas_cuadro_sin_codigo`, con sus guardas de siempre). Si un solo
#   bloque no lo es, no se parte nada: se devuelve la tabla al camino normal.
# - Nada antes de la primera etiqueta entra: es el título del cuadro.
_FILA_SOLO_LOTE_RE = re.compile(r"^lote\s*(?:n[ºo]?\s*)?(\d{1,2})\b")
_MIN_BLOQUES_DE_LOTE = 1


def _etiqueta_de_lote(fila: FILA) -> Optional[str]:
    """La fila es únicamente la etiqueta de un lote ("LOTE 1", "Lote nº2"):
    una sola celda con texto y ese texto empieza por la etiqueta. Devuelve el
    texto literal de la celda, que es lo que la etapa 3.5 sabe interpretar."""
    con_texto = [c for c in fila if _texto_celda(c)]
    if len(con_texto) != 1:
        return None
    return con_texto[0].strip() if _FILA_SOLO_LOTE_RE.match(_texto_celda(con_texto[0])) else None


def _bbox_de_filas(tabla, inicio: int, fin: int) -> tuple[float, float, float, float]:
    """La caja que ocupan las filas `[inicio, fin)` de la tabla, para que cada
    bloque de lote tenga su propia geometría. Si `pdfplumber` no da una fila
    por cada fila extraída (puede fusionar), cae a la caja de la tabla
    entera: perder precisión es aceptable, inventarla no."""
    x0, top, x1, bottom = tabla.bbox
    filas_geometria = [f for f in getattr(tabla, "rows", []) if getattr(f, "bbox", None)]
    if fin > len(filas_geometria) or inicio >= fin:
        return (x0, top, x1, bottom)
    arriba = min(f.bbox[1] for f in filas_geometria[inicio:fin])
    abajo = max(f.bbox[3] for f in filas_geometria[inicio:fin])
    return (x0, arriba, x1, abajo)


def _es_cabecera_de_cuadro(fila: FILA) -> bool:
    descripcion = _columna_con(fila, _COLUMNA_DESCRIPCION)
    precio = _columna_con(fila, ("precio",))
    if precio is None:
        precio = _columna_con(fila, _COLUMNA_PRECIO)
    return descripcion is not None and precio is not None and descripcion != precio


def _bloques_por_fila_de_lote(
    filas: list[FILA], presupuestos_declarados: tuple[Decimal, ...]
) -> Optional[list[tuple[str, FILA, list[FILA], int, int]]]:
    indices = [i for i, fila in enumerate(filas) if _etiqueta_de_lote(fila) is not None]
    if len(indices) < _MIN_BLOQUES_DE_LOTE:
        return None
    bloques: list[tuple[str, FILA, list[FILA], int, int]] = []
    limites = indices + [len(filas)]
    # La cabecera de columnas se repite debajo de cada etiqueta, pero no
    # siempre: `3.21/28510.0098` la imprime para los lotes 1 y 2 y la omite
    # para el 3. Un bloque sin cabecera propia usa la del bloque anterior --
    # es la MISMA tabla, con las mismas columnas en las mismas posiciones, así
    # que no hay nada que adivinar.
    cabecera_vigente: Optional[FILA] = None
    for posicion, inicio in enumerate(indices):
        etiqueta = _etiqueta_de_lote(filas[inicio])
        fin = limites[posicion + 1]
        cuerpo = filas[inicio + 1:fin]
        if cuerpo and _es_cabecera_de_cuadro(cuerpo[0]):
            cabecera_vigente = cuerpo[0]
            cuerpo = cuerpo[1:]
        if cabecera_vigente is None or not cuerpo:
            return None
        datos = _filas_cuadro_sin_codigo([cabecera_vigente] + cuerpo, presupuestos_declarados)
        if not datos:
            return None
        bloques.append((etiqueta, cabecera_vigente, datos, inicio, fin))
    return bloques


def _partir_tabla_aceptada_por_rotulos(tabla, filas: list[FILA], unica: TablaExtraida) -> Optional[list[TablaExtraida]]:
    """Sesión 2026-09-21 (tercera parte), bloque 2 del encargo: una tabla que
    las vías de siempre aceptan puede traer el rótulo de su lote en una de sus
    propias filas -- encima de la cabecera de columnas o entre sus datos, una
    fila por lote --, y hasta hoy ese rótulo no decidía nada: el lote salía de
    la franja de encima, que en `3.22/28510.0048` dice "El presupuesto base
    del lote 1 es de…" justo encima del cuadro del LOTE 2, y en
    `3.23/28510.0135` los lotes 3 a 8 se quedaban en el 2.

    Se parte la tabla por esas filas: cada tramo de datos queda con el rótulo
    que lo abre (`rotulo_de_lote`), y el tramo anterior al primer rótulo de
    los datos se queda con el de la cabecera, si lo hay, o sin ninguno (y la
    etapa 3.5 decide como siempre, por la franja o la herencia). **Ninguna
    fila entra ni sale**: son exactamente las filas que la tabla ya daba, en
    el mismo orden y con la misma cabecera -- y con ella la misma firma y el
    mismo mapeo --; las filas-rótulo no eran datos. `None` si la tabla no trae
    ningún rótulo propio."""
    posicion = {id(fila): i for i, fila in enumerate(filas)}
    if not unica.filas or any(id(fila) not in posicion for fila in unica.filas):
        return None
    primera_de_datos = posicion[id(unica.filas[0])]
    rotulos_cabecera = [_etiqueta_de_lote(f) for f in filas[:primera_de_datos]]
    rotulos_cabecera = [r for r in rotulos_cabecera if r is not None]
    rotulo = rotulos_cabecera[-1] if rotulos_cabecera else ""
    tramos: list[tuple[str, list[FILA], int, int]] = []
    actual: list[FILA] = []
    inicio = primera_de_datos
    for fila in unica.filas:
        etiqueta = _etiqueta_de_lote(fila)
        if etiqueta is None:
            actual.append(fila)
            continue
        if actual:
            tramos.append((rotulo, actual, inicio, posicion[id(fila)]))
        rotulo, actual, inicio = etiqueta, [], posicion[id(fila)]
    if actual:
        tramos.append((rotulo, actual, inicio, posicion[id(actual[-1])] + 1))
    if not any(r for r, *_ in tramos):
        return None
    return [
        replace(
            unica,
            filas=datos,
            bbox=_bbox_de_filas(tabla, desde, hasta) if len(tramos) > 1 else unica.bbox,
            rotulo_de_lote=r,
        )
        for r, datos, desde, hasta in tramos
    ]


def _tablas_extraidas(
    tabla, pagina, presupuestos_declarados: tuple[Decimal, ...] = ()
) -> list[TablaExtraida]:
    """Las tablas de catálogo que salen de UNA tabla cruda de `pdfplumber`.
    Normalmente una, o ninguna si es espuria; varias cuando el cuadro mete
    todos sus lotes en la misma caja de tabla, un bloque por lote (ver
    `_bloques_por_fila_de_lote`)."""
    # `tabla.extract()` una sola vez para las dos vías: no es gratis, y esto
    # corre sobre cada tabla de cada página candidata de todo el corpus.
    filas = tabla.extract()
    unica = _tabla_extraida(tabla, pagina, presupuestos_declarados, filas)
    if unica is not None:
        # La partición por lotes se prueba SOLO cuando ninguna de las vías de
        # siempre acepta la tabla: así no puede quitar ni una fila de las que
        # ya salen (su propia garantía aritmética sí descarta las que ella
        # misma recupera, `descartar_bloques_de_lote_que_no_cuadran`). Una
        # tabla aceptada solo se parte por los rótulos de lote de sus propias
        # filas, sin quitar ni añadir ninguna (sesión 2026-09-21, tercera
        # parte, `_partir_tabla_aceptada_por_rotulos`).
        return _partir_tabla_aceptada_por_rotulos(tabla, filas, unica) or [unica]
    if filas and not _es_modelo_de_oferta_en_blanco(filas):
        bloques = _bloques_por_fila_de_lote(filas, presupuestos_declarados)
        if bloques is not None:
            return [
                TablaExtraida(
                    cabecera=_combinar_filas_cabecera([cabecera]),
                    filas=datos,
                    pagina=pagina.page_number,
                    # Cada bloque con SU propia caja, no la de la tabla entera:
                    # la etapa 3.5 avanza de arriba abajo y dos tablas con la
                    # misma caja le dejan una franja de altura negativa.
                    bbox=_bbox_de_filas(tabla, inicio, fin),
                    columnas_x=_columnas_x(tabla),
                    titulo_propio=etiqueta,
                )
                for etiqueta, cabecera, datos, inicio, fin in bloques
            ]
    return []


def _tabla_extraida(
    tabla, pagina, presupuestos_declarados: tuple[Decimal, ...] = (),
    filas: Optional[list[FILA]] = None,
) -> Optional[TablaExtraida]:
    filas = tabla.extract() if filas is None else filas
    if not filas:
        return None
    if _es_modelo_de_oferta_en_blanco(filas):
        return None
    indice_datos = _indice_primera_fila_datos(filas)
    if indice_datos is None:
        datos = _filas_cuadro_sin_codigo(filas, presupuestos_declarados)
        if datos is None:
            # Última evidencia antes de darla por espuria: que la aritmética de
            # sus propias filas la demuestre (ver `_tripleta_que_cuadra`).
            demostrado = _cuadro_demostrado_por_aritmetica(filas)
            if demostrado is None:
                return None  # tabla espuria: ni código de precio ni cabecera de cuadro
            inicio_datos, filas_que_cuadran, columna_texto, referencias_recuperadas = demostrado
            return TablaExtraida(
                cabecera=_combinar_filas_cabecera(filas[:inicio_datos]),
                filas=filas_que_cuadran,
                pagina=pagina.page_number,
                bbox=tuple(tabla.bbox),
                columnas_x=_columnas_x(tabla),
                columna_referencia=None if columna_texto.es_designacion else columna_texto.indice,
                referencias_recuperadas=referencias_recuperadas,
            )
        return TablaExtraida(
            cabecera=_combinar_filas_cabecera(filas[:1]),
            filas=datos,
            pagina=pagina.page_number,
            bbox=tuple(tabla.bbox),
            columnas_x=_columnas_x(tabla),
        )
    recuperada = _fila_con_el_codigo_en_la_cabecera(filas, indice_datos)
    if recuperada is not None:
        indice_fila, columna, codigo = recuperada
        fila = list(filas[indice_fila])
        fila[columna] = codigo
        # El código sale también de la celda de cabecera: es de la fila, no
        # del rótulo de la columna, y dejarlo cambiaría la firma de la cabecera.
        cabecera = [
            [
                _CODIGO_AL_FINAL_RE.sub("", re.sub(r"\s+", " ", c)).strip() if i == columna and c else c
                for i, c in enumerate(f)
            ]
            for f in filas[:indice_fila]
        ]
        return TablaExtraida(
            cabecera=_combinar_filas_cabecera(cabecera),
            filas=[fila] + filas[indice_datos:],
            pagina=pagina.page_number,
            bbox=tuple(tabla.bbox),
            columnas_x=_columnas_x(tabla),
            codigos_recuperados=(codigo,),
        )
    return TablaExtraida(
        cabecera=_combinar_filas_cabecera(filas[:indice_datos]),
        filas=filas[indice_datos:],
        pagina=pagina.page_number,
        bbox=tuple(tabla.bbox),
        columnas_x=_columnas_x(tabla),
    )


def extraer_tablas_pagina(
    pagina, presupuestos_declarados: tuple[Decimal, ...] = ()
) -> list[TablaExtraida]:
    """`pagina` es un objeto página de `pdfplumber` (ya abierto por el
    llamador, que también es quien decide qué páginas son candidatas —
    etapa 3).

    `presupuestos_declarados`: los importes de licitación que el sistema ya
    tiene publicados y trazados para este expediente y sus lotes. Solo se
    usan para la demostración aritmética de un cuadro cuyos precios vienen
    sin decimales ni símbolo (ver `_precios_demostrados_por_un_total`);
    ninguna otra decisión de esta etapa los mira."""
    resultado: list[TablaExtraida] = []
    descartadas: list[tuple] = []
    for tabla in pagina.find_tables():
        extraidas = _tablas_extraidas(tabla, pagina, presupuestos_declarados)
        if extraidas:
            resultado.extend(extraidas)
        elif len(tabla.rows) >= 2:
            descartadas.append(tuple(tabla.bbox))
    if not descartadas:
        return resultado
    recuperadas = [
        extraida
        for tabla in pagina.find_tables(_AJUSTES_SEGUNDO_INTENTO)
        if any(_solapan(tuple(tabla.bbox), d) for d in descartadas)
        and not any(_solapan(tuple(tabla.bbox), t.bbox) for t in resultado)
        for extraida in _tablas_extraidas(tabla, pagina, presupuestos_declarados)
    ]
    if not recuperadas:
        return resultado
    # En su sitio de arriba abajo: `app.extraccion.lote_tabla` busca la
    # cabecera "LOTE N" en la franja entre una tabla y la anterior.
    return sorted(resultado + recuperadas, key=lambda t: (t.bbox[1], t.bbox[0]))
