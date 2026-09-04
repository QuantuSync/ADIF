import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.db import Base

_TABLAS = [
    models.Expediente.__table__,
    models.Lote.__table__,
    models.Documento.__table__,
    models.LineaCatalogo.__table__,
    models.TrazaOrigen.__table__,
    models.MapeoCabeceraCache.__table__,
    models.TrabajoCola.__table__,
    models.SindicacionExpediente.__table__,
]


@pytest.fixture()
def db_session():
    """Sesión sobre SQLite en memoria: sin Postgres levantado. Usa `JSON`
    genérico (no `JSONB`) en las tablas nuevas para que esto siga siendo
    válido; ver docstring de `app.models.MapeoCabeceraCache`."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=_TABLAS)
    sesion = sessionmaker(bind=engine)()
    try:
        yield sesion
    finally:
        sesion.close()
