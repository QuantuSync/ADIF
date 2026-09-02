"""Caso de aceptación de esta sesión (cola y seguimiento, CLAUDE.md punto 3):
el trabajo "extraer_expediente" corriendo sobre los documentos reales de un
expediente completo, no piezas sueltas de la cascada probadas por separado.
Usa los tres fixtures reales del expediente 6.24/28510.0008 (propuesta
LC.27, anejo/pliego con el cuadro de precios, contrato) tal como quedarían
en `documentos` tras una descarga real."""
from __future__ import annotations
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import openpyxl

from app.config import settings
from app.extraccion.orquestador import LOTE_UNICO, ejecutar_extraccion_expediente
from app.interfaces.document_storage import DocumentStorage
from app.models import Documento, EstadoExpediente, Expediente, Lote, LineaCatalogo, TipoDocumento, TrazaOrigen
from tests import fixtures as fx


class _StorageDirecta(DocumentStorage):
    """Test double: `ruta_almacenamiento` es directamente la ruta absoluta
    del fixture, así que `recuperar` solo tiene que leer el fichero."""

    def guardar(self, nombre: str, contenido: bytes) -> str:
        raise NotImplementedError

    def recuperar(self, ruta: str) -> bytes:
        return Path(ruta).read_bytes()

    def listar(self, prefijo: str = "") -> list[str]:
        raise NotImplementedError


def _crear_expediente_con_documentos(db_session, codigo_expediente, rutas: list[tuple[str, Path]]):
    expediente = Expediente(codigo_expediente=codigo_expediente)
    db_session.add(expediente)
    db_session.commit()
    for categoria, ruta in rutas:
        db_session.add(Documento(
            expediente_id=expediente.id,
            tipo_documento=TipoDocumento.otro,  # placeholder del scraper; el orquestador lo corrige
            hash=f"hash-{codigo_expediente}-{categoria}",
            nombre_archivo=ruta.name,
            ruta_almacenamiento=str(ruta),
        ))
    db_session.commit()
    return expediente


def test_expediente_0008_completo_produce_catalogo_y_pasa_a_completado(db_session):
    expediente = _crear_expediente_con_documentos(
        db_session,
        "6.24/28510.0008",
        [
            ("ADJUDICACION", fx.PROPUESTA_LC27_PRECIOS_UNITARIOS),
            ("ANEJO", fx.ANEJO_PRECIOS_GUANTES),
            ("CONTRATO", fx.CONTRATO_PRECIOS_UNITARIOS),
        ],
    )
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    resultado = ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(expediente)
    assert expediente.estado == EstadoExpediente.completado
    assert expediente.error is None
    assert expediente.importe_licitacion == Decimal("138000.00")
    assert expediente.importe_adjudicacion == Decimal("138000.00")
    # Caso central del proyecto (CLAUDE.md sección 4): no 0%, la baja
    # declarada en texto.
    assert expediente.baja_global == Decimal("0.5400")
    # Objeto del contrato (CLAUDE.md sección 7): sale de la Propuesta LC.27
    # a falta de Anuncio PCSP en este expediente de fixture.
    assert expediente.nombre_proyecto == "SUMINISTRO DE GUANTES CONTRA RIESGO ELECTRICO."

    lote = db_session.query(Lote).filter_by(expediente_id=expediente.id, identificador_lote=LOTE_UNICO).one()
    assert lote.baja_lote == Decimal("0.5400")

    lineas = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id).all()
    assert len(lineas) == 13
    primera = next(l for l in lineas if l.codigo_precio == "P-001")
    assert primera.precio_unitario == Decimal("24.00")
    assert primera.precio_adjudicado == Decimal("11.0400")

    assert resultado["estado"] == "completado"
    assert resultado["motivo_revision"] is None

    # El documento que trae el cuadro de precios (en realidad un pliego
    # completo, CLAUDE.md sección 3) se reclasifica por contenido, no por la
    # categoría que le puso el scraper.
    doc_anejo = db_session.query(Documento).filter_by(nombre_archivo=fx.ANEJO_PRECIOS_GUANTES.name).one()
    assert doc_anejo.tipo_documento in (TipoDocumento.pliego, TipoDocumento.anejo)
    assert doc_anejo.procesado_en is not None

    # Trazabilidad (CLAUDE.md sección 9.10): las cifras de expediente
    # también quedan ancladas a documento/página/fragmento.
    trazas = db_session.query(TrazaOrigen).filter_by(entidad_tipo="expediente", entidad_id=expediente.id).all()
    campos_trazados = {t.campo for t in trazas}
    assert "baja_declarada" in campos_trazados


def test_expediente_sin_documentos_va_a_revision_no_a_fallido(db_session):
    expediente = Expediente(codigo_expediente="6.24/28510.9999")
    db_session.add(expediente)
    db_session.commit()
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    resultado = ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(expediente)
    assert expediente.estado == EstadoExpediente.pendiente_revision
    assert expediente.error is not None
    assert resultado["motivo_revision"] is not None


def test_expediente_0008_cruza_codigo_interno_del_excel_de_referencia(db_session, tmp_path, monkeypatch):
    # CLAUDE.md sección 7: cruce por clave exacta contra el Excel de
    # códigos, ejecutado como parte del mismo trabajo de extracción.
    ruta_excel = tmp_path / "Codigos_de_proyecto.xlsx"
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.append(["Nº Interno", "Nº Expediente", "MATRIZ", "ESPECIALIDAD/DISCIPLINA", "DESCRIPCIÓN"])
    hoja.append([24099, "6.24/28510.0008", None, "EPI", "Guantes"])
    libro.save(ruta_excel)
    monkeypatch.setattr(settings, "codigos_proyecto_path", str(ruta_excel))

    expediente = _crear_expediente_con_documentos(
        db_session,
        "6.24/28510.0008",
        [
            ("ADJUDICACION", fx.PROPUESTA_LC27_PRECIOS_UNITARIOS),
            ("ANEJO", fx.ANEJO_PRECIOS_GUANTES),
            ("CONTRATO", fx.CONTRATO_PRECIOS_UNITARIOS),
        ],
    )
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(expediente)
    assert expediente.codigos_cruzados is True
    assert expediente.codigo_interno == "24099"


def test_expediente_sin_codigo_en_excel_de_referencia_se_marca_sin_cruzar(db_session, tmp_path, monkeypatch):
    ruta_excel = tmp_path / "Codigos_de_proyecto.xlsx"
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.append(["Nº Interno", "Nº Expediente", "MATRIZ", "ESPECIALIDAD/DISCIPLINA", "DESCRIPCIÓN"])
    hoja.append([1, "6.24/28510.9998", None, "otra", "otra"])
    libro.save(ruta_excel)
    monkeypatch.setattr(settings, "codigos_proyecto_path", str(ruta_excel))

    expediente = _crear_expediente_con_documentos(
        db_session,
        "6.24/28510.0008",
        [
            ("ADJUDICACION", fx.PROPUESTA_LC27_PRECIOS_UNITARIOS),
            ("ANEJO", fx.ANEJO_PRECIOS_GUANTES),
            ("CONTRATO", fx.CONTRATO_PRECIOS_UNITARIOS),
        ],
    )
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(expediente)
    assert expediente.codigos_cruzados is False
    assert expediente.codigo_interno is None


def test_trabajo_sin_expediente_id_falla_con_mensaje_claro(db_session):
    trabajo = SimpleNamespace(expediente_id=None)
    try:
        ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)
        assert False, "debía lanzar"
    except RuntimeError as exc:
        assert "expediente_id" in str(exc)
