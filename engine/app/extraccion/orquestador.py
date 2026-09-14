"""Trabajo de cola "extraer_expediente": encadena las seis etapas de la
cascada de extracción (CONTEXTO.md sección 5) sobre todos los documentos ya
descargados de un expediente, y deja líneas de catálogo escritas en base de
datos. Es el punto de entrada que usa el worker (app/worker.py), simétrico a
`app.scraping.job.ejecutar_scraping_expediente` para el trabajo de descarga.

Etapa 1 (clasificar) y etapa 2 (campos de etiqueta fija) se ejecutan aquí por
primera vez sobre datos reales de expediente — hasta ahora solo existían
como funciones probadas contra fixtures sueltos. Etapas 3-6 reutilizan
`app.extraccion.pipeline_anejo.procesar_anejo` tal cual.

Extracción por lote (encargo de la sesión de multi-lote, disparado por el
expediente real 6.25/28510.0027: LOTE 1 al 7,13 %, LOTE 3 al 1,18 %,
presupuestos distintos — el motor se quedaba con la primera baja que
encontraba en el texto y la presentaba como la del expediente entero, dato
incorrecto no solo incompleto). `app.extraccion.lotes.extraer_lotes_declarados`
decide si el expediente tiene varios lotes o uno implícito
(`LOTE_UNICO`); el resto de la cascada (mapeo de cabecera, asociación de
tabla a lote en `app.extraccion.lote_tabla`, guardado de catálogo) ya
trabaja por lote, nunca por expediente.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.catalogo import guardar_lineas_catalogo, podar_lineas_obsoletas_de_documento
from app.extraccion.baja import (
    BajaDeclarada,
    elegir_baja_preferida,
    extraer_baja_declarada,
    extraer_codigo_propio_documento,
)
from app.extraccion.campos_lc27 import (
    extraer_adjudicatario_lc27,
    extraer_importe_adjudicacion_lc27,
    extraer_importe_licitacion_lc27,
    extraer_objeto_contrato_lc27,
)
from app.extraccion.campos_pcsp import CampoAnclado, CODIGO_EXPEDIENTE_RE, extraer_campos_anuncio_pcsp, importe_como_decimal
from app.extraccion.lotes_pcsp import extraer_campos_pcsp_para_expediente, extraer_ventanas_multi_lote_pcsp
from app.extraccion.clasificador import clasificar, es_pliego_sin_precios
from app.extraccion.cruce_codigos import (
    AutoreferenciaMatrizError,
    asegurar_cruce_codigos,
    asignar_matriz,
    normalizar_codigo_expediente,
)
from app.extraccion.herencia_matriz import (
    EstadoResolucionMatriz,
    intentar_heredar_de_matriz,
    reencolar_pedidos_esperando_matriz,
    resolver_o_encolar_matriz,
)
from app.extraccion.identidad_expediente import corregir_identidad_expediente
from app.extraccion.invalidado import INVALIDADO
from app.extraccion.lotes import (
    IdentidadContrato,
    LoteDeclarado,
    ResultadoLotes,
    extraer_identidad_contrato,
    extraer_lotes_declarados,
)
from app.extraccion.modelo_precio_indexado import detectar_modelo_precio_indexado
from app.extraccion.normalizacion import parsear_importe_es
from app.extraccion.pipeline_anejo import procesar_anejo
from app.extraccion.precios_unitarios import calcular_baja_efectiva
from app.extraccion.texto import es_documento_escaneado, extraer_texto_cacheado
from app.interfaces.document_storage import DocumentStorage
from app.interfaces.model_provider import ModelProvider
from app.models import (
    Documento,
    DocumentoExpediente,
    EstadoExpediente,
    Expediente,
    LineaCatalogo,
    Lote,
    ModeloPrecio,
    OrigenDocumento,
    TipoDocumento,
    TrabajoCola,
    TrazaOrigen,
)

# Identificador de lote cuando el documento no declara ninguno por su nombre
# (CONTEXTO.md, encargo de esta sesión, punto 1: "un único lote implícito,
# para que el modelo de datos sea uniforme"). "1" para coincidir con la
# convención ya usada en los tests de la cascada
# (tests/extraccion/test_pipeline_anejo.py).
LOTE_UNICO = "1"

# Documentos de estas plantillas declaran la baja en texto (CONTEXTO.md sección
# 4 y docstring de app.extraccion.baja). `propuesta_dt` añadido en la sesión
# de arreglos pequeños (docs/analisis-corpus.md hallazgo 4): sin esto, aunque
# el clasificador ya reconociera la plantilla, su baja declarada ("con una
# baja del N% a todos los precios unitarios") nunca se llegaba a buscar.
_TIPOS_CON_BAJA_DECLARADA = (
    TipoDocumento.propuesta_lc27,
    TipoDocumento.resolucion_adjudicacion,
    TipoDocumento.contrato,
    TipoDocumento.propuesta_dt,
)

# Igual que `app.extraccion.baja._PRIORIDAD_BAJA` (CONTEXTO.md sección 17:
# preferir la Resolución sobre la Propuesta cuando existan las dos, por ser
# el acto posterior y definitivo). `propuesta_dt` es al mismo tipo de hecho
# que `propuesta_lc27` (docs/analisis-corpus.md hallazgo 4), misma
# prioridad. El Contrato no entra en esta prioridad: declara un único lote
# (el suyo), no el desglose de la licitación -- lo que dice de su propio lote
# se usa aparte, ver `_identidades_de_contratos`.
_PRIORIDAD_LOTES = {
    TipoDocumento.resolucion_adjudicacion: 0,
    TipoDocumento.propuesta_lc27: 1,
    TipoDocumento.propuesta_dt: 1,
}


@dataclass
class _Documento:
    documento: Documento
    tipo: TipoDocumento
    paginas: list
    # CONTEXTO.md sección 3: el único documento escaneado confirmado del
    # corpus. Se marca aquí, en la clasificación, para que el motivo de
    # revisión lo distinga de "no se extrajo ninguna línea" (ver
    # `es_documento_escaneado`) en vez de intentar procesarlo como si tuviera
    # texto.
    escaneado: bool = False
    # CONTEXTO.md sección 26 (criterio del cliente sobre pliegos, verificado
    # contra el corpus real): un pliego administrativo o PCAP nunca trae
    # cuadro de precios -- se salta la localización/extracción de tabla
    # entera, nunca un `pliego de prescripciones tecnicas` (ver
    # `app.extraccion.clasificador.es_pliego_sin_precios`).
    pliego_sin_precios: bool = False
    # Marcador que decidió la clasificación (`ResultadoClasificacion.marcador`,
    # ver docstring de `app.extraccion.clasificador`): necesario para
    # distinguir, dentro de `TipoDocumento.pliego`, un "documento de pliegos"
    # (portada administrativa PCSP con la misma anatomía de etiquetas fijas
    # que un Anuncio PCSP -- docstring del clasificador) de un "pliego de
    # clausulas administrativas" (PCAP, sin esos campos). Ver
    # `_es_documento_de_pliegos_pcsp`.
    marcador: Optional[str] = None


def _traza(
    db: Session,
    entidad_id: int,
    campo: str,
    documento_id: Optional[int],
    pagina: Optional[int],
    fragmento: Optional[str],
    valor,
    entidad_tipo: str = "expediente",
) -> None:
    """CONTEXTO.md sección 9.10: cada cifra derivada queda anclada a
    documento, página y fragmento, no solo al número final. `entidad_tipo`
    por defecto es "expediente" (uso histórico); las trazas de baja/importe
    por lote pasan `entidad_tipo="lote"` con `entidad_id=lote.id`."""
    if valor is None or documento_id is None:
        return
    db.add(
        TrazaOrigen(
            entidad_tipo=entidad_tipo,
            entidad_id=entidad_id,
            campo=campo,
            documento_id=documento_id,
            pagina=pagina,
            fragmento=fragmento,
            valor_extraido=str(valor),
        )
    )


def _acumular_motivo(motivo: Optional[str], nuevo: Optional[str]) -> Optional[str]:
    if not nuevo:
        return motivo
    return f"{motivo}; {nuevo}" if motivo else nuevo


def _combinar_fuente(principal, respaldo):
    """`principal or respaldo` de siempre, adaptado a que `principal` pueda
    ser `INVALIDADO` (`app.extraccion.invalidado`): un respaldo real (LC.27)
    sigue ganando sobre un PCSP invalidado, pero si tampoco hay respaldo se
    devuelve `INVALIDADO` tal cual -- nunca `None`, para que el llamador
    sepa que hay que BORRAR un valor ya guardado, no dejarlo como estaba."""
    if principal is not None and principal is not INVALIDADO:
        return principal
    if respaldo is not None:
        return respaldo
    return principal


def _valor_final(fuente):
    """Primer elemento de la tupla `(valor, documento_id, pagina,
    fragmento)`, o el propio `fuente` tal cual si es `None`/`INVALIDADO`
    (no subindexable)."""
    if fuente is None or fuente is INVALIDADO:
        return fuente
    return fuente[0]


def _nivel_campo(valor, resuelto_por_lote: bool) -> int:
    """Prioridad al combinar el mismo campo (importe de licitación,
    adjudicación o adjudicatario) leído de varios documentos Anuncio PCSP
    del mismo expediente -- ver el comentario sobre los cuatro niveles en
    `_extraer_campos_expediente`."""
    if valor is None:
        return 0
    if valor is INVALIDADO:
        return 2
    return 3 if resuelto_por_lote else 1


def _obtener_o_crear_lote(db: Session, expediente_id: int, identificador: str) -> Lote:
    lote = db.execute(
        select(Lote).where(Lote.expediente_id == expediente_id, Lote.identificador_lote == identificador)
    ).scalar_one_or_none()
    if lote is None:
        lote = Lote(expediente_id=expediente_id, identificador_lote=identificador)
        db.add(lote)
        db.commit()
        db.refresh(lote)
    return lote


def _eliminar_lote_sentinela_obsoleto(
    db: Session, expediente_id: int, lotes_declarados: list[LoteDeclarado]
) -> None:
    """Idempotencia (CONTEXTO.md sección 9.9) al migrar al arreglo de
    identidad de lote (sección 27): un expediente reprocesado con el
    generalizador nuevo puede pasar de "un único lote implícito"
    (`LOTE_UNICO`, camino de antes de esta sesión) a lotes reales de
    verdad, y en varios casos reales (`6.23/28510.0066`) las líneas que
    colgaban del sentinela mezclaban precios de varios lotes distintos
    (sección 22/26 del análisis) -- sustituirlas por las correctas exige
    borrar primero el lote sentinela y sus líneas, nunca dejarlas
    conviviendo con las nuevas. Solo actúa cuando el expediente tiene
    EXACTAMENTE un lote existente y es el sentinela: un expediente que ya
    tenía lotes reales de una ejecución anterior correcta no se toca aquí,
    lo actualiza `_obtener_o_crear_lote` como siempre.

    Bloque 4, sesión 2026-09-12 (continuación, verificación de determinismo):
    `LOTE_UNICO = "1"` -- el mismo texto que un lote REAL declarado "Lote 1"
    en un documento real (verificado contra 11 expedientes reales del
    corpus, `6.23/28510.0051` entre ellos: título "2 LOTES", su único lote
    real se llama "1"). Sin distinguir los dos casos, esta función borraba y
    `_obtener_o_crear_lote` recreaba el mismo lote -- con un `id` nuevo cada
    vez -- en CADA reproceso, para siempre, no solo la primera vez que
    migraba de sentinela a real: verificado en vivo reprocesando el corpus
    completo dos veces seguidas, el `id` de `Lote` y de cada `LineaCatalogo`
    que cuelga de él cambiaba entre pasadas sin que ningún dato cambiara
    (1.071 líneas solo en `6.23/28510.0051`). La comprobación de más:
    `lotes_declarados` es el resultado de ESTA MISMA pasada -- si alguno de
    ellos declara justo el identificador "1", el lote existente con ese
    identificador no es un sentinela obsoleto, es el mismo lote real
    reconfirmándose, y `_obtener_o_crear_lote` ya lo reutiliza sin tocarlo."""
    if any(declarado.identificador == LOTE_UNICO for declarado in lotes_declarados):
        return
    lotes_existentes = db.execute(select(Lote).where(Lote.expediente_id == expediente_id)).scalars().all()
    if len(lotes_existentes) != 1 or lotes_existentes[0].identificador_lote != LOTE_UNICO:
        return
    lote_sentinela = lotes_existentes[0]
    db.execute(delete(LineaCatalogo).where(LineaCatalogo.lote_id == lote_sentinela.id))
    db.delete(lote_sentinela)
    db.commit()


def _lotes_de_expedientes_hermanos(
    expediente: Expediente, lotes_declarados: list[LoteDeclarado]
) -> dict[str, Optional[str]]:
    """Sesión 2026-09-14 (continuación, revisión del cliente): cuando uno de
    los lotes declarados trae como código propio el de ESTE expediente, este
    expediente es ese lote -- un contrato de la licitación, no la licitación
    entera (CONTEXTO.md sección 27, "Contrato ⟷ lote"). Los demás lotes son
    de sus expedientes hermanos, aunque los documentos se compartan: se
    devuelven (identificador -> su código, si se conoce) para que no se
    guarden aquí. Vacío si el expediente no se reconoce en ningún lote (el
    expediente principal de la licitación, que sí los agrupa todos) o si se
    reconoce en más de uno (identidad contradictoria: no se recorta nada).

    Caso que lo motivó: `6.21/28510.0015` (LOTE 1, tornillería) y
    `6.21/28510.0016` (LOTE 2, anclajes) mostraban cada uno las líneas, la
    baja y el importe de los dos lotes."""
    if len(lotes_declarados) < 2:
        return {}
    codigo = normalizar_codigo_expediente(expediente.codigo_expediente)
    propios = [d for d in lotes_declarados if normalizar_codigo_expediente(d.codigo_expediente_lote) == codigo]
    if len(propios) != 1:
        return {}
    return {d.identificador: d.codigo_expediente_lote for d in lotes_declarados if d is not propios[0]}


def _lote_propio(expediente: Expediente, lotes_declarados: list[LoteDeclarado]) -> Optional[str]:
    """Sesión 2026-09-14 (tercera parte): el lote de este expediente, si
    exactamente uno de los declarados trae su código -- con uno solo
    declarado también (`_lotes_de_expedientes_hermanos` pide dos porque
    busca hermanos; aquí basta con saber cuál es el suyo). Ver
    `app.extraccion.pipeline_anejo.procesar_anejo(lote_propio=...)`."""
    codigo = normalizar_codigo_expediente(expediente.codigo_expediente)
    propios = [d for d in lotes_declarados if normalizar_codigo_expediente(d.codigo_expediente_lote) == codigo]
    return propios[0].identificador if len(propios) == 1 else None


def _es_contrato_de_otro_lote(
    expediente: Expediente, identidades_por_documento: dict[int, Optional[IdentidadContrato]], documento_id: int
) -> bool:
    """El documento es el Contrato de otro lote (su "Contrato nº" no es el
    código de este expediente): sus tablas sin cabecera son de ese lote, no
    de este, aunque lo archiven junto a sus documentos (`6.22/28510.0155`
    guarda también el Contrato del LOTE 2)."""
    identidad = identidades_por_documento.get(documento_id)
    return identidad is not None and normalizar_codigo_expediente(
        identidad.codigo_expediente_lote
    ) != normalizar_codigo_expediente(expediente.codigo_expediente)


def _hermanos_en_catalogo(db: Session, lotes_hermanos: dict[str, Optional[str]]) -> set[str]:
    """Los lotes hermanos cuyo expediente está en el catálogo: sus líneas se
    guardan allí (y en el principal), así que aquí se descartan sin perder
    nada. Sesión 2026-09-14 (tercera parte): con los lotes que solo nombra
    un Contrato, un hermano puede no estar en el catálogo -- `6.21/28510.0066`
    (LOTE 2) guarda el Contrato del LOTE 1 (`0065`, que no está), con su
    listado de materiales; descartarlo lo borraba de todas partes."""
    codigos = {
        normalizar_codigo_expediente(codigo): identificador
        for identificador, codigo in lotes_hermanos.items()
        if codigo
    }
    if not codigos:
        return set()
    existentes = {
        normalizar_codigo_expediente(codigo)
        for (codigo,) in db.execute(select(Expediente.codigo_expediente))
    }
    return {identificador for codigo, identificador in codigos.items() if codigo in existentes}


def _como_lineas_de_otro_expediente(
    lineas: list[dict], identificador: str, codigo: Optional[str]
) -> list[dict]:
    """Líneas de la tabla de un lote hermano cuyo expediente no está en el
    catálogo: no son de este expediente, pero se conservan sin lote (con la
    clave de huérfana, que distingue su tabla) para no perderlas. Nunca se
    muestran en el Excel ni cuentan como del expediente."""
    motivo = (
        f"tabla del LOTE {identificador}{f' ({codigo})' if codigo else ''}, otro lote de la licitación cuyo "
        "expediente no está en el catálogo: no es de este expediente, se conserva sin lote"
    )
    convertidas = []
    for linea in lineas:
        linea = dict(linea)
        linea["clave_linea"] = linea["clave_huerfana_hipotetica"]
        linea["motivo_revision"] = _acumular_motivo(linea.get("motivo_revision"), motivo)
        linea["lote_heredado_de_pagina_anterior"] = None
        linea["lote_del_expediente"] = None
        linea["baja_lote"] = None
        linea["precio_adjudicado"] = None
        convertidas.append(linea)
    return convertidas


def _eliminar_lotes_de_hermanos(db: Session, expediente_id: int, identificadores: set[str]) -> None:
    """Idempotencia (CONTEXTO.md sección 9): los lotes de hermanos que una
    pasada anterior guardó en este expediente, con sus líneas, se borran --
    mismo mecanismo que `_eliminar_lote_sentinela_obsoleto`. Las líneas no
    se pierden: siguen en el expediente hermano y en el principal."""
    if not identificadores:
        return
    lotes = db.execute(
        select(Lote).where(Lote.expediente_id == expediente_id, Lote.identificador_lote.in_(identificadores))
    ).scalars().all()
    for lote in lotes:
        db.execute(delete(LineaCatalogo).where(LineaCatalogo.lote_id == lote.id))
        db.execute(delete(TrazaOrigen).where(TrazaOrigen.entidad_tipo == "lote", TrazaOrigen.entidad_id == lote.id))
        db.delete(lote)
    db.commit()


def _clasificar_documentos(db: Session, storage: DocumentStorage, documentos: list[Documento]) -> list[_Documento]:
    resultado = []
    for doc in documentos:
        paginas = extraer_texto_cacheado(
            db, doc.hash, lambda: io.BytesIO(storage.recuperar(doc.ruta_almacenamiento))
        )
        escaneado = es_documento_escaneado(paginas)
        # Un documento escaneado no tiene marcadores de texto que buscar —
        # clasificarlo igual lo mandaría a `otro` de forma indistinguible de
        # un documento legible con una plantilla desconocida (CONTEXTO.md
        # sección 3, docstring de `es_documento_escaneado`).
        clasificacion = clasificar(paginas) if not escaneado else None
        # El clasificador manda, nunca el nombre de fichero ni la categoría
        # que le asignó el scraper (CONTEXTO.md sección 3 y docstring de
        # app.extraccion.clasificador).
        tipo = clasificacion.tipo if clasificacion is not None else TipoDocumento.otro
        sin_precios = clasificacion is not None and es_pliego_sin_precios(clasificacion)
        marcador = clasificacion.marcador if clasificacion is not None else None
        doc.tipo_documento = tipo
        doc.paginas = len(paginas)
        resultado.append(
            _Documento(
                documento=doc, tipo=tipo, paginas=paginas, escaneado=escaneado,
                pliego_sin_precios=sin_precios, marcador=marcador,
            )
        )
    db.commit()
    return resultado


def _priorizar_por_origen(items: list[_Documento]) -> list[_Documento]:
    """Bloque 6, sesión de comparación documento-vs-listado interno
    (política confirmada por el cliente): cuando el mismo expediente trae,
    para el mismo tipo de documento, uno descargado de la Plataforma y uno
    aportado a mano (`app.ingesta_local`), gana la Plataforma. El resto de
    la cascada ya resuelve "varios documentos declaran lo mismo distinto"
    por "primero que aparece gana" o por prioridad de plantilla con
    desempate por orden de lista (`app.extraccion.baja.
    elegir_baja_preferida`, `_nivel_campo` de más abajo...) -- reordenar una
    sola vez aquí, antes de que nada de eso se ejecute, hace que esos
    mecanismos ya existentes y ya probados prefieran la Plataforma sin
    tocarlos uno a uno. `sorted` es estable: dentro del mismo origen, el
    orden relativo no cambia."""
    return sorted(items, key=lambda item: 1 if item.documento.origen == OrigenDocumento.manual else 0)


# Tipos de documento que declaran hechos propios del expediente (baja,
# importes, adjudicatario, objeto del contrato) -- un anejo/pliego sin firma
# ni adjudicación no puede "contradecir" nada de eso, así que queda fuera de
# `_detectar_conflicto_origen` (que sí vigila `anejo`: dos cuadros de
# precios de origen distinto, uno por tipo, es la otra forma real de
# desacuerdo entre las dos fuentes).
_TIPOS_CON_CONFLICTO_RELEVANTE = frozenset({
    TipoDocumento.anuncio_pcsp,
    TipoDocumento.propuesta_lc27,
    TipoDocumento.resolucion_adjudicacion,
    TipoDocumento.propuesta_dt,
    TipoDocumento.contrato,
    TipoDocumento.anejo,
})


def _detectar_conflicto_origen(items: list[_Documento]) -> Optional[str]:
    """Bloque 6: aviso informativo, nunca bloqueante (mismo criterio que
    `aviso_sindicacion`, CONTEXTO.md sección 12) de que este expediente
    combina, para el MISMO tipo de documento, uno descargado de la
    Plataforma y uno aportado a mano -- señal de que puede haber dos
    versiones del mismo hecho. `_priorizar_por_origen` ya resuelve el
    desacuerdo de VALOR a favor de la Plataforma; esto no intenta
    diferenciar campo a campo cuál exactamente discrepó -- solo señala
    dónde mirar, para no dar por hecho en silencio que el documento
    aportado a mano ya no hace falta. Recalculado entero en cada extracción
    (el llamador lo asigna sin condición, nunca lo acumula sobre un aviso
    de una pasada anterior)."""
    tipos_por_origen: dict[TipoDocumento, set[OrigenDocumento]] = {}
    for item in items:
        if item.tipo not in _TIPOS_CON_CONFLICTO_RELEVANTE:
            continue
        origen = item.documento.origen or OrigenDocumento.plataforma
        tipos_por_origen.setdefault(item.tipo, set()).add(origen)
    mixtos = sorted(tipo.value for tipo, origenes in tipos_por_origen.items() if len(origenes) > 1)
    if not mixtos:
        return None
    return (
        "combina documentos descargados de la Plataforma y aportados a mano para el mismo tipo de documento "
        f"({', '.join(mixtos)}) -- en caso de desacuerdo prevalece la Plataforma; revisar si el documento "
        "aportado a mano sigue haciendo falta"
    )


@dataclass(frozen=True)
class _LotesExtraidos:
    lotes: list[LoteDeclarado]
    documento_id: Optional[int]
    lotes_totales_declarados: Optional[int]
    codigo_principal_declarado: Optional[CampoAnclado]
    # Identificador de lote -> por qué su baja salió del Contrato y no de la
    # adjudicación (ver `_extraer_lotes_declarados_del_expediente`).
    motivos_por_lote: Optional[dict[str, str]] = None


def _identidades_de_contratos(documentos: list[_Documento]) -> list[tuple[IdentidadContrato, int]]:
    """Lo que dice cada Contrato firmado del expediente sobre qué lote es
    (`app.extraccion.lotes.extraer_identidad_contrato`), con su documento.
    Si dos Contratos se contradicen (el mismo código con dos números de
    lote, o el mismo número con dos códigos), ninguno de los implicados se
    usa: sin un único valor no hay autoridad que oponer a la adjudicación."""
    identidades: list[tuple[IdentidadContrato, int]] = []
    for item in documentos:
        if item.tipo != TipoDocumento.contrato:
            continue
        identidad = extraer_identidad_contrato(item.paginas)
        if identidad is not None:
            identidades.append((identidad, item.documento.id))
    lotes_por_codigo: dict[str, set[str]] = {}
    codigos_por_lote: dict[str, set[str]] = {}
    for identidad, _ in identidades:
        codigo = normalizar_codigo_expediente(identidad.codigo_expediente_lote)
        lotes_por_codigo.setdefault(codigo, set()).add(identidad.identificador)
        codigos_por_lote.setdefault(identidad.identificador, set()).add(codigo)
    unicas: dict[str, tuple[IdentidadContrato, int]] = {}
    for identidad, documento_id in identidades:
        codigo = normalizar_codigo_expediente(identidad.codigo_expediente_lote)
        if len(lotes_por_codigo[codigo]) == 1 and len(codigos_por_lote[identidad.identificador]) == 1:
            unicas.setdefault(codigo, (identidad, documento_id))
    return sorted(unicas.values(), key=lambda par: (len(par[0].identificador), par[0].identificador))


def _extraer_lotes_declarados_del_expediente(documentos: list[_Documento]) -> _LotesExtraidos:
    """Primer documento (por prioridad de plantilla, no por orden de lista)
    que declare al menos un lote por su nombre gana — mismo criterio que
    `app.extraccion.baja.elegir_baja_preferida` aplicado a listas de lotes
    en vez de a una baja suelta.

    Sesión 2026-09-14 (continuación): los Contratos firmados del expediente
    tienen la última palabra sobre la identidad de cada lote (qué número
    lleva qué código), CONTEXTO.md sección 27. Corrigen una errata de
    número en la adjudicación (ver `extraer_lotes_declarados`) y completan
    el código y la baja de un lote que la adjudicación nombra sin traerlos
    -- caso real: tornillería, cuya única Resolución es la del LOTE 2; el
    LOTE 1 (`6.21/28510.0015`) solo lo nombra de pasada, y su código y su
    baja salen de su Contrato. Si el Contrato de un lote declara una baja
    distinta de la que la adjudicación le atribuye, gana la del Contrato --
    el único documento que habla solo de ese lote -- y queda como motivo
    de revisión.

    Sesión 2026-09-14 (tercera parte): un lote que solo nombra su Contrato
    también se añade. La continuación anterior no lo hacía por una lectura
    equivocada de `6.23/28510.0051` ("cuadro común sin ningún LOTE N"): su
    cuadro de precios trae "Lote 1: ANCHO MIXTO" (p.14) y "Lote 2: ANCHO
    METRICO" (p.38), y lo que no trae lote es el anejo de criterios del
    conjunto. Su adjudicación solo nombra el LOTE 1 y sus dos Contratos
    dicen LOTE 1 -> `0060` y LOTE 2 -> `0061`: sin el LOTE 2, el principal
    mostraba las líneas del LOTE 2 como del 1. Y `0060`, cuyo único
    documento de lotes es la adjudicación de `0061`, recupera su propio
    LOTE 1."""
    identidades = _identidades_de_contratos(documentos)
    lote_por_codigo = {
        normalizar_codigo_expediente(identidad.codigo_expediente_lote): identidad.identificador
        for identidad, _ in identidades
    }
    candidatos: list[tuple[int, ResultadoLotes, int]] = []
    for item in documentos:
        prioridad = _PRIORIDAD_LOTES.get(item.tipo)
        if prioridad is None:
            continue
        resultado = extraer_lotes_declarados(item.paginas, lote_por_codigo)
        if resultado.lotes:
            candidatos.append((prioridad, resultado, item.documento.id))
    if not candidatos:
        return _LotesExtraidos(
            lotes=[], documento_id=None, lotes_totales_declarados=None, codigo_principal_declarado=None
        )
    candidatos.sort(key=lambda c: c[0])
    _, resultado, documento_id = candidatos[0]

    lotes = list(resultado.lotes)
    motivos_por_lote: dict[str, str] = {}
    por_identificador = {identidad.identificador: (identidad, doc_id) for identidad, doc_id in identidades}
    for i, declarado in enumerate(lotes):
        par = por_identificador.pop(declarado.identificador, None)
        if par is None:
            continue
        identidad, doc_id = par
        cambios = {}
        if declarado.codigo_expediente_lote is None:
            cambios["codigo_expediente_lote"] = identidad.codigo_expediente_lote
        if identidad.baja is not None and declarado.baja != identidad.baja:
            cambios.update(
                baja=identidad.baja, pagina=identidad.pagina, fragmento=identidad.fragmento, documento_id=doc_id
            )
            if declarado.baja is not None:
                # El Contrato de ESTE lote contradice el bloque que la
                # adjudicación le atribuye: gana el Contrato, y el resto del
                # bloque (adjudicatario, importe) deja de ser atribuible.
                # Caso real: la Resolución del LOTE 2 de `6.22/28510.0033`
                # copia en su RESUELVE "LOTE 1 ... EXPEDIENTE Nº
                # 6.22/28510.0057" con la empresa y la baja del LOTE 2
                # (TECNOLOGÍA SEÑALÉTICA, 0,50 %); el Contrato de `0057` es
                # de INDUSTRIAS LANEKO, 10,50 %.
                cambios.update(adjudicatario=None, importe_adjudicacion=None)
                baja_adjudicacion = f"{declarado.baja * 100:.2f}".replace(".", ",")
                baja_contrato = f"{identidad.baja * 100:.2f}".replace(".", ",")
                motivos_por_lote[declarado.identificador] = (
                    f"lote {declarado.identificador}: la adjudicación le atribuye una baja del "
                    f"{baja_adjudicacion} % y su Contrato ({identidad.codigo_expediente_lote}) declara "
                    f"{baja_contrato} % -- se usa la del Contrato; el adjudicatario y el importe de "
                    "ese bloque de la adjudicación no se atribuyen a este lote"
                )
        if cambios:
            lotes[i] = replace(declarado, **cambios)
    for identidad, doc_id in por_identificador.values():
        lotes.append(
            LoteDeclarado(
                identificador=identidad.identificador, baja=identidad.baja, importe_licitacion=None,
                importe_adjudicacion=None, adjudicatario=None,
                codigo_expediente_lote=identidad.codigo_expediente_lote, pagina=identidad.pagina,
                fragmento=identidad.fragmento, documento_id=doc_id,
            )
        )
    return _LotesExtraidos(
        lotes=lotes,
        documento_id=documento_id,
        lotes_totales_declarados=resultado.lotes_totales_declarados,
        codigo_principal_declarado=resultado.codigo_principal_declarado,
        motivos_por_lote=motivos_por_lote,
    )


_TIPOS_CONTRATO_OBRA = ("obras", "obra")


def _detectar_contrato_obra(documentos: list[_Documento]) -> Optional[CampoAnclado]:
    """CONTEXTO.md sección 26, criterio del cliente: el campo "Tipo de
    Contrato" del Anuncio PCSP (misma etiqueta fija que ya lee
    `extraer_campos_anuncio_pcsp`) dice "Suministros", "Obras" o "Servicios".
    Ninguno de los dos expedientes reales de este corpus (todos "Suministros",
    departamento 28510) lo dispara -- es una guarda para cuando aparezca uno,
    no algo que hoy cambie ningún resultado."""
    for item in documentos:
        if item.tipo != TipoDocumento.anuncio_pcsp:
            continue
        campo = extraer_campos_anuncio_pcsp(item.paginas).tipo_contrato
        if campo is not None and campo.valor.strip().lower() in _TIPOS_CONTRATO_OBRA:
            return campo
    return None


def _detectar_documento_adjudicacion_no_relacionado(
    items: list[_Documento], codigo_expediente: str, codigo_matriz: Optional[str]
) -> Optional[str]:
    """Bloque 4 (sesión de auditoría 2026-09-09): el nombre de fichero que
    asigna el scraper (`ADJUDICACION_<hash>.pdf`, `app.scraping.pcsp.
    seleccionar_documentos`) es la única pista de qué fila de la Plataforma
    lo trajo -- el clasificador de contenido (CONTEXTO.md sección 3) manda
    para decidir `tipo_documento`, nunca ese nombre, pero aquí se usa
    justo al revés: para encontrar el documento que el scraper SÍ pensaba
    que era la adjudicación, y comprobar si su propio texto respalda esa
    idea.

    Verificado contra 16 documentos reales así clasificados `otro` en el
    corpus: 5 mencionan su propio expediente (o su matriz) en el texto --
    normalmente un boletín de Consejo de Administración que aprueba varios
    contratos a la vez, plantilla que el clasificador todavía no reconoce,
    pero genuinamente relevante, no un error de selección. Al menos 3
    (`6.24/28510.0109`, `6.24/28510.0216`, `4.25/28510.0208`) NUNCA
    mencionan su propio expediente pese a mencionar otros -- el documento
    pertenece a un expediente distinto, descargado por error. Sin este
    aviso, dos de esos tres (`0109`, `0216`) quedaban `completado` con un
    documento de adjudicación ajeno adjunto, invisible para el cliente.

    Solo dispara cuando el documento SÍ trae al menos un código de
    expediente reconocible en su texto (`CODIGO_EXPEDIENTE_RE`) pero NINGUNO
    de ellos es el propio -- un documento sin ningún código legible (p.ej.
    escaneado, o una plantilla sin ese dato) no basta para sospechar, sería
    indistinguible de un falso positivo de extracción."""
    codigos_propios = {codigo_expediente}
    if codigo_matriz:
        codigos_propios.add(codigo_matriz)

    avisos: list[str] = []
    for item in items:
        nombre = item.documento.ruta_almacenamiento or ""
        if "/ADJUDICACION_" not in nombre and not nombre.startswith("ADJUDICACION_"):
            continue
        texto = "\n".join(pagina.texto for pagina in item.paginas)
        codigos_en_texto = set(CODIGO_EXPEDIENTE_RE.findall(texto))
        if not codigos_en_texto or codigos_en_texto & codigos_propios:
            continue
        avisos.append(
            f"el documento descargado como adjudicación ({nombre.rsplit('/', 1)[-1]}) no menciona este "
            f"expediente ni su matriz en su texto, pero sí menciona otros ({', '.join(sorted(codigos_en_texto))[:200]}) "
            "-- posible documento equivocado del scraper, confirmar contra la Plataforma"
        )
    return "; ".join(avisos) if avisos else None


def _es_documento_de_pliegos_pcsp(item: _Documento) -> bool:
    """Un "Documento de Pliegos" clasifica como `TipoDocumento.pliego`
    (CONTEXTO.md sección 26, criterio del cliente: sin cuadro de precios, se
    salta la localización de tabla) pero es, en su contenido, la misma
    portada administrativa PCSP que un Anuncio PCSP -- "comparten
    exactamente la misma anatomía de etiquetas fijas" (docstring de
    `app.extraccion.clasificador`, verificado en `6.23/28510.0135`: su único
    documento con "Nº de Lotes: 8" es justo uno de estos, sin ningún Anuncio
    PCSP en el expediente). Distinto de un "pliego de clausulas
    administrativas" (PCAP, sin esos campos) -- de ahí que haga falta el
    marcador exacto, no basta con `pliego_sin_precios`."""
    return item.tipo == TipoDocumento.pliego and item.marcador == "documento de pliegos"


def _detectar_numero_lotes_pcsp(documentos: list[_Documento]) -> Optional[int]:
    """Sesión de identidad de lote (CONTEXTO.md sección 27): el campo
    estructurado "Nº de Lotes:" del Anuncio PCSP es la única fuente de
    "cuántos lotes declara la licitación" para un expediente que no trae
    ninguna Propuesta LC.27 ni Resolución con bloque narrativo por lote —
    caso real verificado: `6.23/28510.0139` ("2 lotes" en el título, "Nº de
    Lotes: 2" aquí, cero documentos que declaren baja/importe por lote).

    También se busca en un "Documento de Pliegos" (`_es_documento_de_pliegos_pcsp`):
    caso real `6.23/28510.0135` (auditoría de ficheros huérfanos,
    2026-09-06), 8 lotes reales, un único lote con datos propios en este
    expediente -- antes de esta guarda, la cobertura parcial (1 de 8) no se
    detectaba nunca porque el expediente no tiene ningún Anuncio PCSP, solo
    el Documento de Pliegos con el campo "Nº de Lotes: 8", excluido de esta
    búsqueda sin motivo real (CONTEXTO.md sección 12: "lo que no cuadra va a
    revisión" -- esto se quedaba silenciosamente sin ir a revisión)."""
    for item in documentos:
        if item.tipo != TipoDocumento.anuncio_pcsp and not _es_documento_de_pliegos_pcsp(item):
            continue
        campo = extraer_campos_anuncio_pcsp(item.paginas).numero_lotes
        if campo is not None:
            return int(campo.valor)
    return None


def _extraer_campos_expediente(
    db: Session, expediente: Expediente, documentos: list[_Documento], registrar_baja_importe: bool = True,
) -> tuple[Optional[Decimal], Optional[Decimal], Optional[BajaDeclarada], Optional[str], Optional[str], bool]:
    """Etapa 2: nombre del proyecto y matriz (siempre) e importes de
    licitación/adjudicación y baja declarada a nivel de expediente (solo
    cuando `registrar_baja_importe`). Prioridad de importes: Anuncio PCSP
    sobre Propuesta LC.27 (CONTEXTO.md sección 4, tabla "Dónde está cada
    dato") — LC.27 es la reserva para expedientes sin Anuncio PCSP en el
    corpus (docstring de app.extraccion.campos_lc27).

    `registrar_baja_importe=False` es el camino multi-lote (llamador
    `ejecutar_extraccion_expediente`): ahí la baja y los importes del
    expediente salen de sus lotes (`_resumir_lotes_en_expediente`), no de
    "la primera baja que aparece en el texto" — devolver y trazar esa baja
    suelta aquí sería confuso (una cifra sin lote junto a las trazas por
    lote que sí importan) y ya no la usa nadie.

    El último valor devuelto, `multi_lote_pcsp_detectado`, es `True` cuando
    algún Anuncio PCSP de `documentos` agrupa varios lotes bajo "Nº Lote:
    NNN" (tercera variante multi-lote, `app.extraccion.lotes_pcsp`) --
    tanto si se identificó el bloque propio de este expediente como si no
    (ver `motivo_multi_lote_pcsp` para eso). El llamador lo usa para no
    componer el motivo genérico de "cobertura parcial: 0 de N lotes
    identificados" (pensado para cuando de verdad no hay ningún documento
    que desglose por lote) sobre un caso que esta vía ya trató -- bien o
    mal, pero explícitamente."""
    # (valor Decimal, documento_id, pagina, fragmento) por fuente; None si esa
    # fuente no trajo el campo. pcsp gana sobre lc27 al elegir al final.
    licitacion_pcsp = adjudicacion_pcsp = None
    licitacion_lc27 = adjudicacion_lc27 = None
    objeto_pcsp = objeto_lc27 = None
    adjudicatario_lc27 = None
    # Sesión de descubrimiento inverso, hallazgo de paso: el Anuncio PCSP ya
    # traía este campo por etiqueta fija (`campos_pcsp.CamposAnuncioPcsp.
    # adjudicatario`), pero el camino de lote único implícito (el que usan
    # estas tres matrices de carril, y la mayoría del corpus) nunca lo leía
    # -- solo el camino multi-lote explícito lo guardaba, desde una fuente
    # distinta (`LoteDeclarado.adjudicatario`, app.extraccion.lotes). Sin
    # esto, `lotes.adjudicatario` se quedaba `NULL` para casi todo el
    # corpus, y el descubrimiento inverso (que necesita el adjudicatario
    # para acotar su búsqueda en la Plataforma, ajuste 1 del encargo) nunca
    # tenía con qué buscar los pedidos de estas matrices reales.
    adjudicatario_pcsp = None
    candidatos_baja: list[BajaDeclarada] = []
    baja_doc: dict[int, int] = {}  # id(BajaDeclarada) -> documento.id
    # id(BajaDeclarada) -> "Contrato nº" declarado en su documento de origen
    # (None si no lo declara) -- sesión de medición del alcance, parte 2:
    # distingue una baja de UN HERMANO (documento compartido que sí declara
    # a quién pertenece) de una baja genuinamente de este expediente o de
    # un documento sin esa etiqueta (la inmensa mayoría del corpus).
    baja_codigo_propio: dict[int, Optional[str]] = {}
    # Tercera variante multi-lote, sesión de medición del alcance
    # (2026-09-08): un Anuncio PCSP que agrupa varios lotes bajo "Nº Lote:
    # NNN" en un único documento -- ver docstring de
    # `app.extraccion.lotes_pcsp` para el hallazgo real completo.
    motivo_multi_lote_pcsp: Optional[str] = None
    multi_lote_pcsp_detectado = False
    # Hallazgo real, verificando el reproceso de `6.20/28510.0041`: un mismo
    # expediente puede traer DOS Anuncios PCSP (CONTRATO + ADJUDICACION) --
    # uno de ellos, de un único lote en su propia sección de adjudicación,
    # PUEDE seguir teniendo el presupuesto GLOBAL en su propia cabecera sin
    # repetir "Nº Lote: NNN" (así que `extraer_ventanas_multi_lote_pcsp` no
    # lo detecta ni lo corrige). "El primer valor no nulo gana" dejaba que
    # ese documento, si se procesaba antes que el que sí resuelve el bloque
    # propio del lote, fijara la licitación global sin que el segundo,
    # correcto, pudiera corregirla después.
    #
    # Cuatro niveles de confianza, nunca se baja de nivel dentro del mismo
    # expediente (`_nivel_campo`): 3 un valor resuelto por lote con
    # confianza (`resuelto_por_lote`); 2 `INVALIDADO` -- el documento SÍ es
    # multi-lote pero no se pudo atribuir el bloque, más fiable que un
    # valor sin resolver porque sabemos explícitamente que no hay que
    # fiarse de él; 1 un valor sin resolver (documento de un solo lote, o
    # multi-lote nunca comprobado); 0 nada.
    licitacion_pcsp_nivel = adjudicacion_pcsp_nivel = adjudicatario_pcsp_nivel = 0

    for item in documentos:
        if item.tipo == TipoDocumento.anuncio_pcsp:
            campos, motivo_lote = extraer_campos_pcsp_para_expediente(item.paginas, expediente.nombre_proyecto)
            ventanas_item = extraer_ventanas_multi_lote_pcsp(item.paginas)
            resuelto_por_lote = bool(ventanas_item) and motivo_lote is None
            if ventanas_item:
                multi_lote_pcsp_detectado = True
            motivo_multi_lote_pcsp = _acumular_motivo(motivo_multi_lote_pcsp, motivo_lote)

            nivel = _nivel_campo(campos.importe_licitacion, resuelto_por_lote)
            if nivel > licitacion_pcsp_nivel:
                licitacion_pcsp_nivel = nivel
                licitacion_pcsp = (
                    INVALIDADO if campos.importe_licitacion is INVALIDADO else (
                        importe_como_decimal(campos.importe_licitacion), item.documento.id,
                        campos.importe_licitacion.pagina, campos.importe_licitacion.fragmento,
                    )
                )

            nivel = _nivel_campo(campos.importe_adjudicacion, resuelto_por_lote)
            if nivel > adjudicacion_pcsp_nivel:
                adjudicacion_pcsp_nivel = nivel
                adjudicacion_pcsp = (
                    INVALIDADO if campos.importe_adjudicacion is INVALIDADO else (
                        importe_como_decimal(campos.importe_adjudicacion), item.documento.id,
                        campos.importe_adjudicacion.pagina, campos.importe_adjudicacion.fragmento,
                    )
                )
            if campos.codigo_matriz:
                try:
                    escrito = asignar_matriz(expediente, campos.codigo_matriz.valor)
                except AutoreferenciaMatrizError:
                    # No debería pasar con el campo "Licitación basada en el
                    # acuerdo marco" (es una etiqueta distinta de la trampa
                    # "Nº EXPEDIENTE MATRIZ" de CONTEXTO.md sección 2), pero la
                    # comprobación es la misma para cualquier candidato --
                    # ver docstring de `asignar_matriz`.
                    escrito = False
                if escrito:
                    _traza(
                        db, expediente.id, "codigo_matriz", item.documento.id,
                        campos.codigo_matriz.pagina, campos.codigo_matriz.fragmento, campos.codigo_matriz.valor,
                    )
            if campos.objeto_contrato and objeto_pcsp is None:
                objeto_pcsp = (
                    campos.objeto_contrato.valor, item.documento.id,
                    campos.objeto_contrato.pagina, campos.objeto_contrato.fragmento,
                )
            nivel = _nivel_campo(campos.adjudicatario, resuelto_por_lote)
            if nivel > adjudicatario_pcsp_nivel:
                adjudicatario_pcsp_nivel = nivel
                adjudicatario_pcsp = (
                    INVALIDADO if campos.adjudicatario is INVALIDADO else (
                        campos.adjudicatario.valor, item.documento.id,
                        campos.adjudicatario.pagina, campos.adjudicatario.fragmento,
                    )
                )
        elif item.tipo in (TipoDocumento.propuesta_lc27, TipoDocumento.resolucion_adjudicacion):
            # Misma familia de etiquetas fijas en ambas plantillas (CONTEXTO.md
            # sección 17: Propuesta y Resolución declaran los mismos importes
            # del mismo procedimiento) — se tratan igual aquí, "primera que
            # aparece gana" ya cubre la preferencia por la Resolución cuando
            # las dos existen, porque `documentos` no tiene orden fijo pero
            # el importe es idéntico en cualquiera de las dos.
            lic = extraer_importe_licitacion_lc27(item.paginas)
            adj = extraer_importe_adjudicacion_lc27(item.paginas)
            obj = extraer_objeto_contrato_lc27(item.paginas)
            adjc = extraer_adjudicatario_lc27(item.paginas)
            # Bloque 3, sesión 2026-09-10: un importe encontrado por
            # etiqueta pero no interpretable (mismo hallazgo que
            # `app.extraccion.campos_pcsp.importe_como_decimal`, CONTEXTO.md
            # sección 12) se trata como "no encontrado" -- deja
            # `licitacion_lc27`/`adjudicacion_lc27` en `None`, elegible para
            # que un documento posterior sí lo resuelva, en vez de tumbar el
            # expediente entero.
            if lic and licitacion_lc27 is None:
                try:
                    licitacion_lc27 = (parsear_importe_es(lic.valor), item.documento.id, lic.pagina, lic.fragmento)
                except ValueError:
                    pass
            if adj and adjudicacion_lc27 is None:
                try:
                    adjudicacion_lc27 = (parsear_importe_es(adj.valor), item.documento.id, adj.pagina, adj.fragmento)
                except ValueError:
                    pass
            if obj and objeto_lc27 is None:
                objeto_lc27 = (obj.valor, item.documento.id, obj.pagina, obj.fragmento)
            if adjc and adjudicatario_lc27 is None:
                adjudicatario_lc27 = (adjc.valor, item.documento.id, adjc.pagina, adjc.fragmento)

        if registrar_baja_importe and item.tipo in _TIPOS_CON_BAJA_DECLARADA:
            baja = extraer_baja_declarada(item.paginas, tipo_documento=item.tipo)
            if baja is not None:
                candidatos_baja.append(baja)
                baja_doc[id(baja)] = item.documento.id
                baja_codigo_propio[id(baja)] = extraer_codigo_propio_documento(item.paginas)

    fuente_objeto = objeto_pcsp or objeto_lc27
    if fuente_objeto and not expediente.nombre_proyecto:
        expediente.nombre_proyecto = fuente_objeto[0]
        _traza(db, expediente.id, "nombre_proyecto", *fuente_objeto[1:], fuente_objeto[0])

    if not registrar_baja_importe:
        return None, None, None, None, motivo_multi_lote_pcsp, multi_lote_pcsp_detectado

    fuente_licitacion = _combinar_fuente(licitacion_pcsp, licitacion_lc27)
    fuente_adjudicacion = _combinar_fuente(adjudicacion_pcsp, adjudicacion_lc27)
    if fuente_licitacion and fuente_licitacion is not INVALIDADO:
        _traza(db, expediente.id, "importe_licitacion", *fuente_licitacion[1:], fuente_licitacion[0])
    if fuente_adjudicacion and fuente_adjudicacion is not INVALIDADO:
        _traza(db, expediente.id, "importe_adjudicacion", *fuente_adjudicacion[1:], fuente_adjudicacion[0])

    # Sesión de medición del alcance, parte 2: excluir las candidatas cuyo
    # documento declara explícitamente OTRO "Contrato nº" -- son de un
    # expediente hermano, no de este, aunque compartan el mismo
    # `DocumentoExpediente` (caso real: 6.23/28510.0139 y sus dos pedidos,
    # dos CONTRATOs con bajas distintas, 5,07 % y 0,40 %, ambos vinculados a
    # los tres). Si TODAS las candidatas quedan excluidas así (había baja
    # declarada, pero ninguna es confirmadamente de este expediente),
    # `INVALIDADO` en vez de `None` -- ver `app.extraccion.invalidado`.
    codigo_actual = normalizar_codigo_expediente(expediente.codigo_expediente)
    ids_codigo_ajeno = {
        id(c) for c in candidatos_baja
        if baja_codigo_propio.get(id(c)) is not None
        and normalizar_codigo_expediente(baja_codigo_propio[id(c)]) != codigo_actual
    }
    candidatos_baja_propios = [c for c in candidatos_baja if id(c) not in ids_codigo_ajeno]
    if ids_codigo_ajeno and not candidatos_baja_propios:
        motivo_multi_lote_pcsp = _acumular_motivo(
            motivo_multi_lote_pcsp,
            f"{len(ids_codigo_ajeno)} baja(s) declarada(s) en documento(s) compartido(s) con expediente(s) "
            "hermano(s) (cada documento declara explícitamente su propio 'Contrato nº', ninguno coincide "
            "con el de este expediente) -- ninguna se usa, para no atribuir la baja de otro lote",
        )
        baja_preferida = INVALIDADO
    else:
        baja_preferida = elegir_baja_preferida(candidatos_baja_propios)
    if baja_preferida is not None and baja_preferida is not INVALIDADO:
        _traza(
            db, expediente.id, "baja_declarada", baja_doc.get(id(baja_preferida)),
            baja_preferida.pagina, baja_preferida.fragmento, baja_preferida.baja,
        )

    # Prioridad Anuncio PCSP sobre LC.27/Resolución, mismo criterio que
    # licitación/adjudicación de arriba (CONTEXTO.md sección 4): LC.27 es la
    # reserva para expedientes sin Anuncio PCSP, verificado con las 3
    # matrices de carril (ninguna trae Anuncio PCSP, docs/descubrimiento-
    # inverso-matriz-pedidos.md sección 7).
    fuente_adjudicatario = _combinar_fuente(adjudicatario_pcsp, adjudicatario_lc27)
    if fuente_adjudicatario and fuente_adjudicatario is not INVALIDADO:
        _traza(db, expediente.id, "adjudicatario", *fuente_adjudicatario[1:], fuente_adjudicatario[0])

    importe_licitacion = _valor_final(fuente_licitacion)
    importe_adjudicacion = _valor_final(fuente_adjudicacion)
    adjudicatario = _valor_final(fuente_adjudicatario)
    return (
        importe_licitacion, importe_adjudicacion, baja_preferida, adjudicatario,
        motivo_multi_lote_pcsp, multi_lote_pcsp_detectado,
    )


def _procesar_lotes_declarados(
    db: Session, expediente: Expediente, lotes_declarados: list[LoteDeclarado], documento_id: Optional[int],
) -> tuple[list[Lote], Optional[str]]:
    """Un lote por cada `LoteDeclarado`: la baja se extrae del texto, nunca
    se calcula (CONTEXTO.md sección 4), pero se contrasta contra los importes
    de ESE lote con `calcular_baja_efectiva` — el mismo caso "0 % ingenuo"
    de la sección 4 puede darse lote a lote, no solo a nivel de expediente."""
    lotes: list[Lote] = []
    motivo_revision: Optional[str] = None
    for declarado in lotes_declarados:
        baja_efectiva = declarado.baja
        if declarado.importe_licitacion is not None and declarado.importe_adjudicacion is not None:
            resultado = calcular_baja_efectiva(
                declarado.importe_licitacion, declarado.importe_adjudicacion, declarado.baja,
            )
            baja_efectiva = resultado.baja
            if resultado.requiere_revision:
                motivo_revision = _acumular_motivo(motivo_revision, f"lote {declarado.identificador}: {resultado.motivo}")

        lote = _obtener_o_crear_lote(db, expediente.id, declarado.identificador)
        lote.baja_lote = baja_efectiva
        lote.importe_licitacion = declarado.importe_licitacion
        lote.importe_adjudicacion = declarado.importe_adjudicacion
        lote.adjudicatario = declarado.adjudicatario
        if declarado.codigo_expediente_lote:
            lote.codigo_expediente_lote = declarado.codigo_expediente_lote
        db.commit()
        db.refresh(lote)
        lotes.append(lote)

        _traza(
            db, lote.id, "baja_declarada", declarado.documento_id or documento_id, declarado.pagina,
            declarado.fragmento, declarado.baja, entidad_tipo="lote",
        )
    return lotes, motivo_revision


def _resumir_lotes_en_expediente(expediente: Expediente, lotes: list[Lote]) -> None:
    """CONTEXTO.md, encargo de esta sesión, punto 4: "un expediente con lotes
    de bajas distintas no tiene una baja única" — no se inventa una media.
    `baja_variable_por_lote` es lo que le dice a la web que explique el
    vacío de `baja_global` en vez de dejarlo parecer un fallo (ajuste 3)."""
    importes_licitacion = [l.importe_licitacion for l in lotes if l.importe_licitacion is not None]
    importes_adjudicacion = [l.importe_adjudicacion for l in lotes if l.importe_adjudicacion is not None]
    expediente.importe_licitacion = sum(importes_licitacion) if importes_licitacion else None
    expediente.importe_adjudicacion = sum(importes_adjudicacion) if importes_adjudicacion else None

    bajas = {l.baja_lote for l in lotes if l.baja_lote is not None}
    if len(bajas) == 1:
        expediente.baja_global = next(iter(bajas))
        expediente.baja_variable_por_lote = False if len(lotes) > 1 else None
    elif len(bajas) > 1:
        expediente.baja_global = None
        expediente.baja_variable_por_lote = True
    else:
        expediente.baja_global = None
        expediente.baja_variable_por_lote = None


def ejecutar_extraccion_expediente(
    db: Session,
    storage: DocumentStorage,
    trabajo: TrabajoCola,
    model_provider: Optional[ModelProvider] = None,
) -> dict:
    if trabajo.expediente_id is None:
        raise RuntimeError("trabajo de extracción sin expediente_id")
    expediente = db.get(Expediente, trabajo.expediente_id)
    if expediente is None:
        raise RuntimeError(f"expediente_id {trabajo.expediente_id} no existe")

    if expediente.estado == EstadoExpediente.sin_publicar:
        # CONTEXTO.md sección 22: un expediente ya confirmado sin publicar no
        # tiene nada que extraer, y no se reprocesa por error si queda un
        # trabajo de extracción encolado de antes de que se confirmara (o si
        # alguien lo reencola a mano) -- sin este corte, ese trabajo lo
        # devolvería a `pendiente_revision` con un motivo mucho menos claro
        # ("sin documentos descargados"), perdiendo la marca ya verificada.
        return {
            "expediente": expediente.codigo_expediente,
            "documentos_procesados": 0,
            "documentos_pliego_omitidos": 0,
            "tablas_procesadas": 0,
            "lineas_creadas": 0,
            "lineas_actualizadas": 0,
            "lineas_podadas": 0,
            "llamadas_modelo": 0,
            "lotes": [],
            "baja_global": None,
            "estado": expediente.estado.value,
            "motivo_revision": expediente.error,
        }

    expediente.estado = EstadoExpediente.extrayendo
    expediente.error = None
    db.commit()

    try:
        # Sesión de colisión de hash entre expedientes hermanos (2026-09-08,
        # migración 0021): `Documento` ya no tiene `expediente_id` ni
        # `nombre_archivo` propios (un documento puede pertenecer a varios
        # expedientes) -- se listan por `DocumentoExpediente` y se adjunta
        # `nombre_archivo` como atributo de instancia (no una columna
        # mapeada, nunca se persiste) para que el resto de esta función siga
        # leyendo `item.documento.nombre_archivo` sin cambios.
        # Bloque 4, sesión 2026-09-12 (continuación, verificación de
        # determinismo): sin `order_by`, Postgres no garantiza el orden de
        # las filas devueltas -- puede variar entre dos ejecuciones idénticas
        # de esta misma consulta sin que cambie ningún dato. Verificado en
        # vivo reprocesando el corpus completo dos veces seguidas: el mismo
        # `codigo_precio` presente en dos documentos reales del mismo
        # expediente (`6.23/28510.0042`, ANEJO_1 y CONTRATO comparten una
        # fila "P-001" real) terminaba con `documento_origen_id`/`pagina`/
        # `precio_unitario` distintos entre pasadas -- toda la cascada
        # posterior asume "el primero de `documentos` que declara algo gana"
        # (`_priorizar_por_origen` usa `sorted`, que es estable, pero solo
        # preserva un orden de partida que ya tiene que ser estable) sin que
        # nada garantizara ese orden de partida. `Documento.id` (autonumérico,
        # asignado en el momento en que cada documento se registró por
        # primera vez) es estable entre ejecuciones aunque no codifique
        # ninguna prioridad semántica -- esa prioridad ya la deciden los
        # mecanismos existentes (`_priorizar_por_origen`, `elegir_baja_
        # preferida`, `_nivel_campo`), que solo necesitan un punto de partida
        # estable para desempatar siempre igual.
        filas_documentos = db.execute(
            select(Documento, DocumentoExpediente.nombre_archivo)
            .join(DocumentoExpediente, DocumentoExpediente.documento_id == Documento.id)
            .where(DocumentoExpediente.expediente_id == expediente.id)
            .order_by(Documento.id)
        ).all()
        documentos = []
        for doc, nombre_archivo in filas_documentos:
            doc.nombre_archivo = nombre_archivo
            documentos.append(doc)

        motivo_revision: Optional[str] = None
        estado_especial: Optional[EstadoExpediente] = None
        lineas_creadas = lineas_actualizadas = tablas_procesadas = llamadas_modelo = 0
        lineas_podadas = lineas_de_lotes_hermanos = 0
        documentos_procesados = 0
        documentos_pliego_omitidos: list[str] = []
        documentos_escaneados: list[str] = []
        motivo_escaneados: Optional[str] = None
        documentos_escaneados_sin_bloquear: Optional[str] = None
        nota_modelo_precio_indexado: Optional[str] = None
        campo_obra: Optional[CampoAnclado] = None
        lotes: list[Lote] = []
        lotes_declarados: list[LoteDeclarado] = []
        sin_documentos = not documentos
        # Motivo específico de "caso de precios unitarios sin baja
        # declarada" (app.extraccion.precios_unitarios): se guarda aparte en
        # vez de acumularse ya en `motivo_revision` porque la herencia de
        # matriz de más abajo puede resolverlo todavía -- solo se usa si,
        # tras intentarlo, la baja del lote sigue sin determinar.
        motivo_baja_diferido: Optional[str] = None

        if sin_documentos:
            # Sin documentos propios no hay nada que clasificar ni que leer
            # por etiqueta fija -- pero el cruce con el Excel de códigos
            # (CONTEXTO.md sección 7) no depende de los documentos, solo del
            # propio `codigo_expediente`: es el único camino que le queda a
            # un pedido derivado de acuerdo marco sin ningún documento
            # descargado (docs/analisis-corpus.md hallazgo 3, 7 de los 14
            # casos) para encontrar su matriz por la columna MATRIZ del
            # Excel (encargo de la sesión de herencia, requisito 1). Sin
            # este cruce aquí, estos 7 nunca podrían heredar nada aunque su
            # matriz sí esté disponible.
            motivo_revision = _acumular_motivo(motivo_revision, asegurar_cruce_codigos(db, expediente))
            expediente.aviso_conflicto_documento_manual = None
            db.commit()
            lotes = [_obtener_o_crear_lote(db, expediente.id, LOTE_UNICO)]
        else:
            items = _priorizar_por_origen(_clasificar_documentos(db, storage, list(documentos)))
            documentos_procesados = len(items)
            expediente.aviso_conflicto_documento_manual = _detectar_conflicto_origen(items)

            # CONTEXTO.md sección 26, criterio del cliente: solo bajas de
            # material por lotes, un contrato de obra queda fuera de alcance.
            # Se detecta pronto (mismo campo de etiqueta fija que ya lee
            # `_extraer_campos_expediente`, sección 2 de la cascada) para no
            # confundir "es una obra" con "falló la extracción" -- se
            # sobrescribe el motivo al final, después de que el resto de esta
            # rama termine, para que gane sobre cualquier motivo que el
            # intento de leer un cuadro de precios que no existe hubiera
            # dejado por el camino.
            campo_obra = _detectar_contrato_obra(items)

            # Identidad del expediente (CONTEXTO.md sección 20): antes de anclar
            # cualquier otro dato a este expediente, corrige su
            # `codigo_expediente` si sus propios Anuncio PCSP declaran uno
            # distinto -- el código con el que se registró suele ser en
            # realidad el de su matriz (docs/analisis-corpus.md, sesión de
            # herencia de matriz). Tiene que ir antes de
            # `_extraer_campos_expediente` (que rellena `codigo_matriz` si
            # está vacío) y antes del cruce con el Excel de códigos, para que
            # todo lo demás trabaje ya con la identidad correcta.
            motivo_revision = _acumular_motivo(motivo_revision, corregir_identidad_expediente(db, expediente, items))
            db.commit()

            # Bloque 4 (auditoría de documentos de adjudicación, sesión
            # 2026-09-09): después de que la identidad del expediente ya esté
            # corregida arriba, comprueba si el documento que el scraper
            # descargó como adjudicación menciona de verdad este expediente.
            motivo_revision = _acumular_motivo(
                motivo_revision,
                _detectar_documento_adjudicacion_no_relacionado(
                    items, expediente.codigo_expediente, expediente.codigo_matriz
                ),
            )

            # Nº de lotes declarado por el Anuncio PCSP (campo estructurado,
            # sección 27): única fuente para un expediente sin ninguna
            # Propuesta/Resolución con bloque narrativo por lote
            # (`6.23/28510.0139`) -- se detecta pronto para estar disponible
            # en las dos ramas de abajo.
            lotes_totales_pcsp = _detectar_numero_lotes_pcsp(items)

            resultado_lotes = _extraer_lotes_declarados_del_expediente(items)
            lotes_declarados = resultado_lotes.lotes
            lotes_hermanos: dict[str, Optional[str]] = {}
            # Sesión 2026-09-14 (tercera parte): el lote de este expediente
            # cuando es uno de los lotes de la licitación y lo sabe (ver
            # `procesar_anejo(lote_propio=...)`), y lo que dice de sí mismo
            # cada Contrato archivado con él.
            lote_propio: Optional[str] = None
            identidades_por_documento = {
                item.documento.id: extraer_identidad_contrato(item.paginas)
                for item in items
                if item.tipo == TipoDocumento.contrato
            }
            if lotes_declarados:
                # Camino multi-lote (o de un único lote declarado por su nombre
                # real, p.ej. si algún día aparece un "LOTE 2" suelto): los
                # importes/objeto de etiqueta fija del expediente (matriz,
                # nombre del proyecto) se siguen extrayendo igual, pero
                # importe_licitacion/adjudicacion/baja_global del expediente
                # salen de los lotes, no de un único campo de documento.
                _extraer_campos_expediente(db, expediente, items, registrar_baja_importe=False)

                # Contraste, nunca escritura: `codigo_principal_declarado`
                # es solo para detectar una identidad rota (mismo espíritu
                # que `corregir_identidad_expediente`), jamás se asigna a
                # `expediente.codigo_matriz` -- una de sus tres etiquetas
                # reales es literalmente "Nº EXPEDIENTE MATRIZ"
                # (`6.24/28510.0094`), una trampa de vocabulario sin
                # relación con acuerdo marco (CONTEXTO.md sección 27):
                # escribirla ahí reintroduciría el bug de autorreferencia
                # de las secciones 20/21.
                #
                # Un expediente que es uno de los lotes de la licitación
                # (`lotes_hermanos` no vacío) no tiene la identidad rota: que
                # el documento declare otro expediente principal es lo
                # esperado, y ya se sabe exactamente qué lote es.
                lotes_hermanos = _lotes_de_expedientes_hermanos(expediente, lotes_declarados)
                lote_propio = _lote_propio(expediente, lotes_declarados)
                for identificador, motivo_lote in (resultado_lotes.motivos_por_lote or {}).items():
                    if identificador not in lotes_hermanos:
                        motivo_revision = _acumular_motivo(motivo_revision, motivo_lote)
                principal = resultado_lotes.codigo_principal_declarado
                if not lotes_hermanos and lote_propio is None and principal is not None and normalizar_codigo_expediente(
                    principal.valor
                ) != normalizar_codigo_expediente(expediente.codigo_expediente):
                    motivo_revision = _acumular_motivo(
                        motivo_revision,
                        f"el documento declara 'EXPEDIENTE PRINCIPAL/ORIGEN' {principal.valor}, distinto del "
                        f"expediente bajo el que están archivados sus documentos ({expediente.codigo_expediente})",
                    )

                _eliminar_lote_sentinela_obsoleto(db, expediente.id, lotes_declarados)
                _eliminar_lotes_de_hermanos(db, expediente.id, set(lotes_hermanos))
                lotes, motivo_lotes = _procesar_lotes_declarados(
                    db, expediente, [d for d in lotes_declarados if d.identificador not in lotes_hermanos],
                    resultado_lotes.documento_id,
                )
                motivo_revision = _acumular_motivo(motivo_revision, motivo_lotes)
                _resumir_lotes_en_expediente(expediente, lotes)
                expediente.lotes_totales_declarados = (
                    resultado_lotes.lotes_totales_declarados or lotes_totales_pcsp
                )

                # Cobertura parcial (sesión de identidad de lote, CONTEXTO.md
                # sección 27, encargo explícito del cliente): "un expediente
                # del que solo conocemos 2 de 13 lotes no puede figurar como
                # completado". Se compara contra los lotes que SÍ traen dato
                # real (baja o importe), no solo contra `len(lotes)` -- un
                # lote mencionado por nombre en la cabecera pero sin ningún
                # bloque de adjudicación (ninguno de los 15 reales, pero
                # `_procesar_lotes_declarados` lo modela igual, sección 27)
                # no cuenta como "conocido" para este cálculo.
                #
                # Un expediente que es uno de los lotes solo responde de SU
                # lote: los demás son de sus hermanos.
                if lotes_hermanos or lote_propio is not None:
                    if all(l.baja_lote is None and l.importe_adjudicacion is None for l in lotes):
                        motivo_revision = _acumular_motivo(
                            motivo_revision,
                            f"el lote propio de este expediente (lote {lotes[0].identificador_lote}) no trae "
                            "baja ni importe de adjudicación en ningún documento",
                        )
                elif expediente.lotes_totales_declarados is not None:
                    lotes_con_datos = [
                        l for l in lotes if l.baja_lote is not None or l.importe_adjudicacion is not None
                    ]
                    if len(lotes_con_datos) < expediente.lotes_totales_declarados:
                        identificadores = sorted(
                            (l.identificador_lote for l in lotes_con_datos), key=lambda x: (len(x), x)
                        )
                        motivo_revision = _acumular_motivo(
                            motivo_revision,
                            f"cobertura parcial: {len(lotes_con_datos)} de "
                            f"{expediente.lotes_totales_declarados} lotes declarados tienen baja/importe "
                            f"(con datos: {', '.join(identificadores) or 'ninguno'})",
                        )
            else:
                # Camino de siempre: un único lote implícito (CONTEXTO.md,
                # encargo de esta sesión, punto 1). La falta de importe/baja
                # ya no se explica en línea aquí: si el expediente declara
                # una matriz, la herencia de más abajo puede resolverla
                # todavía — el motivo genérico de "no se pudo determinar la
                # baja" solo se compone al final, después de intentarlo.
                (
                    importe_licitacion, importe_adjudicacion, baja_preferida, adjudicatario,
                    motivo_multi_lote_pcsp, multi_lote_pcsp_detectado,
                ) = _extraer_campos_expediente(db, expediente, items)
                motivo_revision = _acumular_motivo(motivo_revision, motivo_multi_lote_pcsp)

                # `INVALIDADO` (app.extraccion.invalidado) solo importa para
                # decidir, más abajo, si hay que BORRAR un valor ya guardado
                # -- para el cálculo de baja de aquí en medio se trata igual
                # que "no hay dato" (nunca como un importe real con el que
                # operar). `adjudicatario_invalidado` se guarda aparte
                # porque la asignación a `lote.adjudicatario`, más abajo,
                # necesita distinguir "no tengo nada nuevo, no lo toco" de
                # "sé que lo que hay no vale, bórralo".
                adjudicatario_invalidado = adjudicatario is INVALIDADO
                if importe_licitacion is INVALIDADO:
                    importe_licitacion = None
                if importe_adjudicacion is INVALIDADO:
                    importe_adjudicacion = None
                if adjudicatario_invalidado:
                    adjudicatario = None
                if baja_preferida is INVALIDADO:
                    # `lote.baja_lote = baja_efectiva`, más abajo, ya
                    # sobrescribe sin condición (igual que los importes) --
                    # basta con que `baja_preferida` deje de ser
                    # `INVALIDADO` para que el cálculo de más abajo la
                    # trate como "no declarada" y borre lo que hubiera.
                    baja_preferida = None

                # Segunda familia de baja (migración 0016, sesión de trabajo
                # pendiente real 2026-09-05): antes de intentar la baja
                # única de lote, comprobar si el propio expediente declara
                # el modelo de precio indexado por pedido -- si lo hace, ni
                # `calcular_baja_efectiva` ni la baja declarada en texto
                # aplican, porque ese modelo no tiene una baja única que
                # extraer (ver docstring de `ModeloPrecio` en app.models).
                modelo_indexado = None
                for item in items:
                    modelo_indexado = detectar_modelo_precio_indexado(item.paginas)
                    if modelo_indexado is not None:
                        break

                baja_efectiva: Optional[Decimal] = None
                if modelo_indexado is not None:
                    pass  # baja_efectiva se queda en None a propósito
                elif importe_licitacion is not None and importe_adjudicacion is not None:
                    resultado_baja = calcular_baja_efectiva(
                        importe_licitacion, importe_adjudicacion,
                        baja_preferida.baja if baja_preferida is not None else None,
                    )
                    baja_efectiva = resultado_baja.baja
                    if resultado_baja.requiere_revision:
                        if baja_efectiva is None:
                            # Caso de precios unitarios sin baja declarada:
                            # `baja_efectiva` sigue sin valor, así que la
                            # herencia de matriz de más abajo todavía puede
                            # resolverlo -- no se fija ya, se difiere.
                            motivo_baja_diferido = resultado_baja.motivo
                        else:
                            # Hay una baja (declarada, pero que no cuadra con
                            # los importes): es un problema real de este
                            # expediente, ajeno a si tiene matriz.
                            motivo_revision = _acumular_motivo(motivo_revision, resultado_baja.motivo)
                elif baja_preferida is not None:
                    baja_efectiva = baja_preferida.baja

                expediente.importe_licitacion = importe_licitacion
                expediente.importe_adjudicacion = importe_adjudicacion
                expediente.baja_global = baja_efectiva
                expediente.baja_variable_por_lote = None

                # Sesión 2026-09-14 (tercera parte): sin ningún documento de
                # lotes, el Contrato del propio expediente puede decir qué
                # lote es ("Contrato nº" = su código, "LOTE N"). Entonces el
                # lote implícito es ese LOTE N, con su código, y los demás
                # Contratos archivados con él son de sus hermanos -- caso
                # real: `6.21/28510.0112` (LOTE 4) y `0113` (LOTE 5) guardaban
                # como su lote "1" las tablas de todos los lotes del anejo
                # que comparten.
                identidades_contratos = _identidades_de_contratos(items)
                codigo_propio = normalizar_codigo_expediente(expediente.codigo_expediente)
                identidad_propia = next(
                    (
                        identidad
                        for identidad, _ in identidades_contratos
                        if normalizar_codigo_expediente(identidad.codigo_expediente_lote) == codigo_propio
                    ),
                    None,
                )
                identificador_implicito = LOTE_UNICO
                if identidad_propia is not None:
                    identificador_implicito = lote_propio = identidad_propia.identificador
                    lotes_hermanos = {
                        identidad.identificador: identidad.codigo_expediente_lote
                        for identidad, _ in identidades_contratos
                        if identidad is not identidad_propia
                    }
                    _eliminar_lotes_de_hermanos(
                        db, expediente.id,
                        {
                            l.identificador_lote
                            for l in db.execute(select(Lote).where(Lote.expediente_id == expediente.id)).scalars()
                            if l.identificador_lote != identificador_implicito
                        },
                    )
                lote = _obtener_o_crear_lote(db, expediente.id, identificador_implicito)
                if identidad_propia is not None:
                    lote.codigo_expediente_lote = identidad_propia.codigo_expediente_lote
                lote.baja_lote = baja_efectiva
                lote.importe_licitacion = importe_licitacion
                lote.importe_adjudicacion = importe_adjudicacion
                if adjudicatario_invalidado:
                    # Encontrado pero no atribuible con confianza (documento
                    # multi-lote ambiguo): a diferencia de "no hay nada
                    # nuevo" (`adjudicatario is None` sin más, que deja el
                    # valor ya guardado tal cual), aquí SÍ se borra -- ese
                    # valor guardado pudo venir de la misma fuente ambigua
                    # en una pasada anterior (caso real: 12 de los 14
                    # expedientes de "balasto" seguían mostrando el
                    # adjudicatario de un lote hermano).
                    lote.adjudicatario = None
                elif adjudicatario is not None:
                    lote.adjudicatario = adjudicatario
                if modelo_indexado is not None:
                    lote.modelo_precio = ModeloPrecio.indexado_por_pedido
                    lote.coeficiente_transformacion = modelo_indexado.coeficiente_transformacion
                    nota_modelo_precio_indexado = (
                        "modelo de precio indexado por pedido (Acuerdo Marco, no baja única de lote): "
                        "la baja no existe todavía en la licitación, se fija en cada pedido futuro contra "
                        "el Acuerdo Marco junto con un índice de actualización de precios (Kt); no es un "
                        "dato que el sistema no haya encontrado"
                    )
                else:
                    # Idempotencia (CONTEXTO.md sección 9): un reproceso que ya
                    # no detecte el marcador (documento corregido, o el
                    # propio marcador dejó de estar) no debe dejar un
                    # `indexado_por_pedido` obsoleto de una ejecución previa.
                    lote.modelo_precio = ModeloPrecio.fijo
                    lote.coeficiente_transformacion = None
                db.commit()
                lotes = [lote]

                expediente.lotes_totales_declarados = lotes_totales_pcsp
                # Sesión 2026-09-14 (tercera parte): un expediente que es uno
                # de los lotes y lo sabe por su Contrato solo responde de su
                # lote (mismo criterio que el camino de lotes declarados).
                if (
                    lotes_totales_pcsp is not None and lotes_totales_pcsp > 1 and not multi_lote_pcsp_detectado
                    and lote_propio is None
                ):
                    # Caso real más peligroso de la sesión de identidad de
                    # lote: `6.23/28510.0139` declara "2 lotes" (el propio
                    # Anuncio PCSP lo confirma, "Nº de Lotes: 2") pero no
                    # trae ninguna Propuesta LC.27 ni Resolución de la que
                    # sacar el desglose por lote -- `lote` de arriba es el
                    # sentinela `LOTE_UNICO`, no un lote identificado por
                    # número, así que cuenta como 0 lotes conocidos aunque
                    # haya podido sacar baja/importe de algún otro sitio
                    # (p.ej. el Contrato): ese valor sería el de un solo
                    # lote de los 2, presentado sin saber de cuál -- el
                    # mismo riesgo que ya diagnosticó CONTEXTO.md sección 26
                    # para 6.24/28510.0088, aquí sin ni siquiera un
                    # documento que lo desglose.
                    #
                    # `not multi_lote_pcsp_detectado` (sesión de medición del
                    # alcance, 2026-09-08): si el propio Anuncio PCSP SÍ trae
                    # el desglose "Nº Lote: NNN" (tercera variante,
                    # `app.extraccion.lotes_pcsp`), este motivo genérico
                    # sería falso ("no trae ninguna... que declare la
                    # adjudicación lote a lote") -- ese caso ya lo explica
                    # `motivo_multi_lote_pcsp` (ambiguo) o no necesita
                    # ningún motivo (resuelto).
                    motivo_revision = _acumular_motivo(
                        motivo_revision,
                        f"cobertura parcial: 0 de {lotes_totales_pcsp} lotes identificados por número "
                        "(el expediente no trae ninguna Propuesta LC.27 ni Resolución de Adjudicación "
                        "que declare la adjudicación lote a lote)",
                    )

            motivo_revision = _acumular_motivo(motivo_revision, asegurar_cruce_codigos(db, expediente))
            db.commit()

            lotes_por_identificador = {l.identificador_lote: l.id for l in lotes}
            # Los lotes de los hermanos siguen contando para asociar cada
            # tabla a su "LOTE N" (si no, sus tablas se leerían como de un
            # lote no declarado, huérfanas); sus líneas se descartan al
            # guardar, más abajo.
            bajas_por_identificador = {
                **{identificador: None for identificador in lotes_hermanos},
                **{l.identificador_lote: l.baja_lote for l in lotes},
            }
            hermanos_en_catalogo = _hermanos_en_catalogo(db, lotes_hermanos)

            # Etapas 3-6: el cuadro de precios se busca por contenido en TODOS
            # los documentos, nunca solo en los clasificados como "anejo"
            # (CONTEXTO.md sección 3: los *_ANEJO_N.pdf son a veces el Pliego
            # completo, y localizar_paginas_candidatas ya descarta barato lo que
            # no trae tabla). Cada documento se procesa de forma aislada: una
            # tabla que no se puede mapear (cabecera nunca vista y sin modelo
            # configurado) manda ESE documento a revisión, no tira las líneas ya
            # extraídas de los demás — CONTEXTO.md sección 12, "lo que no cuadra
            # va a la cola de revisión", no revienta el expediente entero.
            documentos_con_error: list[str] = []
            # Líneas guardadas en esta pasada por los documentos anteriores
            # (`guardar_lineas_catalogo(ids_vivas=...)`).
            ids_tocadas_expediente: set[int] = set()
            for item in items:
                if item.pliego_sin_precios:
                    # CONTEXTO.md sección 26: pliego administrativo o PCAP,
                    # verificado sin cuadro de precios en todo el corpus real
                    # -- ni localizar páginas candidatas ni extraer tabla
                    # gastan tiempo en él. No es un error ni algo que mandar a
                    # revisión, así que no toca `motivo_revision`.
                    documentos_pliego_omitidos.append(item.documento.nombre_archivo)
                    continue
                if item.escaneado:
                    # Sin capa de texto no hay páginas candidatas que buscar
                    # ni cabecera que mapear (CONTEXTO.md sección 3): intentar
                    # `procesar_anejo` igual solo gastaría tiempo abriendo el
                    # PDF para no encontrar nada. Se registra aparte de
                    # `documentos_con_error` para que el motivo final lo diga
                    # con precisión ("documento escaneado"), no con el
                    # genérico "no se pudo extraer el cuadro de precios".
                    documentos_escaneados.append(item.documento.nombre_archivo)
                    continue
                contenido = storage.recuperar(item.documento.ruta_almacenamiento)
                # Todo el trabajo de este documento —extraer, y guardar sus
                # líneas— vive en el mismo bloque try/except con un único commit
                # al final (CONTEXTO.md, sesión de rodaje 2026-09-03, punto 2): un
                # error de base de datos al guardar (p.ej. un valor que revienta
                # una columna) es tan aislable por documento como uno de mapeo de
                # cabecera, y antes tiraba el expediente entero porque el
                # guardado vivía fuera de este try. El punto 3 de la misma
                # sesión: o se guarda entero este documento, o el rollback lo
                # deshace entero — nunca quedan restos de un grupo guardado y
                # otro no, dentro del mismo documento.
                lineas_creadas_doc = lineas_actualizadas_doc = 0
                try:
                    resultado = procesar_anejo(
                        io.BytesIO(contenido), item.paginas, item.documento.id, expediente.id,
                        bajas_por_identificador, db, model_provider,
                        lote_propio=lote_propio,
                        documento_de_otro_lote=_es_contrato_de_otro_lote(
                            expediente, identidades_por_documento, item.documento.id
                        ),
                    )
                    if resultado.lineas:
                        grupos: dict[Optional[str], list[dict]] = {}
                        for linea in resultado.lineas:
                            identificador = linea.pop("identificador_lote")
                            grupos.setdefault(identificador, []).append(linea)
                        # Bloque 4, sesión 2026-09-10: `ids_tocadas` de TODOS
                        # los grupos de este documento, para podar al final
                        # (ver docstring de `podar_lineas_obsoletas_de_documento`)
                        # -- nunca dentro del bucle, porque un grupo no debe
                        # podar lo que otro grupo del MISMO documento acaba
                        # de tocar.
                        ids_tocadas_documento: set[int] = set()
                        for identificador, lineas_grupo in grupos.items():
                            lote_id = lotes_por_identificador.get(identificador) if identificador is not None else None
                            if identificador in lotes_hermanos:
                                if identificador in hermanos_en_catalogo:
                                    lineas_de_lotes_hermanos += len(lineas_grupo)
                                    continue
                                lineas_grupo = _como_lineas_de_otro_expediente(
                                    lineas_grupo, identificador, lotes_hermanos[identificador]
                                )
                                lote_id = None
                            guardado = guardar_lineas_catalogo(
                                db, lote_id, lineas_grupo,
                                ids_vivas=frozenset(ids_tocadas_expediente | ids_tocadas_documento),
                            )
                            lineas_creadas_doc += guardado.creadas
                            lineas_actualizadas_doc += guardado.actualizadas
                            ids_tocadas_documento |= guardado.ids_tocadas
                        # Silenciosa a propósito, sin motivo_revision (no
                        # manda el expediente a revisión): mismo criterio que
                        # `_limpiar_huerfana_superada`, que ya borra huérfanas
                        # superadas sin avisar -- la poda es idempotencia
                        # esperada, no un hallazgo dudoso. Se cuenta igual
                        # (`lineas_podadas`, en el resumen final) para que
                        # quede visible en el informe del reproceso.
                        lineas_podadas += podar_lineas_obsoletas_de_documento(
                            db, expediente.id, item.documento.id, frozenset(ids_tocadas_documento)
                        )
                    item.documento.procesado_en = datetime.now(timezone.utc)
                    db.commit()
                    if resultado.lineas:
                        ids_tocadas_expediente |= ids_tocadas_documento
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    documentos_con_error.append(f"{item.documento.nombre_archivo}: {exc}")
                    continue
                lineas_creadas += lineas_creadas_doc
                lineas_actualizadas += lineas_actualizadas_doc
                tablas_procesadas += resultado.tablas_procesadas
                llamadas_modelo += resultado.llamadas_modelo
                if resultado.tablas_sin_lote:
                    motivo_revision = _acumular_motivo(
                        motivo_revision,
                        f"{item.documento.nombre_archivo}: " + "; ".join(resultado.tablas_sin_lote),
                    )
                if resultado.lineas_con_aviso:
                    motivo_revision = _acumular_motivo(
                        motivo_revision,
                        f"{item.documento.nombre_archivo}: {resultado.lineas_con_aviso} línea(s) con un valor "
                        "que no se pudo interpretar, marcadas para revisión",
                    )

            if documentos_con_error:
                motivo_documentos = "no se pudo extraer el cuadro de precios de: " + "; ".join(documentos_con_error)
                motivo_revision = _acumular_motivo(motivo_revision, motivo_documentos)

            if documentos_escaneados:
                # Texto calculado aquí, pero incorporado a `motivo_revision`
                # más abajo -- una vez que se sepa si el resto del
                # expediente (líneas, cobertura de lotes, baja) quedó
                # completo sin este documento o no (sesión de trabajo
                # pendiente real, 2026-09-05, ver el bloque que usa esta
                # variable).
                motivo_escaneados = (
                    "documento(s) escaneado(s), sin capa de texto (fuera de alcance sin OCR o modelo "
                    "multimodal, CONTEXTO.md sección 15): " + "; ".join(documentos_escaneados)
                )

        total_lineas = lineas_creadas + lineas_actualizadas

        # Herencia de acuerdo marco (docs/analisis-corpus.md hallazgo 3):
        # solo tiene sentido para el lote único implícito -- ningún pedido
        # derivado del corpus declara "En el LOTE N" propio, y sin ese dato
        # no habría forma de saber a qué lote de un pedido multi-lote
        # correspondería la matriz. Solo se intenta si al pedido le falta el
        # cuadro de precios o la baja ("heredar lo que el pedido no tiene"),
        # y nunca si las dos fuentes de matriz ya se marcaron en conflicto
        # (`asegurar_cruce_codigos` más arriba): ahí no hay una matriz
        # fiable de la que heredar.
        if not lotes_declarados and not expediente.matriz_conflicto and expediente.codigo_matriz and lotes:
            lote_pedido = lotes[0]
            if total_lineas == 0 or lote_pedido.baja_lote is None:
                resolucion = resolver_o_encolar_matriz(db, expediente)
                if resolucion.estado == EstadoResolucionMatriz.ciclo:
                    motivo_revision = _acumular_motivo(motivo_revision, resolucion.motivo)
                elif resolucion.estado == EstadoResolucionMatriz.en_proceso:
                    estado_especial = EstadoExpediente.esperando_matriz
                    motivo_revision = _acumular_motivo(
                        motivo_revision,
                        f"esperando a que se procese la matriz {resolucion.matriz.codigo_expediente}",
                    )
                elif resolucion.estado == EstadoResolucionMatriz.lista:
                    resultado_herencia = intentar_heredar_de_matriz(
                        db, expediente, resolucion.matriz, lote_pedido, total_lineas,
                    )
                    if resultado_herencia.motivo_revision is not None:
                        motivo_revision = _acumular_motivo(motivo_revision, resultado_herencia.motivo_revision)
                    else:
                        lineas_creadas += resultado_herencia.lineas_creadas
                        lineas_actualizadas += resultado_herencia.lineas_actualizadas
                        total_lineas += resultado_herencia.lineas_creadas + resultado_herencia.lineas_actualizadas
                        expediente.baja_global = lote_pedido.baja_lote
                        expediente.importe_licitacion = expediente.importe_licitacion or lote_pedido.importe_licitacion
                        expediente.importe_adjudicacion = expediente.importe_adjudicacion or lote_pedido.importe_adjudicacion
                db.commit()

        if motivo_revision is None and total_lineas == 0:
            if sin_documentos:
                motivo_revision = "extracción encolada sin documentos descargados para este expediente"
            elif motivo_escaneados is not None:
                # Motivo aparte y explícito (CONTEXTO.md sección 3): distinto
                # de "no se pudo extraer el cuadro de precios" (ese documento
                # sí tiene texto, solo falló su tabla) y de "no se extrajo
                # ninguna línea de catálogo" (ese expediente sí tiene
                # documentos legibles, solo no traían cuadro de precios).
                # Este dice que el documento no se puede leer en absoluto con
                # las herramientas actuales -- y aquí sí es la única
                # explicación posible de por qué no hay líneas, porque
                # `total_lineas` es 0 y no hubo ningún otro documento que
                # aportara nada.
                motivo_revision = motivo_escaneados
                motivo_escaneados = None  # ya incorporado, que no se repita más abajo
            elif not any(
                item.tipo in (TipoDocumento.anejo, TipoDocumento.pliego) and not item.pliego_sin_precios
                for item in items
            ):
                # Sesión de expedientes sin cuadro de precios (2026-09-05,
                # `6.24/28510.0025` y `6.24/28510.0193`): verificado en vivo
                # contra la Plataforma real que la ficha de estos dos
                # expedientes solo publica Adjudicación y Contrato -- ningún
                # Anejo ni Pliego técnico, ni como fila propia ni embebido en
                # el pliego (`pliego_embedded_urls`). El propio Contrato
                # remite el cuadro de precios a "el Anejo 1 del PPT", un
                # documento que la Plataforma nunca llegó a publicar para
                # este expediente -- no es un fallo del scraper ni del
                # localizador de tablas, es una ausencia real de la fuente.
                # No se generaliza a cualquier expediente sin líneas: se
                # restringe a los que ni siquiera tienen un Anejo/Pliego con
                # posibilidad de traer precios, el único patrón verificado
                # contra la Plataforma real hasta ahora.
                tipos = sorted({item.tipo.value for item in items})
                motivo_revision = (
                    "no se extrajo ninguna línea de catálogo: el expediente no trae ningún Anejo ni "
                    f"Pliego técnico con posible cuadro de precios, solo {', '.join(tipos)} — "
                    "verificar en la Plataforma si existe un Anejo/PPT no publicado o no adjuntado, "
                    "antes de asumir que es un expediente sin cuadro de precios"
                )
            else:
                motivo_revision = "no se extrajo ninguna línea de catálogo de los documentos descargados"
        if motivo_revision is None and not any(
            l.baja_lote is not None or l.modelo_precio == ModeloPrecio.indexado_por_pedido for l in lotes
        ):
            motivo_revision = motivo_baja_diferido or "no se pudo determinar la baja de ningún lote"

        if motivo_escaneados is not None:
            # Sesión de trabajo pendiente real (2026-09-05, `6.20/28510.0136`):
            # antes, un documento escaneado mandaba el expediente entero a
            # revisión sin condición, aunque el resto de documentos ya
            # hubiera resuelto baja, importes y cobertura completa de lotes
            # -- ese es justo el caso real de `0136` (verificado a mano,
            # muestreo visual de 11 páginas del propio `ANEJO_2`: es el
            # Pliego de Cláusulas Administrativas, la misma familia que
            # CONTEXTO.md sección 26 ya confirmó sin cuadro de precios en 93
            # páginas reales de otro expediente; el cuadro de precios real
            # de este expediente ya sale de `ANEJO_3`, con capa de texto).
            # Si llegamos aquí es porque `total_lineas` no era 0 (si lo
            # fuera, el bloque de arriba ya habría consumido este motivo) --
            # si `motivo_revision` sigue vacío, ningún otro chequeo
            # (cobertura parcial, baja) encontró un hueco tampoco: el
            # documento no legible no impidió nada, y forzar revisión de
            # todas formas solo por su existencia sería más cauto de lo que
            # los propios datos justifican. Si en cambio ya hay otro motivo,
            # el documento escaneado se deja como posible causa a mano,
            # igual que antes.
            if motivo_revision is not None:
                motivo_revision = _acumular_motivo(motivo_revision, motivo_escaneados)
            else:
                documentos_escaneados_sin_bloquear = motivo_escaneados

        if campo_obra is not None:
            # Gana sobre cualquier motivo que el intento de leer un cuadro de
            # precios que no existe (porque el expediente es de obra, no de
            # material) hubiera dejado por el camino -- CONTEXTO.md sección 26.
            estado_especial = EstadoExpediente.fuera_de_alcance
            motivo_revision = (
                f'contrato de obra ("Tipo de Contrato: {campo_obra.valor}"), fuera de alcance del motor de '
                "materiales (criterio del cliente, CONTEXTO.md sección 26)"
            )

        if estado_especial is not None:
            expediente.estado = estado_especial
            expediente.error = motivo_revision
        elif motivo_revision is not None:
            expediente.estado = EstadoExpediente.pendiente_revision
            expediente.error = motivo_revision
        else:
            expediente.estado = EstadoExpediente.completado
            expediente.error = None
        db.commit()

        if reencolar_pedidos_esperando_matriz(db, expediente):
            db.commit()

        return {
            "expediente": expediente.codigo_expediente,
            "documentos_procesados": documentos_procesados,
            "documentos_pliego_omitidos": len(documentos_pliego_omitidos),
            "tablas_procesadas": tablas_procesadas,
            "lineas_creadas": lineas_creadas,
            "lineas_actualizadas": lineas_actualizadas,
            "lineas_podadas": lineas_podadas,
            "lineas_de_lotes_hermanos": lineas_de_lotes_hermanos,
            "llamadas_modelo": llamadas_modelo,
            "lotes": [l.identificador_lote for l in lotes],
            "baja_global": str(expediente.baja_global) if expediente.baja_global is not None else None,
            "estado": expediente.estado.value,
            "motivo_revision": motivo_revision,
            "aviso_documento_escaneado": documentos_escaneados_sin_bloquear,
            "nota_modelo_precio_indexado": nota_modelo_precio_indexado,
        }
    except Exception as exc:  # noqa: BLE001
        # Igual que en app.worker.ejecutar_trabajo: una excepción a mitad de
        # este bloque (p.ej. un fallo de conexión con Postgres, o un
        # IntegrityError que escapase del try por documento) deja la
        # transacción de `db` en estado "necesita rollback" — sin este
        # rollback, el `db.commit()` de abajo lanzaría un PendingRollbackError
        # que sustituiría a `exc` y enterraría el motivo real del fallo.
        db.rollback()
        expediente.estado = EstadoExpediente.fallido
        expediente.error = str(exc)
        db.commit()
        if reencolar_pedidos_esperando_matriz(db, expediente):
            db.commit()
        raise
