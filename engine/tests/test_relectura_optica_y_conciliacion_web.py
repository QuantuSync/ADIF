"""Sesión 2026-09-19 (quinta parte): la relectura óptica de páginas concretas
con un modelo mejor (bloque 1) y la Conciliación servida a la web (bloque 5).
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.extraccion import ocr_relectura
from app.extraccion.ocr_relectura import modelo_de_relectura, releer_paginas
from app.exportacion import contar_filas_de_materiales
from app.models import (
    CacheOcrDocumento,
    Documento,
    DocumentoExpediente,
    EstadoExpediente,
    Expediente,
    LineaCatalogo,
    Lote,
    TipoDocumento,
)


@pytest.fixture()
def db_api():
    """Mismo motivo que en `tests/test_api_catalogo.py`: `TestClient` corre el
    ASGI app en otro hilo, y una conexión SQLite normal no se comparte entre
    hilos."""
    from app import models as m

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=[
        m.Expediente.__table__, m.Lote.__table__, m.Documento.__table__,
        m.DocumentoExpediente.__table__, m.LineaCatalogo.__table__, m.TrazaOrigen.__table__,
        m.SindicacionExpediente.__table__, m.CacheOcrDocumento.__table__,
        m.TrabajoCola.__table__,
    ])
    sesion = sessionmaker(bind=engine)()
    try:
        yield sesion
    finally:
        sesion.close()


@pytest.fixture()
def cliente(db_api):
    from app.main import app

    def _get_db_prueba():
        yield db_api

    app.dependency_overrides[get_db] = _get_db_prueba
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _cache_ocr(db, hash_documento="hash-relectura"):
    entrada = CacheOcrDocumento(
        documento_hash=hash_documento,
        version_logica_ocr=ocr_relectura.VERSION_LOGICA_OCR,
        modelo="claude-haiku-4-5",
        num_paginas=3,
        completo=True,
        paginas=[
            {"numero": 1, "texto": "portada", "bloques": []},
            {"numero": 2, "texto": "cabezado a panl, Transmísión", "bloques": []},
            {"numero": 3, "texto": "pie", "bloques": []},
        ],
    )
    db.add(entrada)
    db.commit()
    return entrada


def test_la_relectura_sustituye_solo_las_paginas_pedidas(db_session, monkeypatch):
    _cache_ocr(db_session)
    monkeypatch.setattr(
        ocr_relectura, "_leer_paginas",
        lambda datos, numeros, proveedor: [
            {"numero": n, "texto": f"pagina {n} bien leida", "bloques": [], "segundos": 1.0,
             "tokens_entrada": 100, "tokens_salida": 50}
            for n in numeros
        ],
    )
    resumen = releer_paginas(
        db_session, "hash-relectura", lambda: b"%PDF", object(), [2], "claude-opus-5"
    )
    assert resumen["paginas_sustituidas"] == [2]
    assert resumen["paginas_sin_cambio"] == []
    paginas = db_session.get(CacheOcrDocumento, "hash-relectura").paginas
    assert paginas[1]["texto"] == "pagina 2 bien leida"
    # Queda escrito de dónde sale cada página; el modelo base no cambia.
    assert paginas[1]["modelo"] == "claude-opus-5"
    assert "modelo" not in paginas[0]
    assert db_session.get(CacheOcrDocumento, "hash-relectura").modelo == "claude-haiku-4-5"


def test_una_relectura_con_error_o_vacia_no_pisa_lo_que_habia(db_session, monkeypatch):
    _cache_ocr(db_session)
    monkeypatch.setattr(
        ocr_relectura, "_leer_paginas",
        lambda datos, numeros, proveedor: [
            {"numero": 2, "texto": "", "bloques": [], "segundos": 0.1, "error": "sin saldo",
             "reintentar": True},
            {"numero": 3, "texto": "   ", "bloques": [], "segundos": 0.1},
        ],
    )
    resumen = releer_paginas(
        db_session, "hash-relectura", lambda: b"%PDF", object(), [2, 3], "claude-opus-5"
    )
    assert resumen["paginas_sustituidas"] == []
    assert resumen["paginas_sin_cambio"] == [2, 3]
    paginas = db_session.get(CacheOcrDocumento, "hash-relectura").paginas
    assert paginas[1]["texto"].startswith("cabezado")
    assert paginas[2]["texto"] == "pie"


def test_una_pagina_fuera_del_documento_no_se_relee(db_session):
    _cache_ocr(db_session)
    with pytest.raises(RuntimeError, match="fuera del documento"):
        releer_paginas(db_session, "hash-relectura", lambda: b"", object(), [9], "claude-opus-5")


def test_un_documento_sin_lectura_previa_no_es_una_relectura(db_session):
    with pytest.raises(RuntimeError, match="no tiene ninguna lectura"):
        releer_paginas(db_session, "sin-cache", lambda: b"", object(), [1], "claude-opus-5")


def test_sin_modelo_la_relectura_falla_en_vez_de_repetir_con_el_de_siempre():
    with pytest.raises(RuntimeError, match="sin modelo"):
        modelo_de_relectura({}, None)
    assert modelo_de_relectura({"modelo": "claude-opus-5"}, None) == "claude-opus-5"
    assert modelo_de_relectura({}, "claude-opus-5") == "claude-opus-5"


# --------------------------------------------------------------------------
# Bloque 5 — la Conciliación de la web sale del mismo recuento que el Excel
# --------------------------------------------------------------------------

def _expediente_con_lineas(db, codigo, lineas_con_lote, lineas_sin_lote=0, motivo=None):
    expediente = Expediente(codigo_expediente=codigo, estado=EstadoExpediente.completado)
    db.add(expediente)
    db.flush()
    lote = Lote(expediente_id=expediente.id, identificador_lote="1")
    db.add(lote)
    db.flush()
    for indice in range(lineas_con_lote):
        db.add(LineaCatalogo(
            expediente_id=expediente.id, lote_id=lote.id, clave_linea=f"{codigo}-{indice}",
            orden_aparicion=indice, descripcion=f"material {indice}",
            precio_unitario=Decimal("10"), motivo_revision=motivo,
        ))
    for indice in range(lineas_sin_lote):
        db.add(LineaCatalogo(
            expediente_id=expediente.id, lote_id=None, clave_linea=f"{codigo}-h{indice}",
            orden_aparicion=100 + indice, descripcion=f"huerfana {indice}",
            precio_unitario=Decimal("10"),
        ))
    db.commit()
    return expediente


def test_el_recuento_de_materiales_deja_fuera_lo_mismo_que_el_excel(db_session):
    from app.catalogo import MOTIVO_MAPEO_INCOHERENTE

    a = _expediente_con_lineas(db_session, "6.24/28510.0001", lineas_con_lote=3, lineas_sin_lote=2)
    b = _expediente_con_lineas(
        db_session, "6.24/28510.0002", lineas_con_lote=2, motivo=MOTIVO_MAPEO_INCOHERENTE
    )
    conteo = contar_filas_de_materiales(db_session)
    # Las huérfanas sin lote y las de mapeo incoherente no salen en el Excel.
    assert conteo[a.id] == 3
    assert b.id not in conteo


def test_conciliacion_devuelve_una_fila_por_expediente_y_su_recuento(cliente, db_api):
    from app.conciliacion import APORTA_LINEAS, SITUACIONES

    _expediente_con_lineas(db_api, "6.24/28510.0001", lineas_con_lote=3)
    respuesta = cliente.get("/conciliacion")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total"] == len(cuerpo["filas"]) == 1
    assert cuerpo["total_lineas"] == 3
    assert cuerpo["filas"][0]["codigo_expediente"] == "6.24/28510.0001"
    assert cuerpo["filas"][0]["lineas_en_catalogo"] == 3
    assert cuerpo["filas"][0]["situacion"] == APORTA_LINEAS
    # El recuento trae las once situaciones, incluidas las que están a 0.
    assert [s["situacion"] for s in cuerpo["situaciones"]] == list(SITUACIONES)


def test_conciliacion_filtra_por_situacion(cliente, db_api):
    from app.conciliacion import APORTA_LINEAS, OTRO

    _expediente_con_lineas(db_api, "6.24/28510.0001", lineas_con_lote=3)
    assert len(cliente.get("/conciliacion", params={"situacion": APORTA_LINEAS}).json()["filas"]) == 1
    vacia = cliente.get("/conciliacion", params={"situacion": OTRO}).json()
    assert vacia["filas"] == []
    # El recuento por situación sigue siendo el del total, no el del filtro.
    assert vacia["total"] == 1
