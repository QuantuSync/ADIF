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
    models.PresupuestoLoteDocumento.__table__,
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


# --- Bloque 4, sesión 2026-09-18: POST /mantenimiento/ejecutar reenvía la
# bandera de búsqueda al ciclo. El consumidor (`app.mantenimiento.ciclo`) la
# leía desde que existe el descubrimiento por búsqueda, pero este endpoint
# construye el payload campo a campo y esta clave faltaba -- así que cada
# reproceso repetía la búsqueda completa en la Plataforma para nada.


def test_ejecutar_reenvia_busqueda_desactivada_al_ciclo(cliente, db_session):
    resp = cliente.post("/mantenimiento/ejecutar", json={"busqueda_desactivada": True})

    assert resp.status_code == 200
    trabajo = db_session.query(TrabajoCola).filter_by(tipo="mantenimiento_ciclo").one()
    assert trabajo.payload["busqueda_desactivada"] is True


def test_ejecutar_reenvia_los_fragmentos_de_busqueda(cliente, db_session):
    resp = cliente.post("/mantenimiento/ejecutar", json={"busqueda_fragmentos": ["6.26/28510"]})

    assert resp.status_code == 200
    trabajo = db_session.query(TrabajoCola).filter_by(tipo="mantenimiento_ciclo").one()
    assert trabajo.payload["busqueda_fragmentos"] == ["6.26/28510"]


def test_ejecutar_sin_cuerpo_deja_la_busqueda_activa(cliente, db_session):
    """El botón de la web manda `{}`: el comportamiento por defecto no cambia."""
    resp = cliente.post("/mantenimiento/ejecutar", json={})

    assert resp.status_code == 200
    trabajo = db_session.query(TrabajoCola).filter_by(tipo="mantenimiento_ciclo").one()
    assert trabajo.payload["busqueda_desactivada"] is False
    assert trabajo.payload["busqueda_fragmentos"] is None
