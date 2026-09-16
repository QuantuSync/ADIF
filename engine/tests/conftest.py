import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.db import Base

_TABLAS = [
    models.Expediente.__table__,
    models.Lote.__table__,
    models.Documento.__table__,
    models.DocumentoExpediente.__table__,
    models.LineaCatalogo.__table__,
    models.TrazaOrigen.__table__,
    models.MapeoCabeceraCache.__table__,
    models.CacheCodigoMaterial.__table__,
    models.CacheTextoDocumento.__table__,
    models.TrabajoCola.__table__,
    models.SindicacionExpediente.__table__,
    models.CandidatoAcuerdoMarco.__table__,
    models.SapDesgloseLinea.__table__,
    models.MaestroMaterial.__table__,
    models.CandidatoMatricula.__table__,
]


@pytest.fixture(autouse=True)
def _sin_descubrimiento_por_busqueda(monkeypatch):
    """Sesión 2026-09-16: el descubrimiento por búsqueda directa
    (`app.scraping.descubrimiento_busqueda`) va dentro del ciclo de
    mantenimiento y está activo por defecto en producción -- lo que en un
    test significaría levantar Chromium y golpear la Plataforma real. A
    diferencia de la sindicación, que se desactiva por payload en cada test
    (`_trabajo_ciclo`), esto es un ajuste de configuración, así que se apaga
    una sola vez para toda la suite: ningún test toca la red por descuido.
    El que quiera ejercitarlo lo vuelve a activar y sustituye
    `buscar_codigos_de_fragmentos` por un doble (ver
    `tests/scraping/test_descubrimiento_busqueda.py`)."""
    from app import config
    monkeypatch.setattr(config.settings, "busqueda_descubrimiento_activo", False)


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
