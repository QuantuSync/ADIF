import logging
import time

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.extraccion.orquestador import ejecutar_extraccion_expediente
from app.interfaces.document_storage import LocalDiskStorage
from app.interfaces.model_provider import AnthropicModelProvider, CachedModelProvider
from app.mantenimiento.ciclo import TIPO_TRABAJO as TIPO_MANTENIMIENTO_CICLO
from app.mantenimiento.ciclo import ejecutar_ciclo_mantenimiento
from app.mantenimiento.frescura import debe_estampar_extraccion, estampar_descarga_exitosa, estampar_extraccion
from app.models import Documento, EstadoExpediente, Expediente
from app.queue import ejecutar_trabajo as ejecutar_trabajo_generico
from app.queue import reclamar_trabajos_huerfanos, tomar_siguiente_trabajo
from app.scraping.job import ejecutar_scraping_expediente
from app.sindicacion.contraste import contrastar_expediente

logging.basicConfig(level=logging.INFO, format="%(asctime)s worker %(message)s")
logger = logging.getLogger("worker")

storage = LocalDiskStorage(settings.document_storage_path)

# Etapa 5 de la cascada (CLAUDE.md sección 6): sin clave configurada, se
# procesa igual pero el mapeo de cabecera nunca vista fallará con un error
# real en vez de una llamada silenciosa a ningún sitio (NullModelProvider).
model_provider = (
    AnthropicModelProvider(
        api_key=settings.anthropic_api_key,
        modelo=settings.anthropic_model,
        workspace_id=settings.anthropic_workspace_id,
    )
    if settings.anthropic_api_key
    else None
)
# Decorador de desarrollo (interfaces/model_provider.py, docstring de
# CachedModelProvider): solo se activa si MODEL_CACHE_DIR está en el
# entorno, para no cachear en disco en producción por accidente.
if model_provider is not None and settings.model_cache_dir:
    model_provider = CachedModelProvider(model_provider, settings.model_cache_dir)


def procesar_ping(db, trabajo) -> dict:
    """Trabajo de prueba: no hace nada útil, solo demuestra que la cola funciona."""
    time.sleep(1)
    return {"ok": True, "mensaje": "pong"}


def procesar_descargar_expediente(db, trabajo) -> dict:
    """Envuelve `ejecutar_scraping_expediente` (sin tocarla, CLAUDE.md
    encargo de esta sesión: "no toques el motor de extracción" — esto
    tampoco es el motor, pero por la misma razón se deja intacto) para
    estampar `descargado_en` (bloque 1, CLAUDE.md sección 23) solo cuando la
    descarga termina con éxito. Si falla, o el expediente resulta
    `sin_publicar`, la excepción se propaga antes de llegar aquí y no se
    estampa nada — coherente con `app.mantenimiento.frescura.debe_descargar`,
    que solo mira si el expediente ya tiene documentos."""
    resultado = ejecutar_scraping_expediente(db, storage, trabajo)
    expediente = db.get(Expediente, trabajo.expediente_id)
    if expediente is not None:
        estampar_descarga_exitosa(db, expediente)
    return resultado


def procesar_extraer_expediente(db, trabajo) -> dict:
    """Envuelve `ejecutar_extraccion_expediente` (sin tocarla) para estampar
    frescura (bloque 1) en un `finally`, para que quede registrada tanto si
    el intento termina en éxito/revisión como si termina en `fallido` — un
    intento que sí corrió la cascada, aunque acabara mal, no hace falta
    repetirlo hasta que cambien los documentos o la versión de la lógica
    (ver `app.mantenimiento.frescura.debe_estampar_extraccion` para las dos
    excepciones: `esperando_matriz` y `sin_publicar`)."""
    try:
        return ejecutar_extraccion_expediente(db, storage, trabajo, model_provider=model_provider)
    finally:
        expediente = db.get(Expediente, trabajo.expediente_id) if trabajo.expediente_id else None
        if expediente is not None and debe_estampar_extraccion(expediente):
            documentos = db.execute(
                select(Documento).where(Documento.expediente_id == expediente.id)
            ).scalars().all()
            estampar_extraccion(db, expediente, documentos)
            _contrastar_con_sindicacion(db, expediente)


def _contrastar_con_sindicacion(db, expediente) -> None:
    """Bloque 2, punto 4 (CLAUDE.md sección 24): dos fuentes que se
    verifican entre sí. Solo tiene sentido sobre un resultado real de la
    cascada (`completado` o `pendiente_revision`, nunca `fallido` — ahí no
    hay un importe fiable que contrastar, y downgradearlo escondería el
    motivo real del fallo)."""
    if expediente.estado not in (EstadoExpediente.completado, EstadoExpediente.pendiente_revision):
        return
    motivo = contrastar_expediente(db, expediente)
    if motivo is None:
        return
    if expediente.estado == EstadoExpediente.completado:
        expediente.estado = EstadoExpediente.pendiente_revision
        expediente.error = motivo
    else:
        expediente.error = f"{expediente.error}; {motivo}" if expediente.error else motivo
    db.commit()


def procesar_mantenimiento_ciclo(db, trabajo) -> dict:
    return ejecutar_ciclo_mantenimiento(db, storage, model_provider, MANEJADORES, trabajo)


MANEJADORES = {
    "ping": procesar_ping,
    "descargar_expediente": procesar_descargar_expediente,
    "extraer_expediente": procesar_extraer_expediente,
    TIPO_MANTENIMIENTO_CICLO: procesar_mantenimiento_ciclo,
}


def ejecutar_trabajo(db, trabajo) -> None:
    ejecutar_trabajo_generico(db, trabajo, MANEJADORES)


def bucle_principal() -> None:
    logger.info("worker arrancado, sondeando cada %ss", settings.worker_poll_interval_seconds)
    while True:
        db = SessionLocal()
        try:
            reclamados = reclamar_trabajos_huerfanos(db, settings.worker_orphan_threshold_seconds)
            if reclamados:
                logger.warning("reclamados %s trabajos huerfanos (bloqueado_en vencido)", reclamados)
            trabajo = tomar_siguiente_trabajo(db)
            if trabajo is not None:
                logger.info("procesando trabajo %s (%s)", trabajo.id, trabajo.tipo)
                ejecutar_trabajo(db, trabajo)
        finally:
            db.close()
        time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    bucle_principal()
