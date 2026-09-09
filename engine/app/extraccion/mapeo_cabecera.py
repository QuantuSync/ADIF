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


def heredar_mapeo_de_pagina_anterior(
    cabecera: list[Optional[str]],
    ultimo_mapeo_resuelto: Optional[dict[str, Optional[int]]],
    ultima_longitud_fila: Optional[int],
) -> Optional[ResultadoMapeoCabecera]:
    """Bloque 5, cambios del cliente tras revisar el catálogo (sesión
    2026-09-09): una tabla sin ninguna celda de cabecera con texto real
    (`_cabecera_sin_senal`) nunca puede pedir al modelo un mapeo NUEVO de
    forma fiable -- no hay ninguna palabra que traducir, solo filas de
    datos. Verificado contra el PDF real
    (`6.20/28510.0047_ANEJO_abd69efbdd39b552.pdf`, cuadro de precios de 61
    páginas con cabecera solo en la primera): sin esto, cada página de
    continuación revienta con `RuntimeError` en cuanto no hay
    `model_provider`, y con uno sí configurado el modelo tendría que
    adivinar a ciegas sobre las mismas filas de ejemplo una y otra vez, sin
    garantía de acertar la MISMA asignación de columnas cada vez.

    Devuelve el mapeo de la tabla anterior tal cual, sin tocar `cache_
    mapeo_cabecera` (nunca bajo la firma degenerada de cabecera vacía,
    docstring de `_cabecera_sin_senal`: cachear eso confundiría tablas de
    documentos distintos que comparten esa misma firma), cuando esta tabla
    no trae ninguna señal propia Y la anterior de este mismo documento sí
    tuvo un mapeo resuelto (por cabecera propia, caché, determinista o
    modelo -- da igual el origen) con el MISMO número de columnas -- una
    comprobación barata de que de verdad es la misma forma de tabla, no
    una completamente distinta que por casualidad también carece de
    cabecera. `None` en cualquier otro caso: el llamador decide entonces
    llamar a `mapear_cabecera` como de costumbre. Reiniciar `ultimo_mapeo_
    resuelto` a `None` en cada documento nuevo es responsabilidad del
    llamador (`app.extraccion.pipeline_anejo`), igual que `ultimo_lote_
    resuelto`: heredar de un documento a otro no tendría ninguna base."""
    if (
        _cabecera_sin_senal(cabecera)
        and ultimo_mapeo_resuelto is not None
        and len(cabecera) == ultima_longitud_fila
    ):
        return ResultadoMapeoCabecera(
            mapeo=ultimo_mapeo_resuelto,
            firma=calcular_firma_cabecera(cabecera),
            origen="heredado_pagina_anterior",
            llamada_modelo=False,
        )
    return None


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
