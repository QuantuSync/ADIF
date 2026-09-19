import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.extraccion.cruce_codigos import validar_ruta_codigos_proyecto
from app.extraccion.estado_sap import validar_ruta_estado_sap
from app.extraccion.estados_adif import validar_ruta_estados_adif
from app.extraccion.maestro_materiales import validar_ruta_maestro_materiales
from app.extraccion.sap_desglose import validar_ruta_sap_desglose
from app.routers import catalogo, conciliacion, documentos, expedientes, health, mantenimiento, revision, trabajos

logger = logging.getLogger("api")

# Falla de forma visible en el arranque si CODIGOS_PROYECTO_PATH está mal
# configurada, en vez de dejar que el cruce falle en silencio petición a
# petición (docstring de `validar_ruta_codigos_proyecto`).
validar_ruta_codigos_proyecto(settings.codigos_proyecto_path)
# Mismo motivo, para el estado de contrato SAP (bloque 1, sesión del Excel de
# ejecución SAP): solo la API lo lee (POST /mantenimiento/estado-sap/cargar),
# el worker no necesita esta ruta.
validar_ruta_estado_sap(settings.estado_sap_path)
# Mismo motivo, para el listado de estados de ADIF del 18/09/2026 (bloque 1,
# sesión 2026-09-18 continuación): solo la API lo lee
# (POST /mantenimiento/estados-adif/cargar).
validar_ruta_estados_adif(settings.estados_adif_path)
# Mismo motivo, para el desglose de SAP con matrículas concretas (bloque 6,
# cambios del cliente tras revisar el catálogo): solo la API lo lee
# (POST /mantenimiento/sap-desglose/cargar), el worker no necesita esta ruta.
validar_ruta_sap_desglose(settings.sap_desglose_path)
# Mismo motivo, para el maestro de materiales de SAP (bloque 4, sesión
# 2026-09-09): solo la API lo lee (POST /mantenimiento/maestro-materiales/
# cargar), el worker no necesita esta ruta.
validar_ruta_maestro_materiales(settings.maestro_materiales_path)

app = FastAPI(title="ADIF - Catalogo de materiales")

# Sin esto, cualquier fetch() del navegador (web en otro origen, sección
# 9.1) falla con "Failed to fetch" aunque la API responda 200: el navegador
# descarta la respuesta porque no trae Access-Control-Allow-Origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Sesión de diagnóstico "Failed to fetch" (2026-09-06), segundo hallazgo:
# `app.esperar_bd` solo protege el arranque -- un corte de conexión a la
# base de datos DESPUÉS de que la API ya está sirviendo (el mismo
# `dockerd`/WSL reiniciándose a mitad de sesión, `docs/diagnostico-caidas-
# dockerd.md`) deja que `sqlalchemy.exc.OperationalError` se propague sin
# capturar desde un `get_db()` normal. Starlette añade su propio
# `ServerErrorMiddleware` FUERA de los middlewares registrados con
# `add_middleware` (incluido `CORSMiddleware`) para atrapar justo esto --
# así que una excepción que llega hasta ahí sin que ningún manejador la
# capture antes genera una respuesta que **nunca pasa por `CORSMiddleware`**,
# sin cabecera `Access-Control-Allow-Origin`. El navegador no puede
# distinguir eso de un origen mal configurado: lo reporta como "blocked by
# CORS policy" -- verificado en vivo forzando el corte
# (`docker network disconnect`) con la web abierta de verdad, no solo con
# curl. Un `exception_handler` registrado en la propia `app` intercepta
# ANTES de `ServerErrorMiddleware` (dentro de `CORSMiddleware`), así que la
# respuesta sí lleva la cabecera -- y de paso le da a `useReintentoConexion`
# (bloque de estados de carga y error) el 503 real que ya sabe interpretar
# como "corte transitorio, reintentar", en vez de un error opaco de CORS.
@app.exception_handler(OperationalError)
async def error_conexion_bd(request: Request, exc: OperationalError) -> JSONResponse:
    logger.warning("corte de conexión a la base de datos sirviendo %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Base de datos no disponible temporalmente, reintenta en unos segundos."},
    )


app.include_router(health.router)
app.include_router(expedientes.router)
app.include_router(trabajos.router)
app.include_router(catalogo.router)
app.include_router(conciliacion.router)
app.include_router(revision.router)
app.include_router(documentos.router)
app.include_router(mantenimiento.router)
