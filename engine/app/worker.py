import logging
import time

from app.config import settings
from app.db import SessionLocal
from app.extraccion.orquestador import ejecutar_extraccion_expediente
from app.interfaces.document_storage import LocalDiskStorage
from app.interfaces.model_provider import AnthropicModelProvider
from app.models import EstadoTrabajo
from app.queue import reclamar_trabajos_huerfanos, tomar_siguiente_trabajo
from app.scraping.job import ejecutar_scraping_expediente

logging.basicConfig(level=logging.INFO, format="%(asctime)s worker %(message)s")
logger = logging.getLogger("worker")

storage = LocalDiskStorage(settings.document_storage_path)

# Etapa 5 de la cascada (CLAUDE.md sección 6): sin clave configurada, se
# procesa igual pero el mapeo de cabecera nunca vista fallará con un error
# real en vez de una llamada silenciosa a ningún sitio (NullModelProvider).
model_provider = (
    AnthropicModelProvider(api_key=settings.anthropic_api_key, modelo=settings.anthropic_model)
    if settings.anthropic_api_key
    else None
)


def procesar_ping(db, trabajo) -> dict:
    """Trabajo de prueba: no hace nada útil, solo demuestra que la cola funciona."""
    time.sleep(1)
    return {"ok": True, "mensaje": "pong"}


def procesar_descargar_expediente(db, trabajo) -> dict:
    return ejecutar_scraping_expediente(db, storage, trabajo)


def procesar_extraer_expediente(db, trabajo) -> dict:
    return ejecutar_extraccion_expediente(db, storage, trabajo, model_provider=model_provider)


MANEJADORES = {
    "ping": procesar_ping,
    "descargar_expediente": procesar_descargar_expediente,
    "extraer_expediente": procesar_extraer_expediente,
}


def ejecutar_trabajo(db, trabajo) -> None:
    manejador = MANEJADORES.get(trabajo.tipo)
    if manejador is None:
        trabajo.estado = EstadoTrabajo.fallido
        trabajo.error = f"tipo de trabajo desconocido: {trabajo.tipo}"
        db.commit()
        return
    try:
        resultado = manejador(db, trabajo)
        trabajo.estado = EstadoTrabajo.completado
        trabajo.resultado = resultado
        trabajo.error = None
    except Exception as exc:  # noqa: BLE001
        logger.exception("fallo procesando trabajo %s", trabajo.id)
        trabajo.estado = (
            EstadoTrabajo.pendiente if trabajo.intentos < trabajo.max_intentos else EstadoTrabajo.fallido
        )
        trabajo.error = str(exc)
    db.commit()


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
