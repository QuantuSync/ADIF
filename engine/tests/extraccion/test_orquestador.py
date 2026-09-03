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
from tests.extraccion.dobles import ProveedorModeloCabeceraPorContenido, ProveedorModeloFalso


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


def test_expediente_sin_publicar_no_se_reprocesa(db_session):
    # CLAUDE.md sección 22: un expediente ya confirmado sin publicar no tiene
    # nada que extraer -- un trabajo de extracción encolado por error (o a
    # mano) no debe devolverlo a `pendiente_revision` con un motivo genérico,
    # perdiendo la marca ya verificada.
    expediente = Expediente(
        codigo_expediente="2.18/04703.0019",
        estado=EstadoExpediente.sin_publicar,
        error="no encontrado en la Plataforma ni por matriz ni por expediente: 2.18/04703.0019",
    )
    db_session.add(expediente)
    db_session.commit()
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    resultado = ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(expediente)
    assert expediente.estado == EstadoExpediente.sin_publicar
    assert "no encontrado en la Plataforma" in expediente.error
    assert resultado["estado"] == "sin_publicar"
    assert resultado["lineas_creadas"] == 0


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


def test_expediente_con_documento_escaneado_va_a_revision_con_motivo_distinto(db_session):
    # CLAUDE.md sección 3: un documento escaneado (sin capa de texto) no
    # aporta ninguna línea, pero el motivo debe decirlo explícitamente en vez
    # de confundirse con "no se extrajo ninguna línea de catálogo" (ese
    # motivo dice "se leyó pero no traía cuadro de precios"; este dice "no se
    # pudo leer en absoluto").
    expediente = _crear_expediente_con_documentos(
        db_session, "6.20/28510.0136", [("ANEJO", fx.DOCUMENTO_ESCANEADO_SIN_TEXTO)],
    )
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    resultado = ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(expediente)
    assert expediente.estado == EstadoExpediente.pendiente_revision
    assert "escaneado" in resultado["motivo_revision"]
    assert "no se extrajo ninguna línea" not in resultado["motivo_revision"]

    doc = db_session.query(Documento).filter_by(expediente_id=expediente.id).one()
    assert doc.procesado_en is None  # nunca se intentó procesar su tabla


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


def test_expediente_0027_multi_lote_produce_baja_correcta_por_lote(db_session):
    """Caso de aceptación de la sesión de extracción por lote: expediente
    real 6.25/28510.0027, "SUMINISTRO DE BALASTO... 6 LOTES", cuya Resolución
    de Adjudicación solo adjudica dos de los seis (LOTE 1 al 7,13 %, LOTE 3
    al 1,18 %, presupuestos distintos) — el caso que destapó que el motor se
    quedaba con la primera baja del texto y la presentaba como la del
    expediente entero.

    El modelo de esta cabecera concreta necesita un `ModelProvider` (la
    cabecera real trae un carácter corrompido, "CODIFICACI�N DEL PRECIO",
    que no casa con ningún alias determinista) — se usa
    `ProveedorModeloCabeceraPorContenido`, no un doble de respuesta fija, ver
    su docstring para el porqué (cabecera y filas de datos de esta tabla
    concreta no alinean su columna fantasma en el mismo índice)."""
    expediente = _crear_expediente_con_documentos(
        db_session,
        "6.25/28510.0027",
        [
            ("ADJUDICACION", fx.RESOLUCION_MULTI_LOTE),
            ("ANEJO", fx.ANEJO_PRECIOS_BALASTO_MULTI_LOTE),
        ],
    )
    trabajo = SimpleNamespace(expediente_id=expediente.id)
    modelo = ProveedorModeloCabeceraPorContenido()

    resultado = ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=modelo)

    db_session.refresh(expediente)
    lotes = db_session.query(Lote).filter_by(expediente_id=expediente.id).order_by(Lote.identificador_lote).all()
    assert [l.identificador_lote for l in lotes] == ["1", "3"]

    lote1, lote3 = lotes
    assert lote1.baja_lote == Decimal("0.0713")
    assert lote1.importe_licitacion == Decimal("593375.00")
    assert lote1.importe_adjudicacion == Decimal("593375.00")
    assert lote1.adjudicatario == "ÁRIDOS DE VILLACASTÍN, S.A."

    assert lote3.baja_lote == Decimal("0.0118")
    assert lote3.importe_licitacion == Decimal("853250.00")
    assert lote3.importe_adjudicacion == Decimal("853250.00")
    assert lote3.adjudicatario == "EMIPESA, S.A."

    # CLAUDE.md, encargo de esta sesión, punto 4: un expediente con lotes de
    # bajas distintas no tiene una baja única — nunca se inventa una media,
    # y la web tiene que poder explicar el vacío (ajuste 3, `baja_variable_por_lote`).
    assert expediente.baja_global is None
    assert expediente.baja_variable_por_lote is True
    assert expediente.importe_licitacion == Decimal("1446625.00")
    assert expediente.importe_adjudicacion == Decimal("1446625.00")

    # Las trazas de baja/importe declarado cuelgan del lote, no del
    # expediente (`_traza(..., entidad_tipo="lote")`).
    trazas_lote = db_session.query(TrazaOrigen).filter_by(entidad_tipo="lote").all()
    assert {t.entidad_id for t in trazas_lote} == {lote1.id, lote3.id}

    # Cuadro de precios: los seis lotes del Pliego (1 a 6) traen tabla de
    # precios, pero solo 1 y 3 están entre los lotes declarados por la
    # Resolución (CLAUDE.md, encargo de esta sesión, punto 3: la tabla de un
    # lote no adjudicado, o cuya cabecera "LOTE N" no se pudo leer en la
    # franja que le precede, no se asigna por cercanía — queda huérfana).
    lineas_lote3 = (
        db_session.query(LineaCatalogo)
        .filter_by(lote_id=lote3.id)
        .order_by(LineaCatalogo.codigo_precio)
        .all()
    )
    assert [l.codigo_precio for l in lineas_lote3] == ["P-1", "P-2", "P-3", "P-4", "P-5", "P-6"]
    p1 = lineas_lote3[0]
    assert p1.precio_unitario == Decimal("10.8500")
    # 10,85 * (1 - 0,0118) — la baja de SU lote, no la del expediente
    # (CLAUDE.md, encargo de esta sesión, punto 2). Numeric(14, 4) en la
    # columna redondea a 4 decimales al guardar.
    assert p1.precio_adjudicado == Decimal("10.7220")
    assert all(l.expediente_id == expediente.id for l in lineas_lote3)

    huerfanas = (
        db_session.query(LineaCatalogo)
        .filter_by(expediente_id=expediente.id, lote_id=None)
        .all()
    )
    assert len(huerfanas) > 0
    assert all(l.motivo_revision for l in huerfanas)
    assert all(l.expediente_id == expediente.id for l in huerfanas)
    # 28, no 6: LOTE 2, 4, 5 y 6 tienen todos su propio "P-1".."P-6" — sin
    # lote que las separe, fundirlas por `codigo_precio` a secas mezclaría
    # datos reales de lotes distintos entre sí (bug real encontrado al
    # verificar contra el stack real: antes de desambiguar por página y
    # posición de tabla en `app.extraccion.pipeline_anejo`, esto colapsaba a
    # solo 6 filas).
    assert len(huerfanas) == 28
    # LOTE 1 sí llega a asociarse a su lote (sesión de expedientes sin
    # publicar, bajada del umbral de densidad de `app.extraccion.localizador`
    # de 0,04 a 0,025): su tabla se reparte entre dos páginas, y la página con
    # "P-1"/"P-2" tenía una densidad numérica (0,032) que quedaba por debajo
    # del umbral antiguo — invisible para la cascada entera, ni siquiera
    # llegaba a intentar leer la cabecera "LOTE 1" que sí la precede. Con el
    # umbral nuevo la página se localiza, `app.extraccion.lote_tabla` encuentra
    # la cabecera y las dos primeras líneas de LOTE 1 dejan de perderse.
    lineas_lote1 = (
        db_session.query(LineaCatalogo)
        .filter_by(lote_id=lote1.id)
        .order_by(LineaCatalogo.codigo_precio)
        .all()
    )
    assert [l.codigo_precio for l in lineas_lote1] == ["P-1", "P-2"]
    assert lineas_lote1[0].precio_unitario == Decimal("10.8500")

    # Con líneas huérfanas, el expediente va a revisión — no se presenta
    # como completado un catálogo con líneas sin lote determinado.
    assert expediente.estado == EstadoExpediente.pendiente_revision
    assert expediente.error is not None
    assert resultado["lotes"] == ["1", "3"]
    assert resultado["motivo_revision"] is not None
