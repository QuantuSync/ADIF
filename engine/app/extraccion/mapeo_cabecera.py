"""Etapa 5 de la cascada de extracción (CONTEXTO.md sección 5 y 6): traducir
una cabecera de tabla al esquema del catálogo. El modelo es el último
recurso, no el primero — antes se intenta un mapeo determinista por
coincidencia de nombres de cabecera conocidos, y solo si eso falla se llama
al modelo, una vez por firma de cabecera, con el resultado cacheado en
`cache_mapeo_cabecera` para no volver a preguntarlo nunca (CONTEXTO.md sección
6: "Si no, una llamada, guardas el mapeo, y no vuelves a preguntarlo nunca").

CONTEXTO.md sección 3: "11 variantes distintas [de cabecera] en solo 7
documentos [...] columnas fantasma vacías que desplazan los índices, y
alguna cabecera corrompida por la extracción" — el mapeo determinista falla
a propósito (y cae al modelo) ante cualquier ambigüedad, en vez de adivinar.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.catalogo import CAMPO_IMPORTE, _CODIGO_PRECIO_VALIDO_RE
from app.extraccion.firma_cabecera import calcular_firma_cabecera
from app.extraccion.firma_estructural import clasificar_columnas, tiene_forma_de_matricula
from app.extraccion.normalizacion import limpiar_codigo_celda
from app.extraccion.texto import normalizar
from app.interfaces.model_provider import ModelProvider
from app.models import MapeoCabeceraCache

CAMPOS = ("codigo_precio", "matricula", "descripcion", "unidad_medida", "cantidad", "precio_unitario")
CAMPOS_OBLIGATORIOS = ("descripcion", "precio_unitario")
CAMPOS_IDENTIFICADORES = ("codigo_precio", "matricula")

_ALIAS_DETERMINISTAS: dict[str, tuple[str, ...]] = {
    "codigo_precio": ("codigo de precio", "codigo del precio", "codigo del elemento", "codigo"),
    "matricula": ("matricula", "no matricula", "n matricula"),
    "descripcion": ("descripcion",),
    "unidad_medida": ("unidad de medida", "unidad", "unidades"),
    "cantidad": (
        "cantidades estimadas de referencia",
        "cantidad estimada de referencia",
        "cantidad",
        "cantidades",
        # Bloque 2, sesión 2026-09-19 (quinta parte): "MEDICIÓN" es el tercer
        # nombre que el corpus da a la columna de cantidad, y
        # `app.extraccion.tabla` y `app.extraccion.localizador` ya lo tratan
        # como tal desde 2026-09-15 -- el vocabulario de este módulo se había
        # quedado sin él, así que una cabecera perfectamente legible
        # ("SUMINSTRO CODIGO | DESCRIPCIÓN | UNIDAD | MEDICIÓN | Precio
        # Unitario | IMPORTE", `4.26/28510.0031` p.8) resolvía determinista
        # con `cantidad` a `None` y la cantidad se perdía.
        "medicion",
    ),
    "precio_unitario": (
        "precio unitario de referencia",
        "precio de referencia del elemento",
        "precio de referencia",
        "precio unitario",
        "precio",
    ),
}


@dataclass(frozen=True)
class ResultadoMapeoCabecera:
    mapeo: dict[str, Optional[int]]
    firma: str
    origen: str  # "cache" | "determinista" | "modelo"
    llamada_modelo: bool


def intentar_mapeo_determinista(cabecera: list[Optional[str]]) -> Optional[dict[str, Optional[int]]]:
    """Asignación voraz por especificidad: una columna como "CÓDIGO PRECIO"
    contiene a la vez el alias de `codigo_precio` ("codigo") y el de
    `precio_unitario` ("precio") — descartar el mapeo entero por ese empate
    tiraría cabeceras perfectamente legibles al modelo. En vez de eso, se
    reúnen todos los aciertos (campo, columna, longitud del alias) de todas
    las columnas a la vez y se reparten en orden de alias más largo (más
    específico) primero: un alias de 30 caracteres como "precio unitario de
    referencia" gana su columna antes de que el alias genérico "precio" de
    6 caracteres tenga ocasión de reclamar la columna equivocada. Cada campo
    y cada columna se usan como mucho una vez."""
    normalizados = [normalizar(c) if c else "" for c in cabecera]

    candidatos = sorted(
        (
            (len(alias), campo, indice)
            for indice, texto in enumerate(normalizados)
            if texto  # columna fantasma vacía: nunca es candidata
            for campo, alias_lista in _ALIAS_DETERMINISTAS.items()
            for alias in alias_lista
            if alias in texto
        ),
        key=lambda c: c[0],
        reverse=True,
    )

    campo_a_columna: dict[str, int] = {}
    columnas_usadas: set[int] = set()
    for _, campo, indice in candidatos:
        if campo in campo_a_columna or indice in columnas_usadas:
            continue
        campo_a_columna[campo] = indice
        columnas_usadas.add(indice)

    tiene_obligatorios = all(campo in campo_a_columna for campo in CAMPOS_OBLIGATORIOS)
    tiene_identificador = any(campo in campo_a_columna for campo in CAMPOS_IDENTIFICADORES)
    if not (tiene_obligatorios and tiene_identificador):
        return None

    mapeo = {campo: campo_a_columna.get(campo) for campo in CAMPOS}
    columna_codigo_material = _columna_codigo_material(normalizados, columnas_usadas)
    if columna_codigo_material is not None:
        mapeo[CAMPO_CODIGO_MATERIAL] = columna_codigo_material
    return mapeo


# Sesión 2026-09-14, decisión del cliente tras revisar el Excel: cuando el
# propio documento trae una columna con el TIPO de pieza de cada fila, eso es
# el "Código del material" del catálogo -- literal del documento, no derivado
# de la descripción (`app.extraccion.codigo_material`, que sigue siendo la
# vía para todas las tablas sin esa columna). Verificado contra el corpus
# real: la única forma existente es la columna "REPUESTO" de los criterios
# técnicos de repuestos de aparatos de vía (`6.21/28510.0109_ANEJO_
# 7bfc92005f43e68e.pdf` y los dos CONTRATO de la familia `6.21/28510.0108`,
# "Semicambio", "Aguja", "Cruzamiento obtuso"...). Coincidencia EXACTA del
# nombre de columna, nunca "contiene": "repuesto" dentro de otro nombre
# ("PRECIO DEL REPUESTO") no es esta columna, y el reparto voraz de arriba
# por longitud de alias le robaría su columna a `precio_unitario`. Campo
# opcional, fuera de `CAMPOS`: el modelo nunca lo ve ni lo devuelve (cambiar
# su esquema invalidaría todas las respuestas ya cacheadas sin ningún
# beneficio -- esta columna solo existe con cabecera legible).
CAMPO_CODIGO_MATERIAL = "codigo_material"
# Sesión 2026-09-17: "TIPO DE TRAVIESA*" es la segunda forma real
# (`6.24/28510.0094`/`0175`/`0176`/`0177`, "SURFV / PRBA / PRFV"); la llamada
# de nota ("*") no forma parte del nombre. En esa tabla la misma columna es
# también la descripción (no hay otra), así que puede compartirla con
# `descripcion`, nunca con otro campo.
_NOMBRES_COLUMNA_CODIGO_MATERIAL = frozenset({"repuesto", "tipo de traviesa"})


def _columna_codigo_material(normalizados: list[str], columnas_usadas: set[int]) -> Optional[int]:
    candidatas = [
        indice
        for indice, texto in enumerate(normalizados)
        if texto.rstrip("* ") in _NOMBRES_COLUMNA_CODIGO_MATERIAL and indice not in columnas_usadas
    ]
    return candidatas[0] if len(candidatas) == 1 else None


def completar_columna_codigo_material(
    cabecera: list[Optional[str]], mapeo: dict[str, Optional[int]]
) -> dict[str, Optional[int]]:
    """La columna de tipo de pieza para un mapeo que no la trae: el de la
    caché de antes de esta columna, o el del modelo (que nunca la ve, ver
    arriba). No se guarda en la caché: se recalcula desde la cabecera."""
    if mapeo.get(CAMPO_CODIGO_MATERIAL) is not None:
        return mapeo
    normalizados = [normalizar(c) if c else "" for c in cabecera]
    usadas = {col for campo, col in mapeo.items() if col is not None and campo != "descripcion"}
    columna = _columna_codigo_material(normalizados, usadas)
    if columna is None:
        return mapeo
    return {**mapeo, CAMPO_CODIGO_MATERIAL: columna}


_ESQUEMA_MAPEO = {
    "type": "object",
    "properties": {campo: {"type": ["integer", "null"]} for campo in CAMPOS},
    "required": list(CAMPOS),
    "additionalProperties": False,
}


def _construir_prompt(cabecera: list[Optional[str]], filas_ejemplo: list[list[Optional[str]]]) -> str:
    columnas = "\n".join(f"  {i}: {repr(valor)}" for i, valor in enumerate(cabecera))
    ejemplos = "\n".join(f"  {fila}" for fila in filas_ejemplo)
    return (
        "Esta es la cabecera de una tabla de precios unitarios de un contrato público español "
        "(cuadro de precios de un anejo o pliego). Cada columna está numerada desde 0.\n\n"
        f"Columnas:\n{columnas}\n\n"
        f"Primeras filas de ejemplo (mismo orden de columnas, solo para desambiguar — no las repitas):\n{ejemplos}\n\n"
        "Devuelve, para cada uno de estos campos del esquema del catálogo, el índice de columna que le "
        "corresponde, o null si esa tabla no trae ese campo:\n"
        "- codigo_precio: identificador de la línea dentro del documento (forma 'P-001').\n"
        "- matricula: código de 9 dígitos del artículo en ADIF (puede no estar presente).\n"
        "- descripcion: descripción del material o servicio.\n"
        "- unidad_medida: unidad de medida (ud, dm3, PA, ...).\n"
        "- cantidad: cantidad estimada de referencia.\n"
        "- precio_unitario: precio unitario o de referencia del elemento."
    )


def _mapear_con_modelo(
    cabecera: list[Optional[str]],
    filas_ejemplo: list[list[Optional[str]]],
    model_provider: ModelProvider,
) -> dict[str, Optional[int]]:
    prompt = _construir_prompt(cabecera, filas_ejemplo[:3])
    mapeo = model_provider.completar(prompt, esquema=_ESQUEMA_MAPEO)
    if isinstance(mapeo, str):
        mapeo = json.loads(mapeo)
    return {campo: mapeo.get(campo) for campo in CAMPOS}


def obtener_mapeo_cacheado(db: Session, firma: str) -> Optional[MapeoCabeceraCache]:
    return db.query(MapeoCabeceraCache).filter_by(firma=firma).one_or_none()


def guardar_mapeo_cacheado(
    db: Session, firma: str, cabecera: list[Optional[str]], mapeo: dict[str, Optional[int]], origen: str
) -> MapeoCabeceraCache:
    entrada = MapeoCabeceraCache(firma=firma, cabecera=list(cabecera), mapeo=mapeo, origen=origen)
    db.add(entrada)
    db.commit()
    db.refresh(entrada)
    return entrada


def cabecera_sin_senal(cabecera: list[Optional[str]]) -> bool:
    """Verdadero cuando `cabecera` no trae ningún texto real (todas las
    celdas `None` o en blanco) -- caso real de esta sesión (verificación del
    Excel exportado, 2026-09-08): `app.extraccion.tabla.extraer_tablas_pagina`
    puede no encontrar ninguna fila de cabecera antes de la primera fila de
    datos (cuando esa primera fila ya trae un valor con forma de matrícula,
    típico de una tabla que continúa de la página anterior sin repetir su
    cabecera), y devuelve `[]`.

    Una cabecera así NUNCA es un signo estable de "esta misma tabla, vista
    otra vez": `calcular_firma_cabecera` hashea la cadena vacía igual para
    CUALQUIER tabla sin cabecera detectada, sin importar qué columnas traiga
    de verdad. Cachear y reutilizar el mapeo del modelo bajo esa firma
    aplicaba a ciegas el mapeo aprendido de la PRIMERA tabla sin cabecera del
    corpus a todas las demás -- verificado contra datos reales: la firma de
    cadena vacía (`e3b0c44...`) tenía un único mapeo cacheado
    (`matricula`/`descripcion`/`codigo_precio` de la tabla de
    `6.24/28510.0184`), reaplicado sin más a `6.24/28510.0209` con columnas
    en un orden distinto -- produjo líneas de catálogo sin descripción, sin
    matrícula y sin código de expediente cruzado, exactamente "una línea sin
    expediente" que no debería poder guardarse. Nunca se cachea ni se
    reutiliza esta firma degenerada: cada tabla sin cabecera detectada pide
    su propio mapeo al modelo, usando solo sus filas de ejemplo."""
    return not any(c and c.strip() for c in cabecera)


_UMBRAL_COHERENCIA = 0.5


def evaluar_coherencia_mapeo(
    mapeo: dict[str, Optional[int]], filas: list[list[Optional[str]]]
) -> Optional[str]:
    """Bloque 2 (auditoría de `6.20/28510.0042`/`0046`/`0047`, 51 grupos
    duplicados y 207 líneas sin descripción): solo se aplica a un mapeo de
    modelo sobre una tabla `cabecera_sin_senal` -- sin nombres de columna
    que lo anclen, un modelo pequeño guiado solo por 2-3 filas de ejemplo
    (`_mapear_con_modelo`) puede devolver un índice que no corresponde al
    campo real. Verificado contra el PDF real de `6.20/28510.0047`
    (`ANEJO_abd69efbdd39b552.pdf` p.27): la tabla trae 5 columnas reales
    (matrícula, designación, plano, norma técnica, precio) sin cabecera
    propia -- el modelo, sin más pista que 3 filas, mapeó `descripcion` a
    una columna vacía en el 100% de las filas reales de esa tabla y
    `cantidad` a la columna de la norma técnica ("03.360.101.4" leído como
    33601014).

    Se valida contra TODAS las filas de la tabla, no solo las 2-3 que vio
    el modelo -- las de ejemplo pueden ser, por azar, las únicas donde el
    mapeo sí cuadra. Solo se comprueban los dos campos obligatorios del
    catálogo (`CAMPOS_OBLIGATORIOS`): si el modelo hubiera acertado, ambos
    deberían traer valor real en la inmensa mayoría de las filas -- ningún
    cuadro de precios legítimo del corpus tiene una `descripcion` o un
    `precio_unitario` mayoritariamente vacíos.

    El umbral de vacío no basta por sí solo -- verificado contra otras tablas
    reales del mismo documento (p.27, 29, 35, 42 de `ANEJO_abd69efbdd39b552.
    pdf`): el mismo desplazamiento de una columna (matrícula->codigo_precio,
    designación->matrícula, PLANO->descripcion) deja `descripcion` apuntando
    a la columna "Plano" (referencias de plano tipo "P16.0739.04"), que por
    azar del documento está rellena en más de la mitad de las filas -- pasa
    el umbral de vacío sin ser una descripción real. Por eso se añade una
    segunda comprobación, sobre `matricula` si el mapeo la asigna: sus
    valores no vacíos deben parecer matrículas de verdad (`_MATRICULA_VALIDA_
    RE`, CONTEXTO.md sección 2, 9 dígitos) en la mayoría de las filas -- una
    matrícula real puede faltar en muchas filas (no es clave, sección 2),
    pero cuando trae valor nunca es texto libre como "CUPON MIXTO...". Este
    desplazamiento concreto pone justo ese texto libre en la columna que el
    mapeo cree que es `matricula`, y lo detecta aunque `descripcion` haya
    colado el umbral de arriba. Devuelve el motivo si resulta incoherente, o
    `None` si el mapeo pasa la comprobación."""
    if not filas:
        return None
    total = len(filas)
    for campo in CAMPOS_OBLIGATORIOS:
        indice = mapeo.get(campo)
        if indice is None:
            if campo == "precio_unitario" and "precio" not in clasificar_columnas(filas):
                # Bloque 2, sesión 2026-09-12 (continuación,
                # `corregir_confusion_precio_cantidad`): ninguna columna de
                # esta tabla tiene forma de precio real -- confirmado por
                # contenido, no solo "el modelo no encontró ninguna" -- así
                # que la ausencia de `precio_unitario` es un hecho del
                # documento (esta tabla no declara precio para su material,
                # verificado contra `6.24/28510.0184_CONTRATO_
                # b15b77d1fff4f23f.pdf`, tabla de equipamiento con "Precio
                # Referencia Adquisición/Reparación" siempre en blanco), no
                # un fallo de mapeo que deba descartar la tabla entera. Si
                # SÍ existiera una columna con forma de precio en algún
                # sitio, `clasificar_columnas` la habría encontrado y este
                # atajo no se toma -- la comprobación de abajo sigue
                # protegiendo ese caso real (`6.20/28510.0042`/`0046`/`0047`).
                continue
            return f"{campo} sin columna asignada por el modelo en una tabla sin cabecera propia"
        con_valor = sum(
            1 for fila in filas if indice < len(fila) and fila[indice] and fila[indice].strip()
        )
        if con_valor / total < _UMBRAL_COHERENCIA:
            return (
                f"{campo} vacío en la mayoría de las filas de la tabla "
                f"({con_valor}/{total}) tras aplicar el mapeo del modelo sobre cabecera sin señal"
            )

    indice_matricula = mapeo.get("matricula")
    if indice_matricula is not None:
        valores = [
            fila[indice_matricula].strip()
            for fila in filas
            if indice_matricula < len(fila) and fila[indice_matricula] and fila[indice_matricula].strip()
        ]
        if valores:
            con_forma_valida = sum(
                1 for valor in valores if tiene_forma_de_matricula(valor)
            )
            if con_forma_valida / len(valores) < _UMBRAL_COHERENCIA:
                return (
                    "matricula con valores que no tienen forma de matrícula "
                    f"({con_forma_valida}/{len(valores)} con 9 dígitos) tras aplicar el mapeo del "
                    "modelo sobre cabecera sin señal -- probablemente apunta a otra columna"
                )
    return None


def _buscar_columna_codigo_precio(
    filas: list[list[Optional[str]]], excluir: set[int]
) -> Optional[int]:
    """Entre las columnas no reclamadas por otro campo, la que tenga forma
    real de código de precio (`_CODIGO_PRECIO_VALIDO_RE`, los mismos formatos
    ya verificados contra el corpus en `app.catalogo`: "P-001", "COD0001",
    "L9-T12"...) en casi todos sus valores no vacíos. Nunca el patrón laxo
    "bare" (1-4 dígitos sueltos, válido solo bajo una cabecera real que diga
    "PARTIDA"): sin cabecera, un número corto suelto es demasiado ambiguo
    (podría ser una cantidad) para usarlo como señal de identidad. Devuelve
    `None` si ninguna columna encaja, o si más de una lo hace (ambiguo -- no
    se adivina cuál es la buena)."""
    candidatas = []
    for indice in range(max((len(f) for f in filas), default=0)):
        if indice in excluir:
            continue
        valores = [
            fila[indice].strip() for fila in filas if indice < len(fila) and fila[indice] and fila[indice].strip()
        ]
        if not valores:
            continue
        con_forma = sum(1 for v in valores if _CODIGO_PRECIO_VALIDO_RE.match(v.replace(" ", "")))
        if con_forma / len(valores) >= _UMBRAL_COHERENCIA:
            candidatas.append(indice)
    if len(candidatas) == 1:
        return candidatas[0]
    return None


def derivar_mapeo_por_contenido(filas: list[list[Optional[str]]]) -> Optional[dict[str, Optional[int]]]:
    """Bloque 3, sesión 2026-09-11 (CONTEXTO.md, defecto de la tabla sin
    cabecera de `6.20/28510.0042`/`0046`/`0047`): antes de preguntarle al
    modelo la identidad de cada columna de una tabla sin cabecera, se intenta
    derivarla del CONTENIDO -- verificado en vivo que el modelo, sobre esta
    forma concreta de tabla (matrícula, descripción, referencia de plano,
    referencia normativa, precio -- sin ninguna columna de código de precio),
    devuelve una permutación de columnas DISTINTA en llamadas sucesivas con
    las mismas filas de ejemplo: `codigo_precio`↔columna de matrícula en un
    intento, `codigo_precio` y `matricula` a la misma columna en otro,
    `matricula`↔`descripcion` desplazadas un puesto en un tercero. No hay un
    único error que corregir -- parchear cada forma observada persigue un
    objetivo que se mueve. `app.extraccion.firma_estructural.
    clasificar_columnas` ya clasifica cada columna por su contenido de forma
    determinista (mismo resultado siempre, sin llamar a nada): reutilizarla
    aquí elimina la pregunta al modelo en el caso donde menos fiable es.

    Encargo explícito de esta sesión -- nunca se adivina sobre una
    clasificación ambigua, la línea va a revisión, no aquí: se exige
    exactamente una columna `matricula` (o ninguna, una tabla puede no
    traerla), exactamente una `precio`, y exactamente una `texto_unico` (la
    descripción) -- si hay cero o más de una de cualquiera de ellas, o si no
    hay ninguna columna de precio ni ningún identificador (ni matrícula ni
    código de precio), se devuelve `None` y el llamador sigue con el camino
    de siempre (modelo + `evaluar_coherencia_mapeo`, que en el peor caso
    excluye la tabla del Excel en vez de contaminarlo)."""
    if not filas:
        return None
    tipos = clasificar_columnas(filas)

    indices_matricula = [i for i, t in enumerate(tipos) if t == "matricula"]
    indices_precio = [i for i, t in enumerate(tipos) if t == "precio"]
    indices_descripcion = [i for i, t in enumerate(tipos) if t == "texto_unico"]

    if len(indices_matricula) > 1 or len(indices_precio) != 1 or len(indices_descripcion) != 1:
        return None

    matricula_idx = indices_matricula[0] if indices_matricula else None
    descripcion_idx = indices_descripcion[0]
    precio_idx = indices_precio[0]

    codigo_precio_idx = _buscar_columna_codigo_precio(
        filas, excluir={i for i in (matricula_idx, descripcion_idx, precio_idx) if i is not None}
    )

    if matricula_idx is None and codigo_precio_idx is None:
        # Sin ningún identificador de línea (ni matrícula ni código de
        # precio): mismo criterio que `intentar_mapeo_determinista`
        # (CAMPOS_IDENTIFICADORES) -- sin esto no hay nada que ancle la fila,
        # mejor no derivar nada que inventar una identidad.
        return None

    return {
        "codigo_precio": codigo_precio_idx,
        "matricula": matricula_idx,
        "descripcion": descripcion_idx,
        "unidad_medida": None,
        "cantidad": None,
        "precio_unitario": precio_idx,
    }


# Bloque 2, sesión 2026-09-12 (continuación): sobre una tabla sin cabecera
# propia, el modelo puede asignar `precio_unitario` a una columna que no
# tiene forma de precio real -- verificado contra `6.24/28510.0184_CONTRATO_
# b15b77d1fff4f23f.pdf` p.97-98 (equipamiento de telecomunicaciones,
# "REFERENCIAS PARA SUMINISTRAR Y/O REPARAR..."): la tabla trae dos columnas
# de precio de referencia (adquisición/reparación) que el documento deja
# SIEMPRE en blanco, y una columna "Cantidad Estimada" con el mismo valor
# repetido ("1") en cada fila -- sin más pista que 2-3 filas de ejemplo, el
# modelo mapeó `precio_unitario` a esa columna de cantidad, produciendo un
# "precio" de 1,00 € idéntico en las 57 líneas de esta tabla, en vez de
# reconocer que el documento no declara ningún precio para este material.
# `evaluar_coherencia_mapeo` no lo detectaba porque solo comprueba que la
# columna tenga ALGÚN valor no vacío en la mayoría de las filas -- una
# columna de cantidad rellena al 100% pasa esa comprobación con la misma
# facilidad que un precio real.
#
# Corrección determinista sobre el MAPEO, mismo patrón que
# `corregir_confusion_matricula_codigo_precio`: si la columna que el mapeo
# cree que es `precio_unitario` no tiene forma de precio real según
# `clasificar_columnas` (que ya usa la gramática monetaria estricta de
# `_parece_precio`, bloque 7), se descarta esa asignación -- `precio_unitario`
# queda `None` (esta fila no trae un precio interpretable en esa columna) en
# vez de dejar pasar un valor que con certeza no es un precio. Nunca al
# revés: una columna que SÍ tiene forma de precio nunca se toca aquí, aunque
# `evaluar_coherencia_mapeo` la acabe rechazando por otro motivo.
def corregir_confusion_precio_cantidad(
    mapeo: dict[str, Optional[int]], filas: list[list[Optional[str]]]
) -> dict[str, Optional[int]]:
    indice_precio = mapeo.get("precio_unitario")
    if indice_precio is None:
        return mapeo
    tipos = clasificar_columnas(filas)
    if indice_precio < len(tipos) and tipos[indice_precio] == "precio":
        return mapeo
    corregido = dict(mapeo)
    corregido["precio_unitario"] = None
    return corregido


def completar_matricula_por_contenido(
    mapeo: dict[str, Optional[int]], filas: list[list[Optional[str]]]
) -> dict[str, Optional[int]]:
    """Sesión 2026-09-14 (`6.25/28510.0251_ANEJO_1f2691ba90da3138.pdf` p.23,
    `6.25/28510.0213_ANEJO_ce2a25e8e58ae967.pdf` p.23): la columna de
    matrícula se llama "CÓDIGO ADIF" -- ningún alias determinista de
    `matricula` la reconoce ("codigo" ya lo ha reclamado "CÓDIGO DE
    PRECIO"), así que el mapeo cacheado la deja sin asignar aunque el 100% de
    sus valores sean matrículas de 9 dígitos ("594200000", "591000065"...).
    Con `matricula` sin columna, si hay EXACTAMENTE una columna que ningún
    otro campo reclama y cuyo contenido es de matrícula
    (`clasificar_columnas`, mismo criterio que la derivación por contenido),
    se le asigna. Con cero o más de una, no se adivina."""
    if mapeo.get("matricula") is not None or not filas:
        return mapeo
    reclamadas = {indice for indice in mapeo.values() if indice is not None}
    candidatas = [
        indice for indice, tipo in enumerate(clasificar_columnas(filas))
        if tipo == "matricula" and indice not in reclamadas
    ]
    if len(candidatas) != 1:
        return mapeo
    completado = dict(mapeo)
    completado["matricula"] = candidatas[0]
    return completado


def _columna_parece_codigo_precio(indice: int, filas: list[list[Optional[str]]]) -> bool:
    """Todas las líneas de todas las celdas no vacías de la columna tienen
    forma de código de precio. Se mira línea a línea porque el caso que
    motiva esto es justamente una celda con varias ("P-1", "P-2", "P-3" y
    "P-4" en la misma celda: cuatro artículos que `pdfplumber` funde en una
    sola fila). Se exige el 100 %: una columna de códigos de precio real no
    trae nada más."""
    lineas = [
        trozo.strip()
        for fila in filas
        if indice < len(fila) and fila[indice]
        for trozo in fila[indice].splitlines()
        if trozo.strip()
    ]
    if not lineas:
        return False
    return all(_CODIGO_PRECIO_VALIDO_RE.match(limpiar_codigo_celda(l) or "") for l in lineas)


def completar_codigo_precio_por_contenido(
    mapeo: dict[str, Optional[int]], filas: list[list[Optional[str]]]
) -> dict[str, Optional[int]]:
    """Simétrica de `completar_matricula_por_contenido`, y el arreglo del
    pendiente antiguo de `6.21/28510.0152` p.114 (rodillos de aguja).

    Su cabecera llama a la columna de códigos **"CODIFICACIÓN DEL PRECIO"**:
    no casa con ningún alias determinista de `codigo_precio` ("codificacion"
    no contiene "codigo") y el modelo, que resuelve esa firma, la deja sin
    asignar. Sin `codigo_precio`, `app.catalogo._dividir_fila_multiple` no
    puede separar la fila que `pdfplumber` funde -- "P-1", "P-2", "P-3",
    "P-4" en una sola celda, cuatro artículos con sus cuatro matrículas,
    cantidades y precios -- y los
    cuatro quedan en una sola línea ilegible.

    **Por qué no se arregla con un alias**, que es lo que se probó y se
    revirtió en la sesión de expedientes sin publicar (guarda
    `test_mapeo_determinista_no_reconoce_codificacion_del_precio`): añadir
    "codificacion del precio" hace que el mapeo DETERMINISTA resuelva esa
    firma y, con ello, que el cuadro de balasto multi-lote deje de ir al
    modelo -- y ahí el determinista se equivoca, porque solo mira la posición
    en la cabecera y esa tabla tiene una columna fantasma desplazada de forma
    distinta entre cabecera y datos. La corrección tenía que mirar los DATOS,
    no el nombre de la columna; eso es lo que hace esta función, después del
    mapeo y sin tocar por dónde se resolvió.

    Con `codigo_precio` sin columna, si hay EXACTAMENTE una columna que
    ningún otro campo reclama y en la que **todas** las líneas tienen forma
    de código de precio, se le asigna. Con cero o más de una, no se adivina.
    """
    if mapeo.get("codigo_precio") is not None or not filas:
        return mapeo
    reclamadas = {indice for indice in mapeo.values() if indice is not None}
    num_columnas = max(len(fila) for fila in filas)
    candidatas = [
        indice
        for indice in range(num_columnas)
        if indice not in reclamadas and _columna_parece_codigo_precio(indice, filas)
    ]
    if len(candidatas) != 1:
        return mapeo
    completado = dict(mapeo)
    completado["codigo_precio"] = candidatas[0]
    return completado


# Bloque 1, sesión 2026-09-19 (tercera parte), encargo del cliente sobre las
# cantidades que faltan. Causa raíz medida, no supuesta: en una tabla SIN
# cabecera propia (una página de continuación), el mapeo lo resuelve el modelo
# a partir de la cabecera vacía y 2-3 filas de ejemplo -- y si en esas 2-3
# filas la celda de cantidad está vacía (lo normal en un cuadro cuya
# "CANTIDAD ESTIMADA DE REFERENCIA" solo se rellena en unos pocos renglones),
# el modelo no reclama ninguna columna para `cantidad`. Con `cantidad` sin
# columna, `app.catalogo._recuperar_cantidad_columna_fantasma` **no llega a
# dispararse nunca** (exige que la cabecera SÍ declare el campo), así que el
# número queda en el PDF y la celda del Excel sale vacía con el motivo "no
# consta" -- un motivo falso: el documento sí la publica.
#
# Medido sobre `6.20/28510.0042`/`0046`/`0047` (doc `ANEJO_abd69efbdd39b552`,
# 61 páginas, 1.302 líneas): 1.222 líneas se construyen con el mapeo
# `{'cantidad': None, 'matricula': 0, 'descripcion': 1, 'precio_unitario': 4}`
# mientras la p.3, que SÍ trae cabecera, la declara en el índice 6
# ("Cantidad estimada de referencia"). Segundo caso real, misma forma:
# `6.22/28510.0125`/`0126` (doc `ANEJO_57694f5d5dacb236`), cuya p.15 declara
# "CANTIDADES ESTIMADAS DE REFERENCIA" y cuyas páginas 16-20 la pierden al
# cambiar el número de columnas.
#
# **La certeza es del propio documento, no de una heurística sobre el
# contenido**: esta función solo se llama cuando otra tabla DEL MISMO
# DOCUMENTO declaró una columna de cantidad en su cabecera
# (`cantidad_declarada_en_el_documento`). Sin esa declaración no se completa
# nada: una columna de enteros pequeños suelta podría ser cualquier cosa (el
# radio de un aparato de vía, el peso en toneladas, un número de partida), y
# esos tres casos existen de verdad en el corpus -- `6.21/28510.0108`-`0111`
# p.5/p.17 traen "PESO en toneladas" y "17.000"/"10.000" de tipología, y su
# documento NUNCA declara cantidad, así que aquí no entra.
#
# `_UMBRAL_RELLENO_MINIMO` de `clasificar_columnas` no sirve para esto: la
# columna que se busca está vacía en el 95 % de sus filas por diseño del
# propio cuadro. De ahí el predicado propio, y de ahí que exija el **100 %**
# de sus valores no vacíos con forma de cantidad pequeña: sin separador de
# miles (que dejaría entrar "03.361.140.1" y "17.000"), sin el símbolo de
# euro, sin letras y con cuatro dígitos enteros como máximo (una matrícula
# tiene 8 o 9).
#
# **Y sin decimales.** La primera versión aceptaba "3,3" y el reproceso
# completo demostró que eso no vale: en el anejo de criterios de
# `6.21/28510.0108`-`0111` alguna de sus tablas CON cabecera acaba con
# `cantidad` mapeada (el modelo se lo asigna por las filas de ejemplo, aunque
# ninguna cabecera del documento diga literalmente "cantidad"), así que la
# guarda de "el documento la declara" no lo protegía. Y en sus páginas 7 y 8
# la única columna que ningún campo reclama es el **PESO en toneladas** ("4",
# "3,3", "2,9"): cinco líneas por expediente se llenaron con el peso del
# aparato de vía como si fuera una cantidad de unidades. Una "cantidad estimada de referencia" de
# este corpus es un recuento entero (0, 1, 2, 3, 13, 32.000); un peso lleva
# decimales. Exigir enteros descarta esa columna por el "3,3" y deja pasar
# las que sí son cantidades. Es una restricción deliberada: si algún día
# aparece un cuadro con cantidades decimales en una tabla sin cabecera, esta
# vía no lo recuperará -- y es preferible a escribir un peso en la columna de
# cantidad.
_CANTIDAD_PEQUENA_RE = re.compile(r"^\d{1,4}$")


def _columna_parece_cantidad(indice: int, filas: list[list[Optional[str]]]) -> bool:
    valores = [
        fila[indice].strip()
        for fila in filas
        if indice < len(fila) and fila[indice] and fila[indice].strip()
    ]
    if not valores:
        return False
    return all(_CANTIDAD_PEQUENA_RE.match(v) for v in valores)


def completar_cantidad_por_contenido(
    mapeo: dict[str, Optional[int]],
    filas: list[list[Optional[str]]],
    cantidad_declarada_en_el_documento: bool,
) -> dict[str, Optional[int]]:
    """Hermana de `completar_matricula_por_contenido` y
    `completar_codigo_precio_por_contenido`, para `cantidad` -- ver el
    comentario de arriba para la causa raíz medida y por qué la certeza la
    da el propio documento.

    Con `cantidad` sin columna y el documento declarándola en otra de sus
    tablas, si hay **exactamente una** columna que ningún otro campo reclama
    y en la que **todos** los valores no vacíos tienen forma de cantidad
    pequeña, se le asigna. Con cero o más de una, no se adivina."""
    if not cantidad_declarada_en_el_documento:
        return mapeo
    if mapeo.get("cantidad") is not None or not filas:
        return mapeo
    reclamadas = {indice for indice in mapeo.values() if indice is not None}
    num_columnas = max(len(fila) for fila in filas)
    candidatas = [
        indice
        for indice in range(num_columnas)
        if indice not in reclamadas and _columna_parece_cantidad(indice, filas)
    ]
    if len(candidatas) != 1:
        return mapeo
    completado = dict(mapeo)
    completado["cantidad"] = candidatas[0]
    return completado


_TOLERANCIA_GEOMETRIA = 3.0


def heredar_mapeo_por_geometria(
    mapeo_origen: dict[str, Optional[int]],
    columnas_origen: tuple,
    columnas_destino: tuple,
) -> Optional[dict[str, Optional[int]]]:
    """Sesión 2026-09-14 (páginas de continuación del anejo `6.21/28510.0109_
    ANEJO_7bfc92005f43e68e.pdf` y del cuadro de precios `ANEJO_
    ce1df15b39efdb8c.pdf`, que ahora sí se abren -- ver `app.extraccion.
    localizador`): una tabla que continúa en la página siguiente no repite
    su cabecera, pero sus columnas caen exactamente en las mismas posiciones
    horizontales (verificado: las 8 columnas de la p.4 del anejo coinciden
    con las de la p.3 a menos de 1 punto). Reutilizar el mapeo de la tabla
    con cabecera por esa geometría es determinista y no pregunta nada al
    modelo -- a diferencia del intento retirado (docstring de más abajo, por
    NÚMERO de columnas, que no garantizaba la misma forma), aquí cada campo
    mapeado tiene que encontrar en la tabla nueva UNA sola columna con el
    mismo (x0, x1) de su columna de origen. Si algún campo no la encuentra, o
    encuentra más de una, no se hereda nada (`None`) y el llamador sigue por
    el camino de siempre. El llamador valida además el resultado contra las
    filas reales (`evaluar_coherencia_mapeo`) antes de usarlo."""
    if not columnas_origen or not columnas_destino:
        return None
    resultado: dict[str, Optional[int]] = {}
    for campo, indice in mapeo_origen.items():
        if indice is None:
            resultado[campo] = None
            continue
        if indice >= len(columnas_origen) or columnas_origen[indice] is None:
            return None
        x0, x1 = columnas_origen[indice]
        coincidencias = [
            j
            for j, columna in enumerate(columnas_destino)
            if columna is not None
            and abs(columna[0] - x0) <= _TOLERANCIA_GEOMETRIA
            and abs(columna[1] - x1) <= _TOLERANCIA_GEOMETRIA
        ]
        if len(coincidencias) != 1:
            return None
        resultado[campo] = coincidencias[0]
    return resultado


def _columna_parece_matricula(indice: int, filas: list[list[Optional[str]]]) -> bool:
    valores = [
        fila[indice].strip() for fila in filas if indice < len(fila) and fila[indice] and fila[indice].strip()
    ]
    if not valores:
        return False
    con_forma_matricula = sum(1 for v in valores if tiene_forma_de_matricula(v))
    return con_forma_matricula / len(valores) >= _UMBRAL_COHERENCIA


def _columna_vacia(indice: int, filas: list[list[Optional[str]]]) -> bool:
    """Ninguna fila trae valor real en esta columna -- distinto de "la
    matrícula falta en muchas filas" (legítimo, CONTEXTO.md sección 2): aquí
    es CERO, la huella de un nombre de cabecera desalineado con sus propios
    datos, no de una columna que a veces trae dato y a veces no."""
    return not any(indice < len(fila) and fila[indice] and fila[indice].strip() for fila in filas)


def _columna_sin_forma_de_matricula(indice: int, filas: list[list[Optional[str]]]) -> bool:
    """Ningún valor de la columna tiene forma de matrícula (9 dígitos) --
    cero, no "pocos": una columna de matrícula real puede traer huecos o
    algún valor ilegible, nunca ninguno bueno en toda la tabla."""
    return not any(
        indice < len(fila) and fila[indice] and tiene_forma_de_matricula(fila[indice].strip())
        for fila in filas
    )


def corregir_confusion_matricula_codigo_precio(
    mapeo: dict[str, Optional[int]], filas: list[list[Optional[str]]]
) -> dict[str, Optional[int]]:
    """Bloque 3, sesión 2026-09-11 (CONTEXTO.md, defecto de la tabla sin
    cabecera de `6.20/28510.0042`/`0046`/`0047`): sobre una tabla sin
    cabecera propia sin NINGUNA columna real de código de precio, el
    modelo, guiado solo por 2-3 filas de ejemplo, tiende a confundir la
    primera columna (un identificador numérico de 9 dígitos) con
    `codigo_precio` en vez de con `matricula` -- verificado contra
    `ANEJO_abd69efbdd39b552.pdf` p.35 (33 líneas reales de ese trío) en DOS
    variantes reales, ambas observadas reprocesando el documento real más de
    una vez (sin cabecera, cada reproceso vuelve a llamar al modelo -- ver
    `cabecera_sin_senal` -- así que puede tocar una variante distinta cada
    vez, no siempre la misma):

    1. `matricula` queda sin columna asignada y `codigo_precio` apunta a la
       columna 0 (la matrícula real).
    2. `matricula` Y `codigo_precio` apuntan a la MISMA columna 0 -- el
       modelo identifica la columna dos veces, una vez con cada nombre.

    En los dos casos la columna 0 es la matrícula real (`612260110`,
    `615250090`...), nunca un código de precio (que en esta tabla, verificado
    contra el PDF, no existe en absoluto) -- luego marcada "formato no
    reconocido en el corpus" por `app.catalogo._normalizar_codigo_precio"
    porque un número de 9 dígitos nunca encaja en `_CODIGO_PRECIO_VALIDO_RE`.
    Corrección determinista sobre el MAPEO, no sobre los datos: si la
    columna de `codigo_precio` tiene forma de matrícula
    (`_MATRICULA_VALIDA_RE`, 9 dígitos) en la mayoría de sus valores no
    vacíos -- mismo umbral que ya usa `evaluar_coherencia_mapeo` para el
    caso simétrico -- y `matricula` no apunta a OTRA columna distinta,
    `codigo_precio` queda `None` (esta tabla no trae identificador de línea
    propio) y `matricula` queda asignada a esa columna. Nunca al revés, y
    nunca si `matricula` ya tiene una columna PROPIA y distinta: ahí no hay
    confusión que resolver.

    Tercera variante, bloque 2, sesión 2026-09-12 (continuación) -- esta vez
    con cabecera real, no sin cabecera: `6.21/28510.0149_ANEJO_
    bd79fa987e814be3.pdf` p.6/9 (cabecera `[None, "Nº MATRÍCULA", None,
    "DESCRIPCIÓN", "CRITERIOS TECNICOS"]`). El nombre de columna "Nº
    MATRÍCULA" no está alineado con sus propios datos -- la matrícula real
    (`697100100`...) cae en la columna ANTERIOR, sin nombre, y la que el
    modelo/determinista etiquetan "matricula" por el texto de la cabecera
    está vacía en el 100% de las filas reales. `matricula` SÍ tiene "su
    propia columna, distinta de `codigo_precio`" en la forma del mapeo --
    la comprobación original de abajo la habría dejado intacta -- pero esa
    columna propia no trae ningún dato real: no es una matrícula legítima
    que de verdad falte en la mayoría de las filas (CONTEXTO.md sección 2),
    es la misma desalineación de cabecera-vs-datos ya conocida para otros
    campos (`_recuperar_descripcion_columna_fantasma` y compañía), aquí sin
    cubrir para `matricula`.

    Cuarta variante, sesión 2026-09-14 (`6.21/28510.0016_ANEJO_
    e40fc4e4546ec90b.pdf`, tornillería, cabecera en fuente sin mapa
    Unicode): el modelo pone `codigo_precio` en la columna de la matrícula
    real ("642190360") y `matricula` en la columna vecina "REF. ADIF"
    ("RT58", "Pa1", "AsEM8-20"). La columna de `matricula` no está vacía --
    la comprobación de la tercera variante no la ve --, pero ninguno de sus
    valores tiene forma de matrícula: es la misma confusión, con otra
    columna de relleno. Se trata igual que "vacía": una columna asignada a
    `matricula` sin NINGÚN valor con forma de matrícula no es una matrícula
    legítima que falte a veces (CONTEXTO.md sección 2), es otra columna.

    Zona de riesgo conocida, sin cubrir aquí: el modelo puede producir
    variantes distintas de estas (p.ej. `descripcion` sin columna en vez
    de `matricula`) en otro reproceso -- ver CONTEXTO.md para la vía
    estructural más robusta (derivar la columna de `matricula`/`precio_
    unitario` de `app.extraccion.firma_estructural.calcular_firma_
    estructural`, que ya las clasifica de forma determinista por contenido,
    en vez de fiarse del modelo para esta forma de tabla) si esto vuelve a
    aparecer con otra forma."""
    indice_codigo_precio = mapeo.get("codigo_precio")
    indice_matricula = mapeo.get("matricula")
    if indice_codigo_precio is None:
        return mapeo
    if (
        indice_matricula is not None
        and indice_matricula != indice_codigo_precio
        and not _columna_vacia(indice_matricula, filas)
        and not _columna_sin_forma_de_matricula(indice_matricula, filas)
    ):
        return mapeo
    if not _columna_parece_matricula(indice_codigo_precio, filas):
        return mapeo
    corregido = dict(mapeo)
    corregido["matricula"] = indice_codigo_precio
    corregido["codigo_precio"] = None
    return corregido


# Bloque 5, cambios del cliente tras revisar el catálogo (sesión 2026-09-09):
# se intentó aquí una función `heredar_mapeo_de_pagina_anterior` -- reutilizar
# el mapeo de la tabla anterior del mismo documento para una tabla sin
# ninguna cabecera propia, cuando coincidiera el número de columnas -- para
# que las páginas de continuación que `app.extraccion.localizador` ya sabe
# abrir (mismo bloque, ver su docstring) no revienten sin `model_provider`.
# Retirada tras verificarla contra el corpus real completo (no solo contra
# el caso que la motivó): dos tablas de `6.22/28510.0126_ANEJO_
# 57694f5d5dacb236.pdf` con el MISMO número de columnas (8) tenían formas
# distintas -- una con la descripción desplazada una columna, la otra sin
# desplazar -- así que heredar el mapeo de la primera para la segunda
# desplazaba silenciosamente cantidad/descripción, produciendo líneas
# corruptas (descripción = "UD.", cantidad idéntica al precio) detectadas
# por la propia auditoría automática (`lineas_duplicadas_exactas`) al
# reprocesar en vivo. El número de columnas por sí solo no basta como
# garantía de "misma forma de tabla". La vía segura que ya preveía la
# sesión que cerró `cabecera_sin_senal` (docstring de esa función) sigue
# siendo la correcta: cada tabla sin cabecera pide su propio mapeo al
# modelo, con sus propias filas de ejemplo -- exige `MODEL_API_KEY`
# configurada, no disponible en este entorno; sin ella, esas páginas se
# abren (localizador) pero su tabla queda pendiente de revisión en vez de
# perderse o corromperse.


def mapear_cabecera(
    cabecera: list[Optional[str]],
    filas_ejemplo: list[list[Optional[str]]],
    db: Session,
    model_provider: Optional[ModelProvider],
) -> ResultadoMapeoCabecera:
    firma = calcular_firma_cabecera(cabecera)
    cabecera_fiable = not cabecera_sin_senal(cabecera)

    if cabecera_fiable:
        cacheado = obtener_mapeo_cacheado(db, firma)
        if cacheado is not None:
            return ResultadoMapeoCabecera(
                mapeo=completar_columna_codigo_material(cabecera, dict(cacheado.mapeo)),
                firma=firma, origen="cache", llamada_modelo=False,
            )

        mapeo_determinista = intentar_mapeo_determinista(cabecera)
        if mapeo_determinista is not None:
            guardar_mapeo_cacheado(db, firma, cabecera, mapeo_determinista, origen="determinista")
            return ResultadoMapeoCabecera(
                mapeo=mapeo_determinista, firma=firma, origen="determinista", llamada_modelo=False
            )

    if model_provider is None:
        raise RuntimeError(
            f"la cabecera {cabecera!r} (firma {firma}) no tiene mapeo determinista "
            "y no se proporcionó un ModelProvider para resolverla"
        )
    mapeo_modelo = _mapear_con_modelo(cabecera, filas_ejemplo, model_provider)
    if cabecera_fiable:
        guardar_mapeo_cacheado(db, firma, cabecera, mapeo_modelo, origen="modelo")
    return ResultadoMapeoCabecera(
        mapeo=completar_columna_codigo_material(cabecera, mapeo_modelo), firma=firma, origen="modelo",
        llamada_modelo=True,
    )


# Bloque 2, sesión 2026-09-19 (decisión del cliente): la columna de IMPORTE
# del cuadro -- cantidad × precio unitario de cada renglón, tal como la
# imprime el documento. No es un campo del catálogo y no se guarda: sirve
# solo para la comprobación aritmética de
# `app.catalogo.corregir_precio_con_importe_del_documento`, que es la única
# vía por la que un precio puede reescribirse desde el propio documento.
#
# Campo opcional, fuera de `CAMPOS`, por el mismo motivo que
# `CAMPO_CODIGO_MATERIAL`: el modelo nunca lo ve ni lo devuelve, así que
# añadirlo no invalida ninguna respuesta ya cacheada.
#
# Coincidencia EXACTA del nombre, nunca "contiene". Medido sobre las
# cabeceras reales ya cacheadas del corpus: "IMPORTE" (68 tablas), "TOTAL"
# (11), "TOTALES" (6), "IMPORTE (€)" (4), "IMPORTE (€ Ejecución por
# Contrata)" (2), "SUBTOTAL" (1). Deliberadamente FUERA: "IMPORTE UNITARIO"
# (es un precio unitario, no el total del renglón), "IMPORTE COMPRA",
# "IMPORTE 2024"/"IMPORTE 2025" e "IMPORTE REPARACIÓN" -- nombres de los que
# no se puede afirmar que sean cantidad × precio de esa fila.
_NOMBRES_COLUMNA_IMPORTE = frozenset({"importe", "importe total", "total importe", "total", "totales", "subtotal"})
_PARENTESIS_RE = re.compile(r"\([^)]*\)")


def _nombre_de_columna_importe(texto: str) -> bool:
    """El nombre, sin su calificador entre paréntesis ("IMPORTE (€ Ejecución
    por Contrata)" -> "importe"), es uno de los nombres cerrados de arriba."""
    return _PARENTESIS_RE.sub(" ", texto).strip() in _NOMBRES_COLUMNA_IMPORTE


def completar_columna_importe(
    cabecera: list[Optional[str]], mapeo: dict[str, Optional[int]]
) -> dict[str, Optional[int]]:
    """La columna de importe de la tabla, si la cabecera la nombra sin
    ambigüedad y no la reclama ya ningún campo del catálogo. Con cero o más
    de una candidata no se adivina: sin columna de importe, la comprobación
    aritmética simplemente no se puede hacer y ningún precio se toca.

    No se guarda en la caché de firma: se recalcula desde la cabecera en cada
    pasada, igual que `completar_columna_codigo_material`."""
    if mapeo.get(CAMPO_IMPORTE) is not None:
        return mapeo
    normalizados = [normalizar(c) if c else "" for c in cabecera]
    usadas = {col for col in mapeo.values() if col is not None}
    candidatas = [
        indice
        for indice, texto in enumerate(normalizados)
        if texto and _nombre_de_columna_importe(texto) and indice not in usadas
    ]
    if len(candidatas) != 1:
        return mapeo
    return {**mapeo, CAMPO_IMPORTE: candidatas[0]}
