"""Trabajo de cola "extraer_expediente": encadena las seis etapas de la
cascada de extracción (CLAUDE.md sección 5) sobre todos los documentos ya
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
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.catalogo import guardar_lineas_catalogo
from app.extraccion.baja import BajaDeclarada, elegir_baja_preferida, extraer_baja_declarada
from app.extraccion.campos_lc27 import (
    extraer_importe_adjudicacion_lc27,
    extraer_importe_licitacion_lc27,
    extraer_objeto_contrato_lc27,
)
from app.extraccion.campos_pcsp import CampoAnclado, extraer_campos_anuncio_pcsp, importe_como_decimal
from app.extraccion.clasificador import clasificar, es_pliego_sin_precios
from app.extraccion.cruce_codigos import asegurar_cruce_codigos, normalizar_codigo_expediente
from app.extraccion.herencia_matriz import (
    EstadoResolucionMatriz,
    intentar_heredar_de_matriz,
    reencolar_pedidos_esperando_matriz,
    resolver_o_encolar_matriz,
)
from app.extraccion.identidad_expediente import corregir_identidad_expediente
from app.extraccion.lotes import LoteDeclarado, ResultadoLotes, extraer_lotes_declarados
from app.extraccion.normalizacion import parsear_importe_es
from app.extraccion.pipeline_anejo import procesar_anejo
from app.extraccion.precios_unitarios import calcular_baja_efectiva
from app.extraccion.texto import es_documento_escaneado, extraer_texto
from app.interfaces.document_storage import DocumentStorage
from app.interfaces.model_provider import ModelProvider
from app.models import (
    Documento,
    EstadoExpediente,
    Expediente,
    LineaCatalogo,
    Lote,
    TipoDocumento,
    TrabajoCola,
    TrazaOrigen,
)

# Identificador de lote cuando el documento no declara ninguno por su nombre
# (CLAUDE.md, encargo de esta sesión, punto 1: "un único lote implícito,
# para que el modelo de datos sea uniforme"). "1" para coincidir con la
# convención ya usada en los tests de la cascada
# (tests/extraccion/test_pipeline_anejo.py).
LOTE_UNICO = "1"

# Documentos de estas plantillas declaran la baja en texto (CLAUDE.md sección
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

# Igual que `app.extraccion.baja._PRIORIDAD_BAJA` (CLAUDE.md sección 17:
# preferir la Resolución sobre la Propuesta cuando existan las dos, por ser
# el acto posterior y definitivo). `propuesta_dt` es al mismo tipo de hecho
# que `propuesta_lc27` (docs/analisis-corpus.md hallazgo 4), misma
# prioridad. El contrato no declara lotes por nombre en el corpus visto
# hasta ahora, así que no entra en esta prioridad.
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
    # CLAUDE.md sección 3: el único documento escaneado confirmado del
    # corpus. Se marca aquí, en la clasificación, para que el motivo de
    # revisión lo distinga de "no se extrajo ninguna línea" (ver
    # `es_documento_escaneado`) en vez de intentar procesarlo como si tuviera
    # texto.
    escaneado: bool = False
    # CLAUDE.md sección 26 (criterio del cliente sobre pliegos, verificado
    # contra el corpus real): un pliego administrativo o PCAP nunca trae
    # cuadro de precios -- se salta la localización/extracción de tabla
    # entera, nunca un `pliego de prescripciones tecnicas` (ver
    # `app.extraccion.clasificador.es_pliego_sin_precios`).
    pliego_sin_precios: bool = False


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
    """CLAUDE.md sección 9.10: cada cifra derivada queda anclada a
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


def _eliminar_lote_sentinela_obsoleto(db: Session, expediente_id: int) -> None:
    """Idempotencia (CLAUDE.md sección 9.9) al migrar al arreglo de
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
    lo actualiza `_obtener_o_crear_lote` como siempre."""
    lotes_existentes = db.execute(select(Lote).where(Lote.expediente_id == expediente_id)).scalars().all()
    if len(lotes_existentes) != 1 or lotes_existentes[0].identificador_lote != LOTE_UNICO:
        return
    lote_sentinela = lotes_existentes[0]
    db.execute(delete(LineaCatalogo).where(LineaCatalogo.lote_id == lote_sentinela.id))
    db.delete(lote_sentinela)
    db.commit()


def _clasificar_documentos(db: Session, storage: DocumentStorage, documentos: list[Documento]) -> list[_Documento]:
    resultado = []
    for doc in documentos:
        contenido = storage.recuperar(doc.ruta_almacenamiento)
        paginas = extraer_texto(io.BytesIO(contenido))
        escaneado = es_documento_escaneado(paginas)
        # Un documento escaneado no tiene marcadores de texto que buscar —
        # clasificarlo igual lo mandaría a `otro` de forma indistinguible de
        # un documento legible con una plantilla desconocida (CLAUDE.md
        # sección 3, docstring de `es_documento_escaneado`).
        clasificacion = clasificar(paginas) if not escaneado else None
        # El clasificador manda, nunca el nombre de fichero ni la categoría
        # que le asignó el scraper (CLAUDE.md sección 3 y docstring de
        # app.extraccion.clasificador).
        tipo = clasificacion.tipo if clasificacion is not None else TipoDocumento.otro
        sin_precios = clasificacion is not None and es_pliego_sin_precios(clasificacion)
        doc.tipo_documento = tipo
        doc.paginas = len(paginas)
        resultado.append(
            _Documento(documento=doc, tipo=tipo, paginas=paginas, escaneado=escaneado, pliego_sin_precios=sin_precios)
        )
    db.commit()
    return resultado


@dataclass(frozen=True)
class _LotesExtraidos:
    lotes: list[LoteDeclarado]
    documento_id: Optional[int]
    lotes_totales_declarados: Optional[int]
    codigo_principal_declarado: Optional[CampoAnclado]


def _extraer_lotes_declarados_del_expediente(documentos: list[_Documento]) -> _LotesExtraidos:
    """Primer documento (por prioridad de plantilla, no por orden de lista)
    que declare al menos un lote por su nombre gana — mismo criterio que
    `app.extraccion.baja.elegir_baja_preferida` aplicado a listas de lotes
    en vez de a una baja suelta."""
    candidatos: list[tuple[int, ResultadoLotes, int]] = []
    for item in documentos:
        prioridad = _PRIORIDAD_LOTES.get(item.tipo)
        if prioridad is None:
            continue
        resultado = extraer_lotes_declarados(item.paginas)
        if resultado.lotes:
            candidatos.append((prioridad, resultado, item.documento.id))
    if not candidatos:
        return _LotesExtraidos(
            lotes=[], documento_id=None, lotes_totales_declarados=None, codigo_principal_declarado=None
        )
    candidatos.sort(key=lambda c: c[0])
    _, resultado, documento_id = candidatos[0]
    return _LotesExtraidos(
        lotes=resultado.lotes,
        documento_id=documento_id,
        lotes_totales_declarados=resultado.lotes_totales_declarados,
        codigo_principal_declarado=resultado.codigo_principal_declarado,
    )


_TIPOS_CONTRATO_OBRA = ("obras", "obra")


def _detectar_contrato_obra(documentos: list[_Documento]) -> Optional[CampoAnclado]:
    """CLAUDE.md sección 26, criterio del cliente: el campo "Tipo de
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


def _detectar_numero_lotes_pcsp(documentos: list[_Documento]) -> Optional[int]:
    """Sesión de identidad de lote (CLAUDE.md sección 27): el campo
    estructurado "Nº de Lotes:" del Anuncio PCSP es la única fuente de
    "cuántos lotes declara la licitación" para un expediente que no trae
    ninguna Propuesta LC.27 ni Resolución con bloque narrativo por lote —
    caso real verificado: `6.23/28510.0139` ("2 lotes" en el título, "Nº de
    Lotes: 2" aquí, cero documentos que declaren baja/importe por lote)."""
    for item in documentos:
        if item.tipo != TipoDocumento.anuncio_pcsp:
            continue
        campo = extraer_campos_anuncio_pcsp(item.paginas).numero_lotes
        if campo is not None:
            return int(campo.valor)
    return None


def _extraer_campos_expediente(
    db: Session, expediente: Expediente, documentos: list[_Documento], registrar_baja_importe: bool = True,
) -> tuple[Optional[Decimal], Optional[Decimal], Optional[BajaDeclarada]]:
    """Etapa 2: nombre del proyecto y matriz (siempre) e importes de
    licitación/adjudicación y baja declarada a nivel de expediente (solo
    cuando `registrar_baja_importe`). Prioridad de importes: Anuncio PCSP
    sobre Propuesta LC.27 (CLAUDE.md sección 4, tabla "Dónde está cada
    dato") — LC.27 es la reserva para expedientes sin Anuncio PCSP en el
    corpus (docstring de app.extraccion.campos_lc27).

    `registrar_baja_importe=False` es el camino multi-lote (llamador
    `ejecutar_extraccion_expediente`): ahí la baja y los importes del
    expediente salen de sus lotes (`_resumir_lotes_en_expediente`), no de
    "la primera baja que aparece en el texto" — devolver y trazar esa baja
    suelta aquí sería confuso (una cifra sin lote junto a las trazas por
    lote que sí importan) y ya no la usa nadie."""
    # (valor Decimal, documento_id, pagina, fragmento) por fuente; None si esa
    # fuente no trajo el campo. pcsp gana sobre lc27 al elegir al final.
    licitacion_pcsp = adjudicacion_pcsp = None
    licitacion_lc27 = adjudicacion_lc27 = None
    objeto_pcsp = objeto_lc27 = None
    candidatos_baja: list[BajaDeclarada] = []
    baja_doc: dict[int, int] = {}  # id(BajaDeclarada) -> documento.id

    for item in documentos:
        if item.tipo == TipoDocumento.anuncio_pcsp:
            campos = extraer_campos_anuncio_pcsp(item.paginas)
            if campos.importe_licitacion and licitacion_pcsp is None:
                licitacion_pcsp = (
                    importe_como_decimal(campos.importe_licitacion), item.documento.id,
                    campos.importe_licitacion.pagina, campos.importe_licitacion.fragmento,
                )
            if campos.importe_adjudicacion and adjudicacion_pcsp is None:
                adjudicacion_pcsp = (
                    importe_como_decimal(campos.importe_adjudicacion), item.documento.id,
                    campos.importe_adjudicacion.pagina, campos.importe_adjudicacion.fragmento,
                )
            if campos.codigo_matriz and not expediente.codigo_matriz:
                expediente.codigo_matriz = campos.codigo_matriz.valor
                _traza(
                    db, expediente.id, "codigo_matriz", item.documento.id,
                    campos.codigo_matriz.pagina, campos.codigo_matriz.fragmento, campos.codigo_matriz.valor,
                )
            if campos.objeto_contrato and objeto_pcsp is None:
                objeto_pcsp = (
                    campos.objeto_contrato.valor, item.documento.id,
                    campos.objeto_contrato.pagina, campos.objeto_contrato.fragmento,
                )
        elif item.tipo in (TipoDocumento.propuesta_lc27, TipoDocumento.resolucion_adjudicacion):
            # Misma familia de etiquetas fijas en ambas plantillas (CLAUDE.md
            # sección 17: Propuesta y Resolución declaran los mismos importes
            # del mismo procedimiento) — se tratan igual aquí, "primera que
            # aparece gana" ya cubre la preferencia por la Resolución cuando
            # las dos existen, porque `documentos` no tiene orden fijo pero
            # el importe es idéntico en cualquiera de las dos.
            lic = extraer_importe_licitacion_lc27(item.paginas)
            adj = extraer_importe_adjudicacion_lc27(item.paginas)
            obj = extraer_objeto_contrato_lc27(item.paginas)
            if lic and licitacion_lc27 is None:
                licitacion_lc27 = (parsear_importe_es(lic.valor), item.documento.id, lic.pagina, lic.fragmento)
            if adj and adjudicacion_lc27 is None:
                adjudicacion_lc27 = (parsear_importe_es(adj.valor), item.documento.id, adj.pagina, adj.fragmento)
            if obj and objeto_lc27 is None:
                objeto_lc27 = (obj.valor, item.documento.id, obj.pagina, obj.fragmento)

        if registrar_baja_importe and item.tipo in _TIPOS_CON_BAJA_DECLARADA:
            baja = extraer_baja_declarada(item.paginas, tipo_documento=item.tipo)
            if baja is not None:
                candidatos_baja.append(baja)
                baja_doc[id(baja)] = item.documento.id

    fuente_objeto = objeto_pcsp or objeto_lc27
    if fuente_objeto and not expediente.nombre_proyecto:
        expediente.nombre_proyecto = fuente_objeto[0]
        _traza(db, expediente.id, "nombre_proyecto", *fuente_objeto[1:], fuente_objeto[0])

    if not registrar_baja_importe:
        return None, None, None

    fuente_licitacion = licitacion_pcsp or licitacion_lc27
    fuente_adjudicacion = adjudicacion_pcsp or adjudicacion_lc27
    if fuente_licitacion:
        _traza(db, expediente.id, "importe_licitacion", *fuente_licitacion[1:], fuente_licitacion[0])
    if fuente_adjudicacion:
        _traza(db, expediente.id, "importe_adjudicacion", *fuente_adjudicacion[1:], fuente_adjudicacion[0])

    baja_preferida = elegir_baja_preferida(candidatos_baja)
    if baja_preferida is not None:
        _traza(
            db, expediente.id, "baja_declarada", baja_doc.get(id(baja_preferida)),
            baja_preferida.pagina, baja_preferida.fragmento, baja_preferida.baja,
        )

    importe_licitacion = fuente_licitacion[0] if fuente_licitacion else None
    importe_adjudicacion = fuente_adjudicacion[0] if fuente_adjudicacion else None
    return importe_licitacion, importe_adjudicacion, baja_preferida


def _procesar_lotes_declarados(
    db: Session, expediente: Expediente, lotes_declarados: list[LoteDeclarado], documento_id: Optional[int],
) -> tuple[list[Lote], Optional[str]]:
    """Un lote por cada `LoteDeclarado`: la baja se extrae del texto, nunca
    se calcula (CLAUDE.md sección 4), pero se contrasta contra los importes
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
            db, lote.id, "baja_declarada", documento_id, declarado.pagina, declarado.fragmento,
            declarado.baja, entidad_tipo="lote",
        )
    return lotes, motivo_revision


def _resumir_lotes_en_expediente(expediente: Expediente, lotes: list[Lote]) -> None:
    """CLAUDE.md, encargo de esta sesión, punto 4: "un expediente con lotes
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
        # CLAUDE.md sección 22: un expediente ya confirmado sin publicar no
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
        documentos = db.execute(
            select(Documento).where(Documento.expediente_id == expediente.id)
        ).scalars().all()

        motivo_revision: Optional[str] = None
        estado_especial: Optional[EstadoExpediente] = None
        lineas_creadas = lineas_actualizadas = tablas_procesadas = llamadas_modelo = 0
        documentos_procesados = 0
        documentos_pliego_omitidos: list[str] = []
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
            # (CLAUDE.md sección 7) no depende de los documentos, solo del
            # propio `codigo_expediente`: es el único camino que le queda a
            # un pedido derivado de acuerdo marco sin ningún documento
            # descargado (docs/analisis-corpus.md hallazgo 3, 7 de los 14
            # casos) para encontrar su matriz por la columna MATRIZ del
            # Excel (encargo de la sesión de herencia, requisito 1). Sin
            # este cruce aquí, estos 7 nunca podrían heredar nada aunque su
            # matriz sí esté disponible.
            motivo_revision = _acumular_motivo(motivo_revision, asegurar_cruce_codigos(db, expediente))
            db.commit()
            lotes = [_obtener_o_crear_lote(db, expediente.id, LOTE_UNICO)]
        else:
            items = _clasificar_documentos(db, storage, list(documentos))
            documentos_procesados = len(items)

            # CLAUDE.md sección 26, criterio del cliente: solo bajas de
            # material por lotes, un contrato de obra queda fuera de alcance.
            # Se detecta pronto (mismo campo de etiqueta fija que ya lee
            # `_extraer_campos_expediente`, sección 2 de la cascada) para no
            # confundir "es una obra" con "falló la extracción" -- se
            # sobrescribe el motivo al final, después de que el resto de esta
            # rama termine, para que gane sobre cualquier motivo que el
            # intento de leer un cuadro de precios que no existe hubiera
            # dejado por el camino.
            campo_obra = _detectar_contrato_obra(items)

            # Identidad del expediente (CLAUDE.md sección 20): antes de anclar
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

            # Nº de lotes declarado por el Anuncio PCSP (campo estructurado,
            # sección 27): única fuente para un expediente sin ninguna
            # Propuesta/Resolución con bloque narrativo por lote
            # (`6.23/28510.0139`) -- se detecta pronto para estar disponible
            # en las dos ramas de abajo.
            lotes_totales_pcsp = _detectar_numero_lotes_pcsp(items)

            resultado_lotes = _extraer_lotes_declarados_del_expediente(items)
            lotes_declarados = resultado_lotes.lotes
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
                # relación con acuerdo marco (CLAUDE.md sección 27):
                # escribirla ahí reintroduciría el bug de autorreferencia
                # de las secciones 20/21.
                principal = resultado_lotes.codigo_principal_declarado
                if principal is not None and normalizar_codigo_expediente(
                    principal.valor
                ) != normalizar_codigo_expediente(expediente.codigo_expediente):
                    motivo_revision = _acumular_motivo(
                        motivo_revision,
                        f"el documento declara 'EXPEDIENTE PRINCIPAL/ORIGEN' {principal.valor}, distinto del "
                        f"expediente bajo el que están archivados sus documentos ({expediente.codigo_expediente})",
                    )

                _eliminar_lote_sentinela_obsoleto(db, expediente.id)
                lotes, motivo_lotes = _procesar_lotes_declarados(
                    db, expediente, lotes_declarados, resultado_lotes.documento_id
                )
                motivo_revision = _acumular_motivo(motivo_revision, motivo_lotes)
                _resumir_lotes_en_expediente(expediente, lotes)
                expediente.lotes_totales_declarados = (
                    resultado_lotes.lotes_totales_declarados or lotes_totales_pcsp
                )

                # Cobertura parcial (sesión de identidad de lote, CLAUDE.md
                # sección 27, encargo explícito del cliente): "un expediente
                # del que solo conocemos 2 de 13 lotes no puede figurar como
                # completado". Se compara contra los lotes que SÍ traen dato
                # real (baja o importe), no solo contra `len(lotes)` -- un
                # lote mencionado por nombre en la cabecera pero sin ningún
                # bloque de adjudicación (ninguno de los 15 reales, pero
                # `_procesar_lotes_declarados` lo modela igual, sección 27)
                # no cuenta como "conocido" para este cálculo.
                if expediente.lotes_totales_declarados is not None:
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
                # Camino de siempre: un único lote implícito (CLAUDE.md,
                # encargo de esta sesión, punto 1). La falta de importe/baja
                # ya no se explica en línea aquí: si el expediente declara
                # una matriz, la herencia de más abajo puede resolverla
                # todavía — el motivo genérico de "no se pudo determinar la
                # baja" solo se compone al final, después de intentarlo.
                importe_licitacion, importe_adjudicacion, baja_preferida = _extraer_campos_expediente(db, expediente, items)

                baja_efectiva: Optional[Decimal] = None
                if importe_licitacion is not None and importe_adjudicacion is not None:
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

                lote = _obtener_o_crear_lote(db, expediente.id, LOTE_UNICO)
                lote.baja_lote = baja_efectiva
                lote.importe_licitacion = importe_licitacion
                lote.importe_adjudicacion = importe_adjudicacion
                db.commit()
                lotes = [lote]

                expediente.lotes_totales_declarados = lotes_totales_pcsp
                if lotes_totales_pcsp is not None and lotes_totales_pcsp > 1:
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
                    # mismo riesgo que ya diagnosticó CLAUDE.md sección 26
                    # para 6.24/28510.0088, aquí sin ni siquiera un
                    # documento que lo desglose.
                    motivo_revision = _acumular_motivo(
                        motivo_revision,
                        f"cobertura parcial: 0 de {lotes_totales_pcsp} lotes identificados por número "
                        "(el expediente no trae ninguna Propuesta LC.27 ni Resolución de Adjudicación "
                        "que declare la adjudicación lote a lote)",
                    )

            motivo_revision = _acumular_motivo(motivo_revision, asegurar_cruce_codigos(db, expediente))
            db.commit()

            lotes_por_identificador = {l.identificador_lote: l.id for l in lotes}
            bajas_por_identificador = {l.identificador_lote: l.baja_lote for l in lotes}

            # Etapas 3-6: el cuadro de precios se busca por contenido en TODOS
            # los documentos, nunca solo en los clasificados como "anejo"
            # (CLAUDE.md sección 3: los *_ANEJO_N.pdf son a veces el Pliego
            # completo, y localizar_paginas_candidatas ya descarta barato lo que
            # no trae tabla). Cada documento se procesa de forma aislada: una
            # tabla que no se puede mapear (cabecera nunca vista y sin modelo
            # configurado) manda ESE documento a revisión, no tira las líneas ya
            # extraídas de los demás — CLAUDE.md sección 12, "lo que no cuadra
            # va a la cola de revisión", no revienta el expediente entero.
            documentos_con_error: list[str] = []
            documentos_escaneados: list[str] = []
            for item in items:
                if item.pliego_sin_precios:
                    # CLAUDE.md sección 26: pliego administrativo o PCAP,
                    # verificado sin cuadro de precios en todo el corpus real
                    # -- ni localizar páginas candidatas ni extraer tabla
                    # gastan tiempo en él. No es un error ni algo que mandar a
                    # revisión, así que no toca `motivo_revision`.
                    documentos_pliego_omitidos.append(item.documento.nombre_archivo)
                    continue
                if item.escaneado:
                    # Sin capa de texto no hay páginas candidatas que buscar
                    # ni cabecera que mapear (CLAUDE.md sección 3): intentar
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
                # al final (CLAUDE.md, sesión de rodaje 2026-09-03, punto 2): un
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
                        io.BytesIO(contenido), item.documento.id, expediente.id,
                        bajas_por_identificador, db, model_provider,
                    )
                    if resultado.lineas:
                        grupos: dict[Optional[str], list[dict]] = {}
                        for linea in resultado.lineas:
                            identificador = linea.pop("identificador_lote")
                            grupos.setdefault(identificador, []).append(linea)
                        for identificador, lineas_grupo in grupos.items():
                            lote_id = lotes_por_identificador.get(identificador) if identificador is not None else None
                            guardado = guardar_lineas_catalogo(db, lote_id, lineas_grupo)
                            lineas_creadas_doc += guardado.creadas
                            lineas_actualizadas_doc += guardado.actualizadas
                    item.documento.procesado_en = datetime.now(timezone.utc)
                    db.commit()
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
                # Motivo aparte y explícito (CLAUDE.md sección 3): distinto
                # de "no se pudo extraer el cuadro de precios" (ese documento
                # sí tiene texto, solo falló su tabla) y de "no se extrajo
                # ninguna línea de catálogo" (ese expediente sí tiene
                # documentos legibles, solo no traían cuadro de precios).
                # Este dice que el documento no se puede leer en absoluto con
                # las herramientas actuales.
                motivo_escaneados = (
                    "documento(s) escaneado(s), sin capa de texto (fuera de alcance sin OCR o modelo "
                    "multimodal, CLAUDE.md sección 15): " + "; ".join(documentos_escaneados)
                )
                motivo_revision = _acumular_motivo(motivo_revision, motivo_escaneados)

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
            motivo_revision = (
                "extracción encolada sin documentos descargados para este expediente"
                if sin_documentos
                else "no se extrajo ninguna línea de catálogo de los documentos descargados"
            )
        if motivo_revision is None and not any(l.baja_lote is not None for l in lotes):
            motivo_revision = motivo_baja_diferido or "no se pudo determinar la baja de ningún lote"

        if campo_obra is not None:
            # Gana sobre cualquier motivo que el intento de leer un cuadro de
            # precios que no existe (porque el expediente es de obra, no de
            # material) hubiera dejado por el camino -- CLAUDE.md sección 26.
            estado_especial = EstadoExpediente.fuera_de_alcance
            motivo_revision = (
                f'contrato de obra ("Tipo de Contrato: {campo_obra.valor}"), fuera de alcance del motor de '
                "materiales (criterio del cliente, CLAUDE.md sección 26)"
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
            "llamadas_modelo": llamadas_modelo,
            "lotes": [l.identificador_lote for l in lotes],
            "baja_global": str(expediente.baja_global) if expediente.baja_global is not None else None,
            "estado": expediente.estado.value,
            "motivo_revision": motivo_revision,
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
