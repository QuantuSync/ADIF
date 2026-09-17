"""Reconocimiento óptico de documentos escaneados (sesión 2026-09-17,
`app.extraccion.ocr`): las tres condiciones del cliente -- solo documentos
sin capa de texto y desactivable, línea marcada, y sin repetir la lectura."""
from __future__ import annotations

import io
from types import SimpleNamespace

import pdfplumber
import pypdfium2 as pdfium

from app.config import settings
from app.extraccion.ocr import MARCA_FRAGMENTO, MOTIVO_TEXTO_RECONOCIDO
from app.extraccion.ocr_pdf import generar_pdf_reconocido
from app.extraccion.orquestador import ejecutar_extraccion_expediente
from app.models import CacheOcrDocumento, LineaCatalogo, TrazaOrigen
from tests import fixtures as fx
from tests.extraccion.dobles import ProveedorVisionFalso
from tests.extraccion.test_orquestador import _crear_expediente_con_documentos, _StorageDirecta


def _pdf_escaneado(tmp_path, paginas: int):
    """PDF sin capa de texto de `paginas` páginas (el fixture real escaneado
    solo trae una)."""
    documento = pdfium.PdfDocument.new()
    for _ in range(paginas):
        documento.new_page(595, 842)
    ruta = tmp_path / "ANEJO_ESCANEADO.pdf"
    with open(ruta, "wb") as salida:
        documento.save(salida)
    return ruta


def _extraer(db_session, expediente, proveedor):
    trabajo = SimpleNamespace(expediente_id=expediente.id)
    return ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=proveedor)


def test_documento_escaneado_se_lee_y_sus_lineas_quedan_marcadas(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ocr_paralelismo", 1)
    expediente = _crear_expediente_con_documentos(
        db_session, "6.20/28510.0136", [("ANEJO", _pdf_escaneado(tmp_path, 4))],
    )
    proveedor = ProveedorVisionFalso()

    resultado = _extraer(db_session, expediente, proveedor)

    lineas = db_session.query(LineaCatalogo).filter_by(expediente_id=expediente.id).all()
    assert lineas
    assert all(l.texto_reconocido for l in lineas)
    assert all(MOTIVO_TEXTO_RECONOCIDO in (l.motivo_revision or "") for l in lineas)
    assert all(l.fragmento.startswith(MARCA_FRAGMENTO) for l in lineas)
    assert "reconocimiento óptico" in resultado["motivo_revision"]
    assert "sin capa de texto (fuera de alcance" not in resultado["motivo_revision"]
    cache = db_session.query(CacheOcrDocumento).one()
    assert cache.completo is True
    assert proveedor.llamadas_imagen == cache.num_paginas


def test_texto_reconocido_no_se_vuelve_a_leer(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ocr_paralelismo", 1)
    expediente = _crear_expediente_con_documentos(
        db_session, "6.20/28510.0136", [("ANEJO", _pdf_escaneado(tmp_path, 4))],
    )
    proveedor = ProveedorVisionFalso()
    _extraer(db_session, expediente, proveedor)
    llamadas = proveedor.llamadas_imagen
    lineas = db_session.query(LineaCatalogo).filter_by(expediente_id=expediente.id).count()

    _extraer(db_session, expediente, proveedor)

    assert proveedor.llamadas_imagen == llamadas
    assert db_session.query(LineaCatalogo).filter_by(expediente_id=expediente.id).count() == lineas


def test_pliego_administrativo_escaneado_se_deja_tras_las_primeras_paginas(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ocr_paralelismo", 1)
    expediente = _crear_expediente_con_documentos(
        db_session, "6.20/28510.0136", [("ANEJO", _pdf_escaneado(tmp_path, 4))],
    )
    proveedor = ProveedorVisionFalso(portada="PLIEGO DE CLÁUSULAS ADMINISTRATIVAS PARTICULARES")

    _extraer(db_session, expediente, proveedor)

    assert proveedor.llamadas_imagen == 2
    assert db_session.query(CacheOcrDocumento).one().completo is False
    assert db_session.query(LineaCatalogo).filter_by(expediente_id=expediente.id).count() == 0


def test_desactivado_no_lee_nada(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ocr_modo", "desactivado")
    expediente = _crear_expediente_con_documentos(
        db_session, "6.20/28510.0136", [("ANEJO", fx.DOCUMENTO_ESCANEADO_SIN_TEXTO)],
    )
    proveedor = ProveedorVisionFalso()

    resultado = _extraer(db_session, expediente, proveedor)

    assert proveedor.llamadas_imagen == 0
    assert "escaneado" in resultado["motivo_revision"]


def test_documento_con_texto_nunca_pasa_por_reconocimiento(db_session):
    expediente = _crear_expediente_con_documentos(
        db_session, "6.24/28510.0008",
        [("ADJUDICACION", fx.PROPUESTA_LC27_PRECIOS_UNITARIOS), ("ANEJO", fx.ANEJO_PRECIOS_GUANTES)],
    )
    proveedor = ProveedorVisionFalso()

    _extraer(db_session, expediente, proveedor)

    assert proveedor.llamadas_imagen == 0
    assert db_session.query(CacheOcrDocumento).count() == 0
    assert not any(l.texto_reconocido for l in db_session.query(LineaCatalogo).all())
    assert not any(
        (t.fragmento or "").startswith(MARCA_FRAGMENTO) for t in db_session.query(TrazaOrigen).all()
    )


def test_pdf_reconocido_conserva_numeracion_texto_y_rejilla():
    datos = generar_pdf_reconocido([
        {"numero": 2, "bloques": [
            {"tipo": "texto", "texto": "LOTE 2: Tornillería – precios (€)", "filas": []},
            {"tipo": "tabla", "texto": "", "filas": [
                ["MATRÍCULA", "DESCRIPCIÓN", "PRECIO UNITARIO"],
                ["691616560", "TORNILLO CABEZA EXAGONAL,\nM20X335", "3,18 €"],
            ]},
        ]},
    ])
    with pdfplumber.open(io.BytesIO(datos)) as pdf:
        assert len(pdf.pages) == 2
        pagina = pdf.pages[1]
        assert "LOTE 2: Tornillería - precios (€)" in pagina.extract_text()
        assert pagina.extract_tables() == [[
            ["MATRÍCULA", "DESCRIPCIÓN", "PRECIO UNITARIO"],
            ["691616560", "TORNILLO CABEZA EXAGONAL,\nM20X335", "3,18 €"],
        ]]
