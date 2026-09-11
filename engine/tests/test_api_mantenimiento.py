"""Bloque 6, sesión de comparación documento-vs-listado interno: el botón
manual de ingesta local, igual que el resto de trabajos de mantenimiento
(mismo patrón que test_api_catalogo.py: TestClient sobre SQLite en memoria,
sin Postgres levantado)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.main import app
from app.models import TrabajoCola

_TABLAS = [
    models.Expediente.__table__,
    models.Lote.__table__,
    models.Documento.__table__,
    models.DocumentoExpediente.__table__,
    models.LineaCatalogo.__table__,
    models.TrazaOrigen.__table__,
    models.TrabajoCola.__table__,
]


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=_TABLAS)
    sesion = sessionmaker(bind=engine)()
    try:
        yield sesion
    finally:
        sesion.close()


@pytest.fixture()
def cliente(db_session):
    def _get_db_prueba():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_prueba
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_lanzar_ingesta_local_encola_trabajo(cliente, db_session):
    resp = cliente.post("/mantenimiento/ingesta-local/ejecutar")

    assert resp.status_code == 200
    datos = resp.json()
    assert datos["tipo"] == "ingesta_local"
    assert datos["estado"] == "pendiente"
    assert db_session.query(TrabajoCola).filter_by(tipo="ingesta_local").count() == 1


def test_historial_ingesta_local_lista_lo_encolado(cliente, db_session):
    cliente.post("/mantenimiento/ingesta-local/ejecutar")
    cliente.post("/mantenimiento/ingesta-local/ejecutar")

    resp = cliente.get("/mantenimiento/ingesta-local/historial")

    assert resp.status_code == 200
    datos = resp.json()
    assert len(datos) == 2
    assert all(d["tipo"] == "ingesta_local" for d in datos)


def test_historial_ingesta_local_respeta_limite(cliente, db_session):
    for _ in range(3):
        cliente.post("/mantenimiento/ingesta-local/ejecutar")

    resp = cliente.get("/mantenimiento/ingesta-local/historial", params={"limite": 1})

    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_historial_ingesta_local_no_mezcla_otros_tipos_de_trabajo(cliente, db_session):
    db_session.add(TrabajoCola(tipo="mantenimiento_ciclo"))
    db_session.commit()
    cliente.post("/mantenimiento/ingesta-local/ejecutar")

    resp = cliente.get("/mantenimiento/ingesta-local/historial")

    datos = resp.json()
    assert len(datos) == 1
    assert datos[0]["tipo"] == "ingesta_local"
