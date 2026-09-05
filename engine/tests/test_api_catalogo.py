"""Pruebas de la API de catálogo, revisión y documentos (CLAUDE.md, encargo
de esta sesión, puntos 1 a 4): sobre `TestClient` con SQLite en memoria, sin
Postgres levantado — mismo patrón que `db_session` de conftest.py."""
import io
from decimal import Decimal

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.config import settings
from app.db import Base, get_db
from app.interfaces.document_storage import LocalDiskStorage
from app.main import app
from app.models import (
    Documento,
    EstadoExpediente,
    EstadoRevisionLinea,
    Expediente,
    LineaCatalogo,
    Lote,
    TipoDocumento,
)

_TABLAS = [
    models.Expediente.__table__,
    models.Lote.__table__,
    models.Documento.__table__,
    models.LineaCatalogo.__table__,
    models.TrazaOrigen.__table__,
    models.MapeoCabeceraCache.__table__,
    models.TrabajoCola.__table__,
]


@pytest.fixture()
def db_session():
    # TestClient corre el ASGI app en un hilo de threadpool distinto del
    # hilo del test (starlette.concurrency.run_in_threadpool); una conexión
    # SQLite normal no se puede compartir entre hilos, así que hace falta
    # una única conexión fija (StaticPool + check_same_thread=False) en vez
    # de una nueva conexión ":memory:" (vacía) por hilo.
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


def _sembrar_catalogo(db_session, *, estado=EstadoExpediente.completado):
    expediente = Expediente(
        codigo_expediente="6.24/28510.0008",
        codigo_matriz=None,
        nombre_proyecto="SUMINISTRO DE GUANTES CONTRA RIESGO ELECTRICO.",
        estado=estado,
        error="no se pudo determinar la baja del lote" if estado == EstadoExpediente.pendiente_revision else None,
    )
    db_session.add(expediente)
    db_session.commit()

    lote = Lote(expediente_id=expediente.id, identificador_lote="1", baja_lote=Decimal("0.5400"))
    db_session.add(lote)
    db_session.commit()

    documento = Documento(
        expediente_id=expediente.id,
        tipo_documento=TipoDocumento.anejo,
        hash="hash-1",
        nombre_archivo="6.24_28510.0008_ANEJO_1.pdf",
        ruta_almacenamiento="6.24_28510.0008_ANEJO_1.pdf",
    )
    db_session.add(documento)
    db_session.commit()

    linea = LineaCatalogo(
        lote_id=lote.id,
        expediente_id=expediente.id,
        clave_linea="P-001",
        orden_aparicion=0,
        codigo_precio="P-001",
        matricula="697500900",
        descripcion="GUANTE CONTRA RIESGO ELECTRICO",
        codigo_material="GUANTE",
        cantidad=Decimal("30"),
        precio_unitario=Decimal("24.00"),
        baja_lote=Decimal("0.5400"),
        precio_adjudicado=Decimal("11.0400"),
        documento_origen_id=documento.id,
        pagina=11,
        fragmento="P-001 | GUANTE...",
    )
    db_session.add(linea)
    db_session.commit()
    return expediente, lote, documento, linea


def test_catalogo_lista_lineas_con_datos_de_expediente(cliente, db_session):
    _sembrar_catalogo(db_session)

    resp = cliente.get("/catalogo")

    assert resp.status_code == 200
    datos = resp.json()
    assert datos["total"] == 1
    fila = datos["lineas"][0]
    assert fila["codigo_expediente"] == "6.24/28510.0008"
    assert fila["matricula"] == "697500900"
    assert fila["precio_adjudicado"] == "11.0400"
    assert fila["documento_origen_nombre"] == "6.24_28510.0008_ANEJO_1.pdf"
    assert fila["pagina"] == 11


def test_catalogo_busqueda_por_matricula_a_traves_de_expedientes(cliente, db_session):
    _sembrar_catalogo(db_session)
    otro = Expediente(codigo_expediente="6.24/28510.9999", estado=EstadoExpediente.completado)
    db_session.add(otro)
    db_session.commit()
    otro_lote = Lote(expediente_id=otro.id, identificador_lote="1")
    db_session.add(otro_lote)
    db_session.commit()
    db_session.add(LineaCatalogo(
        lote_id=otro_lote.id, expediente_id=otro.id, clave_linea="P-099", orden_aparicion=0,
        matricula="697500900", descripcion="GUANTE OTRO EXPEDIENTE", precio_unitario=Decimal("25.00"),
    ))
    db_session.commit()

    resp = cliente.get("/catalogo", params={"matricula": "697500900"})

    assert resp.status_code == 200
    datos = resp.json()
    assert datos["total"] == 2
    expedientes = {f["codigo_expediente"] for f in datos["lineas"]}
    assert expedientes == {"6.24/28510.0008", "6.24/28510.9999"}


def test_catalogo_filtra_por_expediente_sin_afectar_a_otros(cliente, db_session):
    _sembrar_catalogo(db_session)

    resp = cliente.get("/catalogo", params={"expediente": "6.24/28510.9999"})

    assert resp.json()["total"] == 0


def test_exportar_catalogo_genera_xlsx_con_columnas_del_formato_esperado(cliente, db_session, tmp_path, monkeypatch):
    # Este test comprueba el caso "sin cruce" (fila[0]/fila[1] vacíos) --
    # tiene que valer sea cual sea el entorno local, incluso con un
    # docker-compose.override.yml real montando un Excel de códigos de
    # verdad (CODIGOS_PROYECTO_PATH no vacío fuera de este proceso de test).
    monkeypatch.setattr(settings, "codigos_proyecto_path", None)
    _sembrar_catalogo(db_session)

    resp = cliente.get("/catalogo/exportar.xlsx")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    ruta = tmp_path / "salida.xlsx"
    ruta.write_bytes(resp.content)
    libro = openpyxl.load_workbook(ruta)
    hoja = libro.active
    cabecera = [c.value for c in next(hoja.iter_rows(min_row=1, max_row=1))]
    # CLAUDE.md, encargo de esta sesión, punto 4: mismas columnas y mismo
    # orden que Ejemplo/Output/.
    assert cabecera == [
        "Código interno", "Código de proyecto", "Código matriz", "Nombre del proyecto",
        "Matrícula del material", "Descripción del material", "Código del material",
        "Cantidad", "Precio unitario", "Lote", "Comentarios",
    ]
    fila = [c.value for c in next(hoja.iter_rows(min_row=2, max_row=2))]
    assert fila[3] == "SUMINISTRO DE GUANTES CONTRA RIESGO ELECTRICO."
    assert fila[4] == "697500900"
    assert fila[5] == "GUANTE CONTRA RIESGO ELECTRICO"
    assert fila[8] == 24.0
    # Sin cruce con el Excel de códigos configurado en este test: código
    # interno y código de proyecto se dejan vacíos, no inventados
    # (CLAUDE.md sección 7).
    assert fila[0] is None
    assert fila[1] is None


def test_revision_lista_solo_pendientes(cliente, db_session):
    _sembrar_catalogo(db_session, estado=EstadoExpediente.pendiente_revision)

    resp = cliente.get("/revision")

    assert resp.status_code == 200
    datos = resp.json()
    assert len(datos) == 1
    assert datos[0]["estado"] == "pendiente_revision"
    assert datos[0]["error"] == "no se pudo determinar la baja del lote"


def test_detalle_revision_incluye_documentos_y_lineas(cliente, db_session):
    expediente, _lote, documento, _linea = _sembrar_catalogo(db_session, estado=EstadoExpediente.pendiente_revision)

    resp = cliente.get(f"/expedientes/{expediente.id}/revision")

    assert resp.status_code == 200
    datos = resp.json()
    assert datos["expediente"]["id"] == expediente.id
    assert len(datos["documentos"]) == 1
    assert datos["documentos"][0]["nombre_archivo"] == documento.nombre_archivo
    assert len(datos["lineas"]) == 1


def test_confirmar_revision_sin_cuerpo_marca_completado(cliente, db_session):
    expediente, _lote, _doc, _linea = _sembrar_catalogo(db_session, estado=EstadoExpediente.pendiente_revision)

    resp = cliente.post(f"/expedientes/{expediente.id}/revision/confirmar")

    assert resp.status_code == 200
    datos = resp.json()
    assert datos["estado"] == "completado"
    assert datos["error"] is None


def test_confirmar_revision_con_correccion_de_baja_recalcula_precio_adjudicado(cliente, db_session):
    expediente, lote, _doc, linea = _sembrar_catalogo(db_session, estado=EstadoExpediente.pendiente_revision)

    resp = cliente.post(
        f"/expedientes/{expediente.id}/revision/confirmar",
        json={"baja_global": "0.1000"},
    )

    assert resp.status_code == 200
    db_session.refresh(lote)
    db_session.refresh(linea)
    assert lote.baja_lote == Decimal("0.1000")
    assert linea.baja_lote == Decimal("0.1000")
    assert linea.precio_adjudicado == Decimal("21.6000")  # 24,00 * 0,90


def test_corregir_linea_catalogo_actualiza_y_marca_corregido(cliente, db_session):
    _expediente, _lote, _doc, linea = _sembrar_catalogo(db_session)

    resp = cliente.patch(
        f"/catalogo/lineas/{linea.id}",
        json={"matricula": "697500901", "comentarios": "matrícula corregida a mano"},
    )

    assert resp.status_code == 200
    datos = resp.json()
    assert datos["matricula"] == "697500901"
    assert datos["comentarios"] == "matrícula corregida a mano"
    assert datos["estado_revision"] == "corregido"
    # Un campo no incluido en la corrección no se borra (mismo criterio que
    # guardar_lineas_catalogo, CLAUDE.md sección 9.9).
    assert datos["descripcion"] == "GUANTE CONTRA RIESGO ELECTRICO"


def test_confirmar_linea_catalogo(cliente, db_session):
    _expediente, _lote, _doc, linea = _sembrar_catalogo(db_session)
    assert linea.estado_revision == EstadoRevisionLinea.sin_revisar

    resp = cliente.post(f"/catalogo/lineas/{linea.id}/confirmar")

    assert resp.status_code == 200
    assert resp.json()["estado_revision"] == "confirmado"


def test_descartar_linea_catalogo_exige_motivo(cliente, db_session):
    _expediente, _lote, _doc, linea = _sembrar_catalogo(db_session)

    resp = cliente.post(f"/catalogo/lineas/{linea.id}/descartar", json={"motivo": ""})

    assert resp.status_code == 422


def test_descartar_linea_catalogo(cliente, db_session):
    # CLAUDE.md bloque 2: una línea que no es material real, o no se puede
    # determinar, se saca del catálogo con un motivo -- nunca se borra.
    _expediente, _lote, _doc, linea = _sembrar_catalogo(db_session)

    resp = cliente.post(
        f"/catalogo/lineas/{linea.id}/descartar",
        json={"motivo": "es el epígrafe de la tabla, no una línea de material"},
    )

    assert resp.status_code == 200
    datos = resp.json()
    assert datos["estado_revision"] == "descartado"
    assert "es el epígrafe de la tabla" in datos["comentarios"]


def test_marcar_linea_pendiente_exige_nota(cliente, db_session):
    _expediente, _lote, _doc, linea = _sembrar_catalogo(db_session)

    resp = cliente.post(f"/catalogo/lineas/{linea.id}/pendiente", json={"nota": ""})

    assert resp.status_code == 422


def test_marcar_linea_pendiente(cliente, db_session):
    _expediente, _lote, _doc, linea = _sembrar_catalogo(db_session)

    resp = cliente.post(
        f"/catalogo/lineas/{linea.id}/pendiente",
        json={"nota": "consultar con compras si esta matrícula sigue vigente"},
    )

    assert resp.status_code == 200
    datos = resp.json()
    assert datos["estado_revision"] == "pendiente"
    assert "consultar con compras" in datos["comentarios"]


def test_descartar_y_pendiente_acumulan_comentarios_sin_perder_los_anteriores(cliente, db_session):
    _expediente, _lote, _doc, linea = _sembrar_catalogo(db_session)
    cliente.patch(f"/catalogo/lineas/{linea.id}", json={"comentarios": "nota original"})

    resp = cliente.post(f"/catalogo/lineas/{linea.id}/pendiente", json={"nota": "nota nueva"})

    datos = resp.json()
    assert "nota original" in datos["comentarios"]
    assert "nota nueva" in datos["comentarios"]


def test_exportar_catalogo_excluye_lineas_descartadas(cliente, db_session, monkeypatch):
    monkeypatch.setattr(settings, "codigos_proyecto_path", None)
    _expediente, _lote, _doc, linea = _sembrar_catalogo(db_session)
    cliente.post(f"/catalogo/lineas/{linea.id}/descartar", json={"motivo": "no es material real"})

    resp = cliente.get("/catalogo/exportar.xlsx")

    libro = openpyxl.load_workbook(io.BytesIO(resp.content))
    hoja = libro.active
    assert hoja.max_row == 1  # solo la cabecera: la única línea del catálogo estaba descartada


def test_catalogo_sigue_mostrando_lineas_descartadas(cliente, db_session):
    # A diferencia del Excel, la pantalla de catálogo/revisión no oculta las
    # descartadas -- CLAUDE.md bloque 2 solo pide excluirlas de la entrega.
    _expediente, _lote, _doc, linea = _sembrar_catalogo(db_session)
    cliente.post(f"/catalogo/lineas/{linea.id}/descartar", json={"motivo": "no es material real"})

    resp = cliente.get("/catalogo")

    assert resp.json()["total"] == 1


def test_descargar_documento_sirve_los_bytes_reales(cliente, db_session, tmp_path, monkeypatch):
    from app.routers import documentos as documentos_router

    _expediente, _lote, documento, _linea = _sembrar_catalogo(db_session)
    storage = LocalDiskStorage(str(tmp_path))
    storage.guardar(documento.ruta_almacenamiento, b"%PDF-1.4 contenido de prueba")
    monkeypatch.setattr(documentos_router, "_storage", storage)

    resp = cliente.get(f"/documentos/{documento.id}/archivo")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content == b"%PDF-1.4 contenido de prueba"


def test_descargar_documento_inexistente_da_404(cliente, db_session):
    resp = cliente.get("/documentos/999/archivo")
    assert resp.status_code == 404
