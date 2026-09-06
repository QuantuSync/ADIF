import logging
import time

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.db import SessionLocal
from app.extraccion.cruce_codigos import validar_ruta_codigos_proyecto
from app.extraccion.orquestador import ejecutar_extraccion_expediente
from app.interfaces.document_storage import LocalDiskStorage
from app.interfaces.model_provider import AnthropicModelProvider, CachedModelProvider
from app.mantenimiento.ciclo import TIPO_TRABAJO as TIPO_MANTENIMIENTO_CICLO
from app.mantenimiento.ciclo import ejecutar_ciclo_mantenimiento
from app.mantenimiento.frescura import (
    contar_lineas_catalogo,
    debe_estampar_extraccion,
    detectar_crecimiento_sin_cambios,
    documentos_sin_cambios,
    estampar_descarga_exitosa,
    estampar_extraccion,
)
from app.mantenimiento.programacion import verificar_y_lanzar_ciclo_programado
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
    excepciones: `esperando_matriz` y `sin_publicar`).

    También captura, antes de llamar a la cascada, si los documentos de este
    expediente son exactamente los que ya se usaron en su última extracción
    con éxito (`app.mantenimiento.frescura.documentos_sin_cambios`) y, si es
    así, cuántas líneas de catálogo tenía entonces -- para poder comparar al
    terminar y detectar sola la duplicación silenciosa que motivó esta
    comprobación (CLAUDE.md sección 9.9, auditoría 2026-09-05: ~4.500 líneas
    de sobra en siete expedientes, sin que nada lo señalara hasta la
    revisión manual)."""
    expediente_antes = db.get(Expediente, trabajo.expediente_id) if trabajo.expediente_id else None
    verificar_integridad = False
    conteo_antes = 0
    if expediente_antes is not None:
        documentos_antes = db.execute(
            select(Documento).where(Documento.expediente_id == expediente_antes.id)
        ).scalars().all()
        verificar_integridad = documentos_sin_cambios(expediente_antes, documentos_antes)
        if verificar_integridad:
            conteo_antes = contar_lineas_catalogo(db, expediente_antes.id)
    try:
        return ejecutar_extraccion_expediente(db, storage, trabajo, model_provider=model_provider)
    finally:
        expediente = db.get(Expediente, trabajo.expediente_id) if trabajo.expediente_id else None
        if expediente is not None and debe_estampar_extraccion(expediente):
            documentos = db.execute(
                select(Documento).where(Documento.expediente_id == expediente.id)
            ).scalars().all()
            if verificar_integridad:
                aviso = detectar_crecimiento_sin_cambios(conteo_antes, contar_lineas_catalogo(db, expediente.id))
                if aviso is not None:
                    logger.error("%s: %s", expediente.codigo_expediente, aviso)
                    expediente.error = f"{expediente.error}; {aviso}" if expediente.error else aviso
                    if expediente.estado == EstadoExpediente.completado:
                        expediente.estado = EstadoExpediente.pendiente_revision
                    db.commit()
            estampar_extraccion(db, expediente, documentos)
            _contrastar_con_sindicacion(db, expediente)


def _contrastar_con_sindicacion(db, expediente) -> None:
    """Bloque 2, punto 4 (CLAUDE.md sección 24), corregido en la sección 26:
    dos fuentes que se verifican entre sí, pero no con la misma autoridad. El
    PDF es el acto administrativo; la instantánea de sindicación es un
    volcado de otra fuente, que puede tener otro alcance (la licitación
    completa de un expediente con varios lotes, cuando el PDF que tenemos es
    el de un lote concreto — el caso real que hizo bajar de `completado` a
    revisión el ejemplo central de CLAUDE.md sección 4, 6.24/28510.0088, sin
    que la extracción tuviera nada mal) o estar simplemente desactualizada.
    Un desajuste ya nunca cambia `estado` ni `error` — se guarda como aviso
    informativo en `aviso_sindicacion`, para que se pueda ver sin que
    bloquee nada. Solo tiene sentido sobre un resultado real de la cascada
    (`completado` o `pendiente_revision`, nunca `fallido` — ahí no hay un
    importe fiable que contrastar)."""
    if expediente.estado not in (EstadoExpediente.completado, EstadoExpediente.pendiente_revision):
        return
    expediente.aviso_sindicacion = contrastar_expediente(db, expediente)
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


def _vuelta_bucle_principal(db) -> None:
    """Una vuelta del bucle principal, separada de `bucle_principal` para
    poder probarla sin depender de un `while True`."""
    reclamados = reclamar_trabajos_huerfanos(db, settings.worker_orphan_threshold_seconds)
    if reclamados:
        logger.warning("reclamados %s trabajos huerfanos (bloqueado_en vencido)", reclamados)
    lanzado = verificar_y_lanzar_ciclo_programado(db)
    if lanzado is not None:
        logger.info("ciclo de mantenimiento programado encolado (trabajo %s)", lanzado.id)
    trabajo = tomar_siguiente_trabajo(db)
    if trabajo is not None:
        logger.info("procesando trabajo %s (%s)", trabajo.id, trabajo.tipo)
        ejecutar_trabajo(db, trabajo)


def bucle_principal() -> None:
    logger.info("worker arrancado, sondeando cada %ss", settings.worker_poll_interval_seconds)
    while True:
        db = SessionLocal()
        try:
            _vuelta_bucle_principal(db)
        except OperationalError as exc:
            # Tolerancia a reinicios de dockerd (sesión 2026-09-06):
            # `app.esperar_bd` ya espera a que la base de datos responda
            # antes de llegar aquí, pero un reinicio real de dockerd puede
            # dejar la red del stack recreándose todavía unos segundos
            # después de esa comprobación -- una consulta de este bucle
            # (no de un trabajo concreto, que ya aísla sus propios fallos en
            # `app.queue.ejecutar_trabajo`) puede toparse con el mismo DNS
            # que no resuelve. Antes esto no se atrapaba aquí: la excepción
            # salía de `bucle_principal()`, mataba el proceso entero, y
            # `restart: unless-stopped` reiniciaba el contenedor desde cero
            # -- perdiendo el propio reintento que `esperar_bd` ya había
            # hecho. Registrar y reintentar en la siguiente vuelta (mismo
            # `sleep` de siempre) es un reintento más, no una caída.
            logger.warning("fallo de conexión a la base de datos en esta vuelta, se reintenta: %s", exc.orig or exc)
        finally:
            db.close()
        time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    # Mismo arranque visible que `app.main` (docstring de
    # `validar_ruta_codigos_proyecto`): el worker es el otro proceso que
    # lee `CODIGOS_PROYECTO_PATH` (cascada de extracción, no solo el
    # backfill perezoso de la API).
    validar_ruta_codigos_proyecto(settings.codigos_proyecto_path)
    bucle_principal()
