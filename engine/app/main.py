from fastapi import FastAPI

from app.routers import expedientes, health, trabajos

app = FastAPI(title="ADIF - Catalogo de materiales")

app.include_router(health.router)
app.include_router(expedientes.router)
app.include_router(trabajos.router)
