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
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.extraccion.firma_cabecera import calcular_firma_cabecera
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

    return {campo: campo_a_columna.get(campo) for campo in CAMPOS}


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


def _cabecera_sin_senal(cabecera: list[Optional[str]]) -> bool:
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
# sesión que cerró `_cabecera_sin_senal` (docstring de esa función) sigue
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
    cabecera_fiable = not _cabecera_sin_senal(cabecera)

    if cabecera_fiable:
        cacheado = obtener_mapeo_cacheado(db, firma)
        if cacheado is not None:
            return ResultadoMapeoCabecera(
                mapeo=dict(cacheado.mapeo), firma=firma, origen="cache", llamada_modelo=False
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
    return ResultadoMapeoCabecera(mapeo=mapeo_modelo, firma=firma, origen="modelo", llamada_modelo=True)
