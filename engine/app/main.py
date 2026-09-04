from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import catalogo, documentos, expedientes, health, mantenimiento, revision, trabajos

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

app.include_router(health.router)
app.include_router(expedientes.router)
app.include_router(trabajos.router)
app.include_router(catalogo.router)
app.include_router(revision.router)
app.include_router(documentos.router)
app.include_router(mantenimiento.router)
