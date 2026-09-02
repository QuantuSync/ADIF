"""Trabajo de cola "extraer_expediente": encadena las seis etapas de la
cascada de extracción (CLAUDE.md sección 5) sobre todos los documentos ya
descargados de un expediente, y deja líneas de catálogo escritas en base de
datos. Es el punto de entrada que usa el worker (app/worker.py), simétrico a
`app.scraping.job.ejecutar_scraping_expediente` para el trabajo de descarga.

Etapa 1 (clasificar) y etapa 2 (campos de etiqueta fija) se ejecutan aquí por
primera vez sobre datos reales de expediente — hasta ahora solo existían
como funciones probadas contra fixtures sueltos. Etapas 3-6 reutilizan
`app.extraccion.pipeline_anejo.procesar_anejo` tal cual.

Sin lógica de subdivisión en varios lotes todavía (CLAUDE.md sección 16,
pendiente de verificar): todo expediente se procesa hoy como un único lote
`LOTE_UNICO`. El día que se verifique que hace falta partir por lote, este
es el sitio a tocar — el resto de la cascada (mapeo de cabecera, guardado de
catálogo) ya trabaja por `lote_id`, no por expediente.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalogo import guardar_lineas_catalogo
from app.extraccion.baja import BajaDeclarada, elegir_baja_preferida, extraer_baja_declarada
from app.extraccion.campos_lc27 import (
    extraer_importe_adjudicacion_lc27,
    extraer_importe_licitacion_lc27,
)
from app.extraccion.campos_pcsp import extraer_campos_anuncio_pcsp, importe_como_decimal
from app.extraccion.clasificador import clasificar
from app.extraccion.normalizacion import parsear_importe_es
from app.extraccion.pipeline_anejo import procesar_anejo
from app.extraccion.precios_unitarios import calcular_baja_efectiva
from app.extraccion.texto import extraer_texto
from app.interfaces.document_storage import DocumentStorage
from app.interfaces.model_provider import ModelProvider
from app.models import Documento, EstadoExpediente, Expediente, Lote, TipoDocumento, TrabajoCola, TrazaOrigen

# Identificador de lote mientras no exista subdivisión real (ver docstring
# del módulo). "1" para coincidir con la convención ya usada en los tests de
# la cascada (tests/extraccion/test_pipeline_anejo.py).
LOTE_UNICO = "1"

# Documentos de estas plantillas declaran la baja en texto (CLAUDE.md sección
# 4 y docstring de app.extraccion.baja).
_TIPOS_CON_BAJA_DECLARADA = (
    TipoDocumento.propuesta_lc27,
    TipoDocumento.resolucion_adjudicacion,
    TipoDocumento.contrato,
)


@dataclass
class _Documento:
    documento: Documento
    tipo: TipoDocumento
    paginas: list


def _traza(
    db: Session,
    expediente_id: int,
    campo: str,
    documento_id: Optional[int],
    pagina: Optional[int],
    fragmento: Optional[str],
    valor,
) -> None:
    """CLAUDE.md sección 9.10: cada cifra derivada a nivel de expediente
    queda anclada a documento, página y fragmento, no solo al número final."""
    if valor is None or documento_id is None:
        return
    db.add(
        TrazaOrigen(
            entidad_tipo="expediente",
            entidad_id=expediente_id,
            campo=campo,
            documento_id=documento_id,
            pagina=pagina,
            fragmento=fragmento,
            valor_extraido=str(valor),
        )
    )


def _obtener_o_crear_lote(db: Session, expediente_id: int) -> Lote:
    lote = db.execute(
        select(Lote).where(Lote.expediente_id == expediente_id, Lote.identificador_lote == LOTE_UNICO)
    ).scalar_one_or_none()
    if lote is None:
        lote = Lote(expediente_id=expediente_id, identificador_lote=LOTE_UNICO)
        db.add(lote)
        db.commit()
        db.refresh(lote)
    return lote


def _clasificar_documentos(db: Session, storage: DocumentStorage, documentos: list[Documento]) -> list[_Documento]:
    resultado = []
    for doc in documentos:
        contenido = storage.recuperar(doc.ruta_almacenamiento)
        paginas = extraer_texto(io.BytesIO(contenido))
        clasificacion = clasificar(paginas)
        # El clasificador manda, nunca el nombre de fichero ni la categoría
        # que le asignó el scraper (CLAUDE.md sección 3 y docstring de
        # app.extraccion.clasificador).
        doc.tipo_documento = clasificacion.tipo
        doc.paginas = len(paginas)
        resultado.append(_Documento(documento=doc, tipo=clasificacion.tipo, paginas=paginas))
    db.commit()
    return resultado


def _extraer_campos_expediente(db: Session, expediente: Expediente, documentos: list[_Documento]) -> tuple[
    Optional[Decimal], Optional[Decimal], Optional[BajaDeclarada]
]:
    """Etapa 2: campos de etiqueta fija. Prioridad de importes: Anuncio PCSP
    sobre Propuesta LC.27 (CLAUDE.md sección 4, tabla "Dónde está cada
    dato") — LC.27 es la reserva para expedientes sin Anuncio PCSP en el
    corpus (docstring de app.extraccion.campos_lc27)."""
    # (valor Decimal, documento_id, pagina, fragmento) por fuente; None si esa
    # fuente no trajo el campo. pcsp gana sobre lc27 al elegir al final.
    licitacion_pcsp = adjudicacion_pcsp = None
    licitacion_lc27 = adjudicacion_lc27 = None
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
        elif item.tipo == TipoDocumento.propuesta_lc27:
            lic = extraer_importe_licitacion_lc27(item.paginas)
            adj = extraer_importe_adjudicacion_lc27(item.paginas)
            if lic and licitacion_lc27 is None:
                licitacion_lc27 = (parsear_importe_es(lic.valor), item.documento.id, lic.pagina, lic.fragmento)
            if adj and adjudicacion_lc27 is None:
                adjudicacion_lc27 = (parsear_importe_es(adj.valor), item.documento.id, adj.pagina, adj.fragmento)

        if item.tipo in _TIPOS_CON_BAJA_DECLARADA:
            baja = extraer_baja_declarada(item.paginas, tipo_documento=item.tipo)
            if baja is not None:
                candidatos_baja.append(baja)
                baja_doc[id(baja)] = item.documento.id

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

    expediente.estado = EstadoExpediente.extrayendo
    expediente.error = None
    db.commit()

    try:
        documentos = db.execute(
            select(Documento).where(Documento.expediente_id == expediente.id)
        ).scalars().all()
        if not documentos:
            motivo = "extracción encolada sin documentos descargados para este expediente"
            expediente.estado = EstadoExpediente.pendiente_revision
            expediente.error = motivo
            db.commit()
            return {"expediente": expediente.codigo_expediente, "documentos": 0, "motivo_revision": motivo}

        items = _clasificar_documentos(db, storage, list(documentos))

        importe_licitacion, importe_adjudicacion, baja_preferida = _extraer_campos_expediente(db, expediente, items)

        motivo_revision: Optional[str] = None
        baja_efectiva: Optional[Decimal] = None
        if importe_licitacion is not None and importe_adjudicacion is not None:
            resultado_baja = calcular_baja_efectiva(
                importe_licitacion, importe_adjudicacion,
                baja_preferida.baja if baja_preferida is not None else None,
            )
            baja_efectiva = resultado_baja.baja
            if resultado_baja.requiere_revision:
                motivo_revision = resultado_baja.motivo
        elif baja_preferida is not None:
            baja_efectiva = baja_preferida.baja
        else:
            motivo_revision = (
                "no se encontró importe de licitación/adjudicación ni baja declarada "
                "en ningún documento de este expediente"
            )

        expediente.importe_licitacion = importe_licitacion
        expediente.importe_adjudicacion = importe_adjudicacion
        expediente.baja_global = baja_efectiva
        db.commit()

        lote = _obtener_o_crear_lote(db, expediente.id)
        lote.baja_lote = baja_efectiva
        lote.importe_licitacion = importe_licitacion
        lote.importe_adjudicacion = importe_adjudicacion
        db.commit()

        # Etapas 3-6: el cuadro de precios se busca por contenido en TODOS
        # los documentos, nunca solo en los clasificados como "anejo"
        # (CLAUDE.md sección 3: los *_ANEJO_N.pdf son a veces el Pliego
        # completo, y localizar_paginas_candidatas ya descarta barato lo que
        # no trae tabla). Cada documento se procesa de forma aislada: una
        # tabla que no se puede mapear (cabecera nunca vista y sin modelo
        # configurado) manda ESE documento a revisión, no tira las líneas ya
        # extraídas de los demás — CLAUDE.md sección 12, "lo que no cuadra
        # va a la cola de revisión", no revienta el expediente entero.
        lineas_creadas = lineas_actualizadas = tablas_procesadas = llamadas_modelo = 0
        documentos_con_error: list[str] = []
        for item in items:
            contenido = storage.recuperar(item.documento.ruta_almacenamiento)
            try:
                resultado = procesar_anejo(
                    io.BytesIO(contenido), item.documento.id, baja_efectiva, db, model_provider
                )
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                documentos_con_error.append(f"{item.documento.nombre_archivo}: {exc}")
                continue
            tablas_procesadas += resultado.tablas_procesadas
            llamadas_modelo += resultado.llamadas_modelo
            if resultado.lineas:
                guardado = guardar_lineas_catalogo(db, lote.id, resultado.lineas)
                lineas_creadas += guardado.creadas
                lineas_actualizadas += guardado.actualizadas
            item.documento.procesado_en = datetime.now(timezone.utc)
        db.commit()

        total_lineas = lineas_creadas + lineas_actualizadas
        if documentos_con_error:
            motivo_documentos = "no se pudo extraer el cuadro de precios de: " + "; ".join(documentos_con_error)
            motivo_revision = f"{motivo_revision}; {motivo_documentos}" if motivo_revision else motivo_documentos
        if motivo_revision is None and total_lineas == 0:
            motivo_revision = "no se extrajo ninguna línea de catálogo de los documentos descargados"
        if motivo_revision is None and baja_efectiva is None:
            motivo_revision = "no se pudo determinar la baja del lote"

        if motivo_revision is not None:
            expediente.estado = EstadoExpediente.pendiente_revision
            expediente.error = motivo_revision
        else:
            expediente.estado = EstadoExpediente.completado
            expediente.error = None
        db.commit()

        return {
            "expediente": expediente.codigo_expediente,
            "documentos_procesados": len(items),
            "tablas_procesadas": tablas_procesadas,
            "lineas_creadas": lineas_creadas,
            "lineas_actualizadas": lineas_actualizadas,
            "llamadas_modelo": llamadas_modelo,
            "baja_global": str(baja_efectiva) if baja_efectiva is not None else None,
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
        raise
