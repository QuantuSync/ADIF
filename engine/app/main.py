from fastapi import FastAPI

from app.routers import catalogo, documentos, expedientes, health, revision, trabajos

app = FastAPI(title="ADIF - Catalogo de materiales")

app.include_router(health.router)
app.include_router(expedientes.router)
app.include_router(trabajos.router)
app.include_router(catalogo.router)
app.include_router(revision.router)
app.include_router(documentos.router)
