"""Trabajo de cola que envuelve `pcsp.scrape_expediente`: descarga, guarda por
la interfaz de almacenamiento y registra expediente y documentos en la base de
datos. Es el punto de entrada que usa el worker (app/worker.py) para el tipo
de trabajo "descargar_expediente"."""
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.extraccion.herencia_matriz import reencolar_pedidos_esperando_matriz
from app.interfaces.document_storage import DocumentStorage
from app.mantenimiento.frescura import VERSION_LOGICA_BUSQUEDA
from app.models import (
    Documento,
    DocumentoExpediente,
    EstadoExpediente,
    Expediente,
    OrigenDocumento,
    TipoDocumento,
    TrabajoCola,
)
from app.queue import encolar_trabajo
from app.scraping.limitador import esperar_turno
from app.scraping.pcsp import ExpedienteNoPublicadoError, safe, scrape_expediente

CATEGORIA_A_TIPO = {
    "CONTRATO": TipoDocumento.contrato,
    "PLIEGO": TipoDocumento.pliego,
    "ANEJO": TipoDocumento.anejo,
    # La adjudicación es "Anuncio PCSP" o "Propuesta LC.27" según su contenido;
    # esa clasificación es la etapa 1 de la cascada de extracción, no esta.
    "ADJUDICACION": TipoDocumento.otro,
}


def ejecutar_scraping_expediente(db: Session, storage: DocumentStorage, trabajo: TrabajoCola) -> dict:
    if trabajo.expediente_id is None:
        raise RuntimeError("trabajo de scraping sin expediente_id")
    expediente = db.get(Expediente, trabajo.expediente_id)
    if expediente is None:
        raise RuntimeError(f"expediente_id {trabajo.expediente_id} no existe")

    # Sesión de límite de tasa (2026-09-07): si este expediente YA tiene
    # documentos de una descarga anterior con éxito, ningún fallo de ESTE
    # intento (búsqueda sin resultados, timeout, bloqueo) puede degradarlo
    # -- comprobado con datos reales que la Plataforma no revoca una
    # publicación (encargo del cliente: "un expediente que ya tiene
    # documentos descargados y catálogo extraído no puede pasar nunca a no
    # publicado por un fallo de búsqueda", y el mismo principio aplica a
    # `fallido` sin matices: es un fallo transitorio, no una prueba de nada).
    # `estado_anterior` se captura ANTES de tocar nada, para poder
    # restaurarlo tal cual si este intento falla -- ni la rama
    # `ExpedienteNoPublicadoError` ni la genérica añaden ningún documento
    # nuevo antes de fallar, así que "ya tenía documentos" sigue siendo
    # válido en el momento de decidir qué hacer con el fallo.
    estado_anterior = expediente.estado
    ya_tenia_documentos = (
        db.execute(
            select(DocumentoExpediente.id).where(DocumentoExpediente.expediente_id == expediente.id).limit(1)
        ).first()
        is not None
    )

    expediente.estado = EstadoExpediente.descargando
    expediente.error = None
    db.commit()

    esperar_turno()
    try:
        resultado = asyncio.run(
            scrape_expediente(expediente.codigo_expediente, expediente.codigo_matriz)
        )
    except ExpedienteNoPublicadoError as exc:
        if ya_tenia_documentos:
            # Se restaura el estado previo tal cual (nunca `sin_publicar` ni
            # `fallido`) y se trata como un fallo transitorio normal
            # (reintentable con el backoff de `app.queue`) -- `raise` deja
            # que `ejecutar_trabajo` decida si le quedan intentos, sin
            # tocar los documentos/catálogo que ya tenía.
            expediente.estado = estado_anterior
            expediente.error = (
                f"la búsqueda no encontró el expediente en este reintento, pero ya tenía documentos "
                f"descargados de antes -- tratado como fallo transitorio, no como 'no publicado': {exc}"
            )
            db.commit()
            raise
        # Resultado negativo determinista (docstring de la excepción): no es
        # "fallido" (que sugiere que reintentar podría cambiar el resultado),
        # es "sin_publicar" (CONTEXTO.md sección 22) -- y no hay razón para
        # gastar dos intentos más de scraping real repitiendo una búsqueda
        # que ya se sabe que no encuentra nada, así que se agota el trabajo
        # aquí mismo en vez de dejar que `ejecutar_trabajo` lo reintente.
        expediente.estado = EstadoExpediente.sin_publicar
        expediente.error = str(exc)
        # Negativo confirmado con la lógica de búsqueda vigente (sesión
        # 2026-09-15): el ciclo de mantenimiento lo vuelve a buscar pasado el
        # plazo (`app.mantenimiento.frescura.sin_publicar_reintento_desde`).
        expediente.sin_publicar_en = datetime.now(timezone.utc)
        expediente.sin_publicar_version_busqueda = VERSION_LOGICA_BUSQUEDA
        trabajo.intentos = trabajo.max_intentos
        db.commit()
        if reencolar_pedidos_esperando_matriz(db, expediente):
            db.commit()
        raise
    except Exception as exc:
        # Un fallo transitorio en el reintento de un `sin_publicar` (sesión
        # 2026-09-15) no prueba nada: se queda `sin_publicar` con su fecha y
        # versión de antes, y el ciclo lo vuelve a buscar cuando toque, en
        # vez de pasar a `fallido` y perder de dónde venía.
        conserva_estado = ya_tenia_documentos or estado_anterior == EstadoExpediente.sin_publicar
        expediente.estado = estado_anterior if conserva_estado else EstadoExpediente.fallido
        expediente.error = str(exc)
        db.commit()
        # Si este expediente es la matriz de algún pedido derivado
        # (app.extraccion.herencia_matriz) que se quedó `esperando_matriz`,
        # un fallo aquí es tan terminal como uno en la extracción: si no se
        # reencola ahora, esos pedidos se quedarían esperando para siempre,
        # porque nunca llega a generarse el trabajo "extraer_expediente" de
        # esta matriz que dispararía el reencolado normal.
        if reencolar_pedidos_esperando_matriz(db, expediente):
            db.commit()
        raise

    carpeta = safe(expediente.codigo_expediente.replace("/", "_"))
    contadores = {"CONTRATO": 0, "PLIEGO": 0, "ADJUDICACION": 0, "ANEJO": 0}
    nuevos = 0
    enlaces_nuevos = 0
    for doc in resultado.documentos:
        contadores[doc.categoria] += 1
        nombre_display = f"{doc.categoria}_{contadores[doc.categoria]}.pdf"

        # Idempotencia por CONTENIDO (mismo hash): el fichero físico no se
        # vuelve a guardar ni a descargar si ya existe una fila `Documento`
        # con este hash, sea de este expediente o de cualquier otro.
        existente = db.execute(select(Documento).where(Documento.hash == doc.hash)).scalar_one_or_none()
        if existente is None:
            nuevos += 1
            ruta = storage.guardar(f"{carpeta}/{doc.categoria}_{doc.hash}.pdf", doc.contenido)
            existente = Documento(
                tipo_documento=CATEGORIA_A_TIPO[doc.categoria],
                hash=doc.hash,
                ruta_almacenamiento=ruta,
            )
            db.add(existente)
            db.flush()  # necesita existente.id para el enlace de abajo
        elif existente.origen == OrigenDocumento.manual:
            # Bloque 6, sesión de comparación documento-vs-listado interno:
            # "si mañana aparece publicado, hay que poder distinguirlos" --
            # el mismo contenido (mismo hash) que se había aportado a mano
            # ahora se confirma con una descarga real de la Plataforma. Deja
            # de ser "aportado" y pasa a ser el mismo fichero, con
            # verificación oficial.
            existente.origen = OrigenDocumento.plataforma

        # Sesión de colisión de hash entre expedientes hermanos (2026-09-08,
        # migración 0021): el documento puede ya existir (mismo contenido
        # descargado antes bajo OTRO expediente -- expedientes hermanos de
        # una licitación multi-lote que comparten el mismo PDF real,
        # verificado con `4.25/28510.0124`/`0132`), pero este expediente
        # concreto puede no tener todavía su propio enlace. Antes, este caso
        # se descartaba en silencio (`continue`) y el expediente se quedaba
        # sin ver un documento que sí existía en el sistema -- ahora se
        # enlaza siempre que falte, nunca se duplica el fichero.
        enlace_existente = db.execute(
            select(DocumentoExpediente.id).where(
                DocumentoExpediente.documento_id == existente.id,
                DocumentoExpediente.expediente_id == expediente.id,
            )
        ).first()
        if enlace_existente is None:
            enlaces_nuevos += 1
            db.add(DocumentoExpediente(
                documento_id=existente.id,
                expediente_id=expediente.id,
                nombre_archivo=nombre_display,
            ))

    expediente.estado = EstadoExpediente.descargado
    expediente.error = None
    expediente.sin_publicar_en = None
    expediente.sin_publicar_version_busqueda = None
    db.commit()

    # Encadenado (CONTEXTO.md, encargo de esta sesión, punto 3): al terminar
    # la descarga se encola la extracción, no se ejecuta suelta.
    encolar_trabajo(db, tipo="extraer_expediente", expediente_id=expediente.id)

    return {
        "expediente": expediente.codigo_expediente,
        "encontrado_como": resultado.codigo_encontrado,
        "documentos": contadores,
        "documentos_nuevos": nuevos,
        # Sesión de colisión de hash entre expedientes hermanos (2026-09-08):
        # distinto de `documentos_nuevos` -- un documento ya existente
        # (mismo hash de otro expediente) que este expediente enlaza por
        # primera vez cuenta aquí, no arriba.
        "enlaces_nuevos": enlaces_nuevos,
    }
