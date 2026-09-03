"""Trabajo de cola que envuelve `pcsp.scrape_expediente`: descarga, guarda por
la interfaz de almacenamiento y registra expediente y documentos en la base de
datos. Es el punto de entrada que usa el worker (app/worker.py) para el tipo
de trabajo "descargar_expediente"."""
import asyncio

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.extraccion.herencia_matriz import reencolar_pedidos_esperando_matriz
from app.interfaces.document_storage import DocumentStorage
from app.models import Documento, EstadoExpediente, Expediente, TipoDocumento, TrabajoCola
from app.queue import encolar_trabajo
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

    expediente.estado = EstadoExpediente.descargando
    expediente.error = None
    db.commit()

    try:
        resultado = asyncio.run(
            scrape_expediente(expediente.codigo_expediente, expediente.codigo_matriz)
        )
    except ExpedienteNoPublicadoError as exc:
        # Resultado negativo determinista (docstring de la excepción): no es
        # "fallido" (que sugiere que reintentar podría cambiar el resultado),
        # es "sin_publicar" (CLAUDE.md sección 22) -- y no hay razón para
        # gastar dos intentos más de scraping real repitiendo una búsqueda
        # que ya se sabe que no encuentra nada, así que se agota el trabajo
        # aquí mismo en vez de dejar que `ejecutar_trabajo` lo reintente.
        expediente.estado = EstadoExpediente.sin_publicar
        expediente.error = str(exc)
        trabajo.intentos = trabajo.max_intentos
        db.commit()
        if reencolar_pedidos_esperando_matriz(db, expediente):
            db.commit()
        raise
    except Exception as exc:
        expediente.estado = EstadoExpediente.fallido
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
    for doc in resultado.documentos:
        contadores[doc.categoria] += 1
        # Idempotencia: mismo contenido (mismo hash) ya registrado, aunque sea
        # de una ejecución anterior de este mismo expediente -> no se duplica.
        existente = db.execute(select(Documento).where(Documento.hash == doc.hash)).scalar_one_or_none()
        if existente is not None:
            continue
        nuevos += 1
        # La ruta de almacenamiento va con el hash, no con el índice: si una
        # regrabación trae contenido distinto en el mismo hueco (p.ej. una
        # resolución de adjudicación más reciente), no se pisa el fichero de
        # una fila de documentos que aún la referencia por su hash antiguo.
        nombre_display = f"{doc.categoria}_{contadores[doc.categoria]}.pdf"
        ruta = storage.guardar(f"{carpeta}/{doc.categoria}_{doc.hash}.pdf", doc.contenido)
        db.add(Documento(
            expediente_id=expediente.id,
            tipo_documento=CATEGORIA_A_TIPO[doc.categoria],
            hash=doc.hash,
            nombre_archivo=nombre_display,
            ruta_almacenamiento=ruta,
        ))

    expediente.estado = EstadoExpediente.descargado
    expediente.error = None
    db.commit()

    # Encadenado (CLAUDE.md, encargo de esta sesión, punto 3): al terminar
    # la descarga se encola la extracción, no se ejecuta suelta.
    encolar_trabajo(db, tipo="extraer_expediente", expediente_id=expediente.id)

    return {
        "expediente": expediente.codigo_expediente,
        "encontrado_como": resultado.codigo_encontrado,
        "documentos": contadores,
        "documentos_nuevos": nuevos,
    }
