"""Caso de aceptación de esta sesión (cola y seguimiento, CONTEXTO.md punto 3):
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
from app.extraccion.orquestador import (
    LOTE_UNICO,
    _Documento,
    _detectar_contrato_obra,
    _detectar_documento_adjudicacion_no_relacionado,
    _detectar_numero_lotes_pcsp,
    _el_cuadro_declara_todos_los_lotes,
    _extraer_campos_expediente,
    _extraer_lotes_declarados_del_expediente,
    _lote_propio,
    _lotes_candidatos_del_cuadro,
    ejecutar_extraccion_expediente,
)
from app.extraccion.invalidado import INVALIDADO
from app.extraccion.texto import PaginaTexto, extraer_texto
from app.interfaces.document_storage import DocumentStorage
from app.models import (
    Documento,
    DocumentoExpediente,
    EstadoExpediente,
    Expediente,
    Lote,
    LineaCatalogo,
    TipoDocumento,
    TrazaOrigen,
)
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
        documento = Documento(
            tipo_documento=TipoDocumento.otro,  # placeholder del scraper; el orquestador lo corrige
            hash=f"hash-{codigo_expediente}-{categoria}",
            ruta_almacenamiento=str(ruta),
        )
        db_session.add(documento)
        db_session.commit()
        db_session.add(DocumentoExpediente(
            documento_id=documento.id, expediente_id=expediente.id, nombre_archivo=ruta.name,
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
    # Caso central del proyecto (CONTEXTO.md sección 4): no 0%, la baja
    # declarada en texto.
    assert expediente.baja_global == Decimal("0.5400")
    # Objeto del contrato (CONTEXTO.md sección 7): sale de la Propuesta LC.27
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
    # completo, CONTEXTO.md sección 3) se reclasifica por contenido, no por la
    # categoría que le puso el scraper.
    doc_anejo = (
        db_session.query(Documento)
        .join(DocumentoExpediente, DocumentoExpediente.documento_id == Documento.id)
        .filter(DocumentoExpediente.nombre_archivo == fx.ANEJO_PRECIOS_GUANTES.name)
        .one()
    )
    assert doc_anejo.tipo_documento in (TipoDocumento.pliego, TipoDocumento.anejo)
    assert doc_anejo.procesado_en is not None

    # Trazabilidad (CONTEXTO.md sección 9.10): las cifras de expediente
    # también quedan ancladas a documento/página/fragmento.
    trazas = db_session.query(TrazaOrigen).filter_by(entidad_tipo="expediente", entidad_id=expediente.id).all()
    campos_trazados = {t.campo for t in trazas}
    assert "baja_declarada" in campos_trazados


def test_reextraer_no_duplica_trazas(db_session):
    # Sesión 2026-09-17: cada pasada añadía otra vez la misma traza (35.777
    # filas para unas 2.000 distintas en la base real), contra el invariante 9.
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
    primera = sorted(
        (t.entidad_tipo, t.entidad_id, t.campo, t.documento_id, t.pagina, t.valor_extraido)
        for t in db_session.query(TrazaOrigen).all()
    )
    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)
    segunda = sorted(
        (t.entidad_tipo, t.entidad_id, t.campo, t.documento_id, t.pagina, t.valor_extraido)
        for t in db_session.query(TrazaOrigen).all()
    )

    assert primera
    assert segunda == primera


def test_expediente_sin_publicar_no_se_reprocesa(db_session):
    # CONTEXTO.md sección 22: un expediente ya confirmado sin publicar no tiene
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


def test_expediente_sin_anejo_ni_pliego_da_motivo_especifico_de_cuadro_ausente(db_session):
    # Caso real, 6.24/28510.0025 y 6.24/28510.0193 (sesión de trabajo
    # pendiente real, 2026-09-05, docs/hallazgos-extraccion.md sección
    # 31.1): solo Adjudicación y Contrato, sin ningún Anejo/Pliego con
    # posibilidad de traer precios -- el motivo debe decirlo, distinto del
    # genérico "no se extrajo ninguna línea" que suena a fallo del
    # localizador de tablas cuando en realidad el documento nunca existió.
    expediente = _crear_expediente_con_documentos(
        db_session,
        "6.24/28510.0025",
        [
            ("ADJUDICACION", fx.PROPUESTA_LC27_PRECIOS_UNITARIOS),
            ("CONTRATO", fx.CONTRATO_PRECIOS_UNITARIOS),
        ],
    )
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    resultado = ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(expediente)
    assert expediente.estado == EstadoExpediente.pendiente_revision
    assert "no trae ningún Anejo ni" in resultado["motivo_revision"]
    assert resultado["lineas_creadas"] == 0


def test_expediente_con_documento_escaneado_va_a_revision_con_motivo_distinto(db_session):
    # CONTEXTO.md sección 3: un documento escaneado (sin capa de texto) no
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

    doc = (
        db_session.query(Documento)
        .join(DocumentoExpediente, DocumentoExpediente.documento_id == Documento.id)
        .filter(DocumentoExpediente.expediente_id == expediente.id)
        .one()
    )
    assert doc.procesado_en is None  # nunca se intentó procesar su tabla


def test_documento_escaneado_no_bloquea_si_el_resto_ya_resolvio_el_expediente(db_session):
    # Sesión de trabajo pendiente real (2026-09-05), caso real
    # `6.20/28510.0136`: el documento escaneado (Pliego de Cláusulas
    # Administrativas, verificado a mano sin cuadro de precios, misma
    # familia que CONTEXTO.md sección 26) convive con otros documentos reales
    # que ya dan baja, importes y líneas completas -- forzar revisión solo
    # por la existencia del escaneado sería más cauto de lo que los propios
    # datos justifican. Antes de esta sesión, cualquier documento escaneado
    # bloqueaba `completado` sin condición.
    expediente = _crear_expediente_con_documentos(
        db_session,
        "6.20/28510.0136",
        [
            ("ADJUDICACION", fx.PROPUESTA_LC27_PRECIOS_UNITARIOS),
            ("ANEJO", fx.ANEJO_PRECIOS_GUANTES),
            ("CONTRATO", fx.CONTRATO_PRECIOS_UNITARIOS),
            ("ANEJO_ESCANEADO", fx.DOCUMENTO_ESCANEADO_SIN_TEXTO),
        ],
    )
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    resultado = ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(expediente)
    assert expediente.estado == EstadoExpediente.completado
    assert expediente.error is None
    assert resultado["motivo_revision"] is None
    # El aviso queda registrado aparte, sin bloquear el estado (mismo
    # espíritu que `aviso_sindicacion`, CONTEXTO.md sección 12).
    assert "escaneado" in resultado["aviso_documento_escaneado"]

    doc_escaneado = (
        db_session.query(Documento)
        .join(DocumentoExpediente, DocumentoExpediente.documento_id == Documento.id)
        .filter(
            DocumentoExpediente.expediente_id == expediente.id,
            DocumentoExpediente.nombre_archivo == fx.DOCUMENTO_ESCANEADO_SIN_TEXTO.name,
        )
        .one()
    )
    assert doc_escaneado.procesado_en is None  # nunca se intentó procesar su tabla


def test_expediente_0008_cruza_codigo_interno_del_excel_de_referencia(db_session, tmp_path, monkeypatch):
    # CONTEXTO.md sección 7: cruce por clave exacta contra el Excel de
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

    # CONTEXTO.md, encargo de esta sesión, punto 4: un expediente con lotes de
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
    # Resolución (CONTEXTO.md, encargo de esta sesión, punto 3: la tabla de un
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
    # (CONTEXTO.md, encargo de esta sesión, punto 2). Numeric(14, 4) en la
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
    # 24, no 6: LOTE 2, 4, 5 y 6 tienen todos su propio "P-1".."P-6" — sin
    # lote que las separe, fundirlas por `codigo_precio` a secas mezclaría
    # datos reales de lotes distintos entre sí (bug real encontrado al
    # verificar contra el stack real: antes de desambiguar por página y
    # posición de tabla en `app.extraccion.pipeline_anejo`, esto colapsaba a
    # solo 6 filas).
    #
    # 24, no 28 (sesión de herencia de lote entre páginas de continuación,
    # 2026-09-08): las 4 líneas de menos son "P-3".."P-6" de LOTE 1, que
    # SÍ pertenecen a un lote declarado -- ver `lineas_lote1` más abajo. No
    # están entre las huérfanas de LOTE 2/4/5/6 (esas siguen siendo 24 en
    # total: 6+6+6+6), que siguen sin resolverse porque cada una tiene su
    # propia cabecera "LOTE N" real, solo que no declarada -- una mención
    # real de "LOTE", aunque rechazada, corta la cadena de herencia
    # (`app.extraccion.pipeline_anejo`, `ultimo_lote_resuelto = None`): la
    # continuación de LOTE 6 en la página siguiente (P-6 suelto) se queda
    # huérfana en vez de heredar a ciegas el último lote VÁLIDO visto mucho
    # antes (LOTE 1) -- justo el riesgo de mezclar lotes que motivó pedir
    # esta verificación antes de aprobar la propuesta.
    assert len(huerfanas) == 24
    # LOTE 1 ya llega completo a las 6 líneas reales (antes de esta sesión,
    # sesión de expedientes sin publicar: solo "P-1"/"P-2", bajada del
    # umbral de densidad de `app.extraccion.localizador` de 0,04 a 0,025 --
    # su tabla se reparte entre dos páginas, y la página con "P-1"/"P-2"
    # tenía una densidad numérica, 0,032, que quedaba por debajo del umbral
    # antiguo). "P-3".."P-6" de LOTE 1 están en la página SIGUIENTE, sin
    # ninguna cabecera "LOTE" propia (confirmado contra el PDF real: la
    # banda que los precede está vacía de la palabra "LOTE", la cabecera
    # "LOTE 2" real aparece más abajo, ya después de estas cuatro filas,
    # introduciendo la tabla siguiente) -- se perdían como huérfanas hasta
    # esta sesión (herencia de lote entre páginas de continuación, aprobada
    # por el cliente tras verificar que aquí no hay ningún candidato de
    # LOTE distinto al que pudieran pertenecer en su lugar).
    lineas_lote1 = (
        db_session.query(LineaCatalogo)
        .filter_by(lote_id=lote1.id)
        .order_by(LineaCatalogo.codigo_precio)
        .all()
    )
    assert [l.codigo_precio for l in lineas_lote1] == ["P-1", "P-2", "P-3", "P-4", "P-5", "P-6"]
    assert lineas_lote1[0].precio_unitario == Decimal("10.8500")
    # Trazabilidad: P-1/P-2 vinieron de la cabecera propia de LOTE 1
    # (`lote_heredado_de_pagina_anterior` en None); P-3..P-6 vinieron de
    # heredar, y tienen que poder distinguirse como tales (encargo explícito
    # del cliente al aprobar la propuesta).
    heredadas = {l.codigo_precio: l.lote_heredado_de_pagina_anterior for l in lineas_lote1}
    assert heredadas["P-1"] is None
    assert heredadas["P-2"] is None
    for codigo in ("P-3", "P-4", "P-5", "P-6"):
        assert heredadas[codigo] is True
    # Ninguna otra línea del expediente (LOTE 3, ni ninguna huérfana) se
    # marca como heredada: la herencia es un mecanismo acotado a este caso
    # concreto, no un efecto secundario que toque el resto del expediente.
    assert all(l.lote_heredado_de_pagina_anterior is None for l in lineas_lote3)
    assert all(l.lote_heredado_de_pagina_anterior is None for l in huerfanas)

    # Con líneas huérfanas, el expediente va a revisión — no se presenta
    # como completado un catálogo con líneas sin lote determinado.
    assert expediente.estado == EstadoExpediente.pendiente_revision
    assert expediente.error is not None
    assert resultado["lotes"] == ["1", "3"]
    assert resultado["motivo_revision"] is not None


# --- CONTEXTO.md sección 27: sesión de identidad de lote ---------------------


def test_expediente_0124_lote_2_de_dos_no_usa_sentinela(db_session):
    """6.24/28510.0124 solo trae la Resolución del LOTE 2 de una licitación
    de 2 lotes -- el cuerpo nunca repite "LOTE N", así que antes de esta
    sesión el lote quedaba etiquetado con el sentinela `LOTE_UNICO` ("1"),
    no con su número real (2). Sin ningún ANEJO en este fixture no hay
    catálogo que extraer, pero el lote sí debe quedar identificado
    correctamente y el expediente marcado con cobertura parcial (1 de 2)."""
    expediente = _crear_expediente_con_documentos(
        db_session, "6.24/28510.0124", [("ADJUDICACION", fx.RESOLUCION_ADJUDICACION)],
    )
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(expediente)
    lotes = db_session.query(Lote).filter_by(expediente_id=expediente.id).all()
    assert [l.identificador_lote for l in lotes] == ["2"]
    assert lotes[0].baja_lote == Decimal("0.0450")
    assert lotes[0].codigo_expediente_lote == "6.24/28510.0179"
    assert expediente.lotes_totales_declarados == 2
    assert expediente.estado == EstadoExpediente.pendiente_revision
    assert "cobertura parcial: 1 de 2" in expediente.error


def test_lote_unico_guarda_adjudicatario_del_anuncio_pcsp(db_session):
    """Hallazgo de paso (sesión de descubrimiento inverso): el Anuncio PCSP
    ya traía el adjudicatario por etiqueta fija (`campos_pcsp`), pero el
    camino de lote único implícito -- el que usan la mayoría de expedientes
    del corpus, incluidas las tres matrices de carril de esa sesión -- nunca
    lo guardaba en `lotes.adjudicatario` (solo el camino multi-lote
    explícito lo hacía, desde otra fuente). Sin él, el descubrimiento
    inverso (`app.extraccion.descubrimiento_matriz`) no tiene con qué
    acotar su búsqueda de pedidos en la Plataforma."""
    expediente = _crear_expediente_con_documentos(
        db_session, "6.24/28510.0193", [("ADJUDICACION", fx.ANUNCIO_PCSP_SIN_MATRIZ)],
    )
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    lote = db_session.query(Lote).filter_by(expediente_id=expediente.id, identificador_lote=LOTE_UNICO).one()
    assert lote.adjudicatario == "Enclavamientos Señaliza Ferroviaria"


def test_tres_lotes_completos_no_generan_motivo_de_cobertura_parcial(db_session):
    # 6.24/28510.0117: los tres lotes de la licitación traen baja/importe en
    # el mismo documento -- ninguna cobertura parcial que señalar, aunque el
    # expediente siga en revisión por falta de catálogo (sin ANEJO en este
    # fixture).
    expediente = _crear_expediente_con_documentos(
        db_session, "6.24/28510.0117", [("ADJUDICACION", fx.PROPUESTA_LC27_TRES_LOTES_BAJA_ENTRE_PAGINAS)],
    )
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(expediente)
    assert expediente.lotes_totales_declarados == 3
    assert "cobertura parcial" not in (expediente.error or "")


def test_expediente_0028_con_hueco_en_la_numeracion_marca_cobertura_parcial(db_session):
    # Encargo explícito del cliente (CONTEXTO.md sección 27): 6.25/28510.0028
    # declara "7 LOTES" pero el LOTE 5 no aparece en ningún sitio del
    # documento -- el motivo tiene que decir "6 de 7", nunca fabricar un
    # LOTE 5 vacío para completar la secuencia.
    expediente = _crear_expediente_con_documentos(
        db_session, "6.25/28510.0028", [("ADJUDICACION", fx.RESOLUCION_LOTES_CON_HUECO)],
    )
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(expediente)
    identificadores = {l.identificador_lote for l in db_session.query(Lote).filter_by(expediente_id=expediente.id)}
    assert identificadores == {"1", "2", "3", "4", "6", "7"}
    assert expediente.lotes_totales_declarados == 7
    assert "cobertura parcial: 6 de 7" in expediente.error


def test_expediente_0139_sin_nombre_proyecto_no_puede_identificar_su_lote(db_session):
    """El caso más peligroso de la sesión (encargo explícito del cliente):
    6.23/28510.0139 confirma "Nº de Lotes: 2" en su Anuncio PCSP y, desde la
    sesión de medición del alcance (2026-09-08), el propio documento SÍ trae
    el desglose por lote bajo "Nº Lote: NNN" (tercera variante multi-lote,
    `app.extraccion.lotes_pcsp`) -- pero sin `Expediente.nombre_proyecto`
    (la fuente independiente con la que se empareja el bloque propio de
    cada expediente, ver docstring del módulo) no hay con qué distinguir
    cuál de los dos bloques es el suyo, así que ninguno de los dos se usa:
    a revisión, nunca se adivina."""
    expediente = _crear_expediente_con_documentos(
        db_session, "6.23/28510.0139", [("ADJUDICACION", fx.ANUNCIO_PCSP_DOS_LOTES_SIN_DESGLOSE)],
    )
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(expediente)
    assert expediente.lotes_totales_declarados == 2
    assert expediente.estado == EstadoExpediente.pendiente_revision
    assert "no se pudo identificar con confianza" in expediente.error
    assert "Nº Lote: 001/002" in expediente.error
    # El motivo genérico de "cobertura parcial: 0 de 2" (pensado para cuando
    # no hay NINGÚN documento que desglose por lote) no debe aparecer
    # también -- sería falso aquí, el documento sí desglosa.
    assert "cobertura parcial" not in expediente.error


def test_expediente_0139_con_nombre_proyecto_toma_los_datos_de_su_propio_lote(db_session):
    """Contrapartida: con `nombre_proyecto` ya puesto (como lo deja el Excel
    de ejecución SAP antes de que corra esta extracción, caso real), el
    expediente toma el importe de licitación, el de adjudicación y el
    adjudicatario de SU bloque -- no la cabecera global del documento ni el
    primer bloque. Objeto real del Lote 1 (La Gineta) del propio PDF."""
    expediente = _crear_expediente_con_documentos(
        db_session, "6.23/28510.0139", [("ADJUDICACION", fx.ANUNCIO_PCSP_DOS_LOTES_SIN_DESGLOSE)],
    )
    expediente.nombre_proyecto = (
        "Suministro de balasto para las necesidades de obras y mantenimiento en la red ferroviaria de interés "
        "general (línea este). 2 lotes. Lote 1: Base de mantenimiento de La Gineta"
    )
    db_session.commit()
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(expediente)
    lote = db_session.query(Lote).filter_by(expediente_id=expediente.id).one()
    # Ni el total global del documento (590.256 + 1.291.698) ni el bloque
    # del OTRO lote (Almussafes, 1.291.698) -- el propio, La Gineta.
    assert lote.importe_licitacion == Decimal("590256")
    assert lote.importe_adjudicacion == Decimal("590256")
    assert lote.adjudicatario == "UTE SUMINISTRO LA GINETA"
    assert expediente.lotes_totales_declarados == 2
    assert "cobertura parcial" not in (expediente.error or "")


def test_expediente_0139_sin_nombre_proyecto_borra_un_adjudicatario_rancio(db_session):
    """`INVALIDADO` (app.extraccion.invalidado): el caso real que motivó
    este símbolo. Un `lote.adjudicatario` ya guardado de una pasada anterior
    (la extracción vieja, antes de esta sesión, que copiaba a ciegas el
    primer bloque del documento) no debe sobrevivir cuando esta pasada
    determina explícitamente que no se puede atribuir con confianza -- a
    diferencia de "no encontré nada" (`None`), que sí lo habría dejado tal
    cual."""
    expediente = _crear_expediente_con_documentos(
        db_session, "6.23/28510.0139", [("ADJUDICACION", fx.ANUNCIO_PCSP_DOS_LOTES_SIN_DESGLOSE)],
    )
    lote_previo = Lote(
        expediente_id=expediente.id, identificador_lote=LOTE_UNICO, adjudicatario="UTE SUMINISTRO LA GINETA",
    )
    db_session.add(lote_previo)
    db_session.commit()
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    lote = db_session.query(Lote).filter_by(expediente_id=expediente.id).one()
    assert lote.adjudicatario is None


def test_reprocesar_expediente_con_sentinela_previo_lo_sustituye(db_session):
    """Idempotencia (CONTEXTO.md sección 9.9) al migrar al arreglo de
    identidad de lote: un expediente que ya tenía el lote implícito único
    (de antes de esta sesión) con líneas de catálogo colgando de él no debe
    dejarlas conviviendo con los datos correctos una vez que se reprocesa y
    se detecta que en realidad es multi-lote.

    Bloque 4, sesión 2026-09-12 (continuación): desde que
    `_eliminar_lote_sentinela_obsoleto` deja de borrar el lote cuando esta
    pasada vuelve a declarar el identificador "1" de verdad (mismo texto que
    `LOTE_UNICO`, verificado contra 11 expedientes reales donde borraba y
    recreaba el mismo lote -- con un `id` nuevo -- en cada reproceso sin que
    ningún dato cambiara), la línea de basura ya no se limpia por ahí: la
    limpia `podar_lineas_obsoletas_de_documento` (mecanismo general, sesión
    2026-09-10), acotado a `(expediente_id, documento_id)` -- por eso la
    línea de basura de este test necesita un `documento_origen_id` real
    (antes no hacía falta, la borraba el camino del sentinela)."""
    expediente = _crear_expediente_con_documentos(
        db_session, "6.24/28510.0088",
        [("ADJUDICACION", fx.PROPUESTA_LC27_UTE), ("ANEJO", fx.ANEJO_PRECIOS_TRAVIESAS)],
    )
    documento_anejo = (
        db_session.query(Documento).filter_by(hash="hash-6.24/28510.0088-ANEJO").one()
    )
    lote_sentinela = Lote(expediente_id=expediente.id, identificador_lote=LOTE_UNICO, baja_lote=Decimal("0.9999"))
    db_session.add(lote_sentinela)
    db_session.commit()
    db_session.add(LineaCatalogo(
        expediente_id=expediente.id, lote_id=lote_sentinela.id, documento_origen_id=documento_anejo.id,
        clave_linea="basura", orden_aparicion=0, codigo_precio="P-999", descripcion="basura del sentinela",
    ))
    db_session.commit()

    trabajo = SimpleNamespace(expediente_id=expediente.id)
    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(expediente)
    lotes = db_session.query(Lote).filter_by(expediente_id=expediente.id).all()
    assert [l.identificador_lote for l in lotes] == ["1"]
    # El valor de baja del sentinela (0,9999) no sobrevive: la fila se
    # sustituyó por la correcta, no se actualizó encima de la basura.
    assert lotes[0].baja_lote == Decimal("0.0050")
    assert lotes[0].codigo_expediente_lote == "6.24/28510.0113"
    assert db_session.query(LineaCatalogo).filter_by(codigo_precio="P-999").first() is None


def test_reprocesar_dos_veces_un_lote_real_llamado_uno_no_cambia_su_id(db_session):
    """Bloque 4, sesión 2026-09-12 (continuación, verificación de
    determinismo): caso real, `6.23/28510.0051` (título "2 LOTES", su único
    lote real declarado se llama "1", el mismo texto que `LOTE_UNICO`) --
    verificado reprocesando el corpus completo dos veces seguidas que el
    `id` de `Lote` y de cada `LineaCatalogo` que cuelga de él cambiaba entre
    pasadas sin que ningún dato cambiara, porque `_eliminar_lote_sentinela_
    obsoleto` confundía el lote real "1" con el sentinela de migración del
    mismo nombre y lo borraba y recreaba en cada pasada. Reprocesar dos
    veces seguidas el mismo expediente (sin ningún sentinela previo, el
    caso normal) debe conservar el mismo `Lote.id`."""
    expediente = _crear_expediente_con_documentos(
        db_session, "6.24/28510.0088",
        [("ADJUDICACION", fx.PROPUESTA_LC27_UTE), ("ANEJO", fx.ANEJO_PRECIOS_TRAVIESAS)],
    )
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)
    lote_id_primera_pasada = db_session.query(Lote).filter_by(expediente_id=expediente.id).one().id
    linea_ids_primera_pasada = sorted(
        l.id for l in db_session.query(LineaCatalogo).filter_by(expediente_id=expediente.id).all()
    )

    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)
    lote_id_segunda_pasada = db_session.query(Lote).filter_by(expediente_id=expediente.id).one().id
    linea_ids_segunda_pasada = sorted(
        l.id for l in db_session.query(LineaCatalogo).filter_by(expediente_id=expediente.id).all()
    )

    assert lote_id_primera_pasada == lote_id_segunda_pasada
    assert linea_ids_primera_pasada == linea_ids_segunda_pasada


def test_codigo_principal_declarado_nunca_se_confunde_con_matriz(db_session):
    """Trampa de vocabulario verificada en 6.24/28510.0094 ("Nº EXPEDIENTE
    MATRIZ" sin relación con acuerdo marco, CONTEXTO.md sección 27): procesar
    este expediente no debe dejar `codigo_matriz` relleno con el valor que
    el documento llama "matriz" (que aquí es simplemente su propio
    expediente principal, el mismo código bajo el que ya está archivado) --
    eso reintroduciría el bug de autorreferencia de las secciones 20/21."""
    expediente = _crear_expediente_con_documentos(
        db_session, "6.24/28510.0094", [("ADJUDICACION", fx.PROPUESTA_LC27_NUMERADA_CON_ETIQUETA_MATRIZ)],
    )
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(expediente)
    assert expediente.codigo_matriz is None
    lotes = {l.identificador_lote: l for l in db_session.query(Lote).filter_by(expediente_id=expediente.id)}
    assert set(lotes) == {"1", "2", "3"}
    assert lotes["1"].codigo_expediente_lote == "6.24/28510.0175"
    assert expediente.lotes_totales_declarados == 3


# --- Sesión 2026-09-14 (continuación): identidad de lote en expedientes hermanos


def _item(documento_id: int, tipo: TipoDocumento, paginas: list[PaginaTexto]) -> _Documento:
    return _Documento(documento=SimpleNamespace(id=documento_id), tipo=tipo, paginas=paginas)


def test_contratos_de_tornilleria_corrigen_la_identidad_de_los_dos_lotes():
    """Caso del cliente: la única Resolución de tornillería es la del LOTE 2,
    con la errata "LOTE 1: ... 6.21/28510.0016" en el RESUELVE. Antes, los
    dos lotes quedaban ligados a 0016 y el LOTE 1 se llevaba la baja y el
    importe del LOTE 2. Con los Contratos: LOTE 1 = 0015 (su baja, 0,00 %,
    sale de su Contrato), LOTE 2 = 0016 con los datos de la Resolución."""
    from tests.extraccion.test_lotes import (
        _CABECERA_CONTRATO_TORNILLERIA_LOTE1, _CABECERA_CONTRATO_TORNILLERIA_LOTE2,
    )
    resultado = _extraer_lotes_declarados_del_expediente([
        _item(1, TipoDocumento.resolucion_adjudicacion, extraer_texto(fx.RESOLUCION_LOTE2_ERRATA_LOTE1_0016)),
        _item(2, TipoDocumento.contrato, [PaginaTexto(numero=1, texto=_CABECERA_CONTRATO_TORNILLERIA_LOTE2)]),
        _item(3, TipoDocumento.contrato, [PaginaTexto(numero=1, texto=_CABECERA_CONTRATO_TORNILLERIA_LOTE1)]),
    ])
    lotes = {l.identificador: l for l in resultado.lotes}
    assert set(lotes) == {"1", "2"}
    assert lotes["1"].codigo_expediente_lote == "6.21/28510.0015"
    assert lotes["1"].baja == Decimal("0.0000")
    assert lotes["1"].documento_id == 3  # la baja la declara su Contrato
    assert lotes["1"].importe_adjudicacion is None
    assert lotes["2"].codigo_expediente_lote == "6.21/28510.0016"
    assert lotes["2"].importe_adjudicacion == Decimal("15000.00")
    assert not resultado.motivos_por_lote


def test_contrato_contradice_la_baja_que_la_adjudicacion_da_a_su_lote():
    """6.22/28510.0033: la Resolución del LOTE 2 copia en su RESUELVE "LOTE
    1 ... 6.22/28510.0057" con la empresa y la baja del LOTE 2 (0,50 %). El
    Contrato de 0057 (LOTE 1) declara 10,50 %: gana el Contrato, el
    adjudicatario de ese bloque no se atribuye al LOTE 1, y queda motivo."""
    resultado = _extraer_lotes_declarados_del_expediente([
        _item(1, TipoDocumento.resolucion_adjudicacion, extraer_texto(fx.RESOLUCION_REFERENCIA_CRUZADA_0058)),
        _item(2, TipoDocumento.contrato, extraer_texto(fx.CONTRATO_LOTE2_0058)),
        _item(3, TipoDocumento.contrato, extraer_texto(fx.CONTRATO_LOTE1_0057)),
    ])
    lotes = {l.identificador: l for l in resultado.lotes}
    assert lotes["1"].codigo_expediente_lote == "6.22/28510.0057"
    assert lotes["1"].baja == Decimal("0.1050")
    assert lotes["1"].adjudicatario is None
    assert lotes["2"].codigo_expediente_lote == "6.22/28510.0058"
    assert lotes["2"].baja == Decimal("0.0050")
    assert set(resultado.motivos_por_lote) == {"1"}
    assert "baja del 0,50 % y su Contrato (6.22/28510.0057) declara 10,50 %" in resultado.motivos_por_lote["1"]


def test_el_contrato_completa_el_importe_que_la_adjudicacion_no_da_a_su_lote():
    """Sesión 2026-09-15: `6.22/28510.0058` (LOTE 2) se quedaba sin importe --
    el único bloque de la Resolución que lo traía es el RESUELVE con la
    errata, que ya no se atribuye a ningún lote. Su Contrato lo declara, y el
    de `0057` el suyo; los dos quedan trazados a la página del Contrato."""
    resultado = _extraer_lotes_declarados_del_expediente([
        _item(1, TipoDocumento.resolucion_adjudicacion, extraer_texto(fx.RESOLUCION_REFERENCIA_CRUZADA_0058)),
        _item(2, TipoDocumento.contrato, extraer_texto(fx.CONTRATO_LOTE2_0058_CON_IMPORTE)),
        _item(3, TipoDocumento.contrato, extraer_texto(fx.CONTRATO_LOTE1_0057_CON_IMPORTE)),
    ])
    lotes = {l.identificador: l for l in resultado.lotes}
    for identificador, documento_id in (("1", 3), ("2", 2)):
        assert lotes[identificador].importe_licitacion == Decimal("2400000.00")
        assert lotes[identificador].importe_adjudicacion == Decimal("2400000.00")
        assert {(c, d, a.pagina) for c, d, a in lotes[identificador].trazas_importe} == {
            ("importe_licitacion", documento_id, 2), ("importe_adjudicacion", documento_id, 2),
        }
    assert lotes["1"].baja == Decimal("0.1050")
    assert lotes["2"].baja == Decimal("0.0050")


def test_el_contrato_no_pisa_el_importe_que_ya_trae_la_adjudicacion():
    # Tornillería `6.21/28510.0016`: el LOTE 2 ya tiene 15.000,00 € de la
    # Resolución; aunque su Contrato declarase otro, no se toca.
    from app.extraccion.orquestador import _completar_importes_con_contrato
    from app.extraccion.campos_pcsp import CampoAnclado
    from app.extraccion.lotes import IdentidadContrato, LoteDeclarado

    declarado = LoteDeclarado(
        identificador="2", baja=None, importe_licitacion=None, importe_adjudicacion=Decimal("15000.00"),
        adjudicatario=None, codigo_expediente_lote="6.21/28510.0016", pagina=1, fragmento="",
    )
    identidad = IdentidadContrato(
        identificador="2", codigo_expediente_lote="6.21/28510.0016", baja=None, pagina=1, fragmento="",
        importe_adjudicacion=CampoAnclado(valor="99.000,00", pagina=2, fragmento="Base imponible 99.000,00 €"),
    )
    completado = _completar_importes_con_contrato(declarado, identidad, 7)
    assert completado.importe_adjudicacion == Decimal("15000.00")
    assert completado.trazas_importe == ()


def _crear_familia_0122(db_session, codigo_expediente: str):
    return _crear_expediente_con_documentos(
        db_session, codigo_expediente,
        [
            ("ADJUDICACION", fx.PROPUESTA_REFERENCIA_CRUZADA_0156),
            ("CONTRATO_1", fx.CONTRATO_LOTE2_0156),
            ("CONTRATO_2", fx.CONTRATO_LOTE1_0155),
            ("ANEJO", fx.ANEJO_HERENCIA_LOTE_0156),
        ],
    )


def test_expediente_de_lote_solo_guarda_su_propio_lote(db_session):
    """6.22/28510.0155 es el LOTE 1 de la licitación 6.22/28510.0122 (lo dice
    su Contrato) y comparte todos los documentos con el LOTE 2 (0156): antes
    mostraba los dos lotes, con sus líneas, y el LOTE 1 con el código y la
    baja del LOTE 2. Ahora solo su lote, con su código y su baja (24,90 %,
    de su Contrato), y solo las líneas de las tablas del LOTE 1 del anejo
    (p.1-3 del fixture)."""
    expediente = _crear_familia_0122(db_session, "6.22/28510.0155")
    _registrar_expediente(db_session, "6.22/28510.0156")  # el hermano está en el catálogo
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    resultado = ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(expediente)
    lotes = db_session.query(Lote).filter_by(expediente_id=expediente.id).all()
    assert [(l.identificador_lote, l.codigo_expediente_lote, l.baja_lote) for l in lotes] == [
        ("1", "6.22/28510.0155", Decimal("0.2490")),
    ]
    lineas = db_session.query(LineaCatalogo).filter_by(expediente_id=expediente.id).all()
    assert lineas
    assert {l.lote_id for l in lineas} == {lotes[0].id}
    assert {l.pagina for l in lineas} <= {1, 2, 3}
    assert resultado["lineas_de_lotes_hermanos"] > 0
    assert expediente.baja_global == Decimal("0.2490")
    assert "cobertura parcial" not in (expediente.error or "")


def test_expediente_principal_conserva_todos_los_lotes(db_session):
    # El expediente que agrupa la licitación (su código no es el de ningún
    # lote) sigue guardando los dos lotes, ya con la identidad corregida.
    expediente = _crear_familia_0122(db_session, "6.22/28510.0122")
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    resultado = ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    lotes = {l.identificador_lote: l for l in db_session.query(Lote).filter_by(expediente_id=expediente.id)}
    assert set(lotes) == {"1", "2"}
    assert lotes["1"].codigo_expediente_lote == "6.22/28510.0155"
    assert lotes["2"].codigo_expediente_lote == "6.22/28510.0156"
    assert resultado["lineas_de_lotes_hermanos"] == 0
    paginas_por_lote = {
        identificador: {
            l.pagina for l in db_session.query(LineaCatalogo).filter_by(lote_id=lote.id)
        }
        for identificador, lote in lotes.items()
    }
    assert paginas_por_lote["1"] <= {1, 2, 3} and paginas_por_lote["1"]
    assert paginas_por_lote["2"] <= {4, 5} and paginas_por_lote["2"]


def test_reprocesar_expediente_de_lote_borra_los_lotes_de_hermanos_de_antes(db_session):
    """Idempotencia: lo que una pasada anterior guardó en el expediente como
    lote del hermano (con sus líneas) desaparece al reprocesar."""
    expediente = _crear_familia_0122(db_session, "6.22/28510.0156")
    _registrar_expediente(db_session, "6.22/28510.0155")
    lote_viejo = Lote(expediente_id=expediente.id, identificador_lote="1", codigo_expediente_lote="6.22/28510.0156")
    db_session.add(lote_viejo)
    db_session.commit()
    db_session.add(LineaCatalogo(
        expediente_id=expediente.id, lote_id=lote_viejo.id, clave_linea="vieja", orden_aparicion=0,
        codigo_precio="P-999", descripcion="línea del lote hermano guardada por una pasada anterior",
    ))
    db_session.commit()
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    lotes = db_session.query(Lote).filter_by(expediente_id=expediente.id).all()
    assert [(l.identificador_lote, l.codigo_expediente_lote) for l in lotes] == [("2", "6.22/28510.0156")]
    assert db_session.query(LineaCatalogo).filter_by(codigo_precio="P-999").first() is None
    paginas = {l.pagina for l in db_session.query(LineaCatalogo).filter_by(expediente_id=expediente.id)}
    assert paginas and paginas <= {4, 5}


# --- Sesión 2026-09-14, tercera parte: el lote que solo nombra su Contrato, y
# el expediente de lote que se queda con las tablas sin cabecera


def test_lote_que_solo_nombra_su_contrato_se_registra():
    """`6.23/28510.0051`: su Propuesta solo nombra el LOTE 1 (`0060`); sus
    dos Contratos dicen LOTE 1 -> `0060` y LOTE 2 -> `0061`. Antes el LOTE 2
    no se registraba y el principal mostraba sus líneas como del LOTE 1."""
    resultado = _extraer_lotes_declarados_del_expediente([
        _item(1, TipoDocumento.propuesta_lc27, extraer_texto(fx.PROPUESTA_SOLO_LOTE1_0051)),
        _item(2, TipoDocumento.contrato, extraer_texto(fx.CONTRATO_LOTE1_0060)),
        _item(3, TipoDocumento.contrato, extraer_texto(fx.CONTRATO_LOTE2_0061)),
    ])
    lotes = {l.identificador: l for l in resultado.lotes}
    assert set(lotes) == {"1", "2"}
    assert (lotes["1"].codigo_expediente_lote, lotes["1"].baja) == ("6.23/28510.0060", Decimal("0.2531"))
    assert (lotes["2"].codigo_expediente_lote, lotes["2"].baja) == ("6.23/28510.0061", Decimal("0.2510"))
    assert lotes["2"].documento_id == 3
    assert _lote_propio(SimpleNamespace(codigo_expediente="6.23/28510.0051"), resultado.lotes) is None
    assert _lote_propio(SimpleNamespace(codigo_expediente="6.23/28510.0060"), resultado.lotes) == "1"
    assert _lote_propio(SimpleNamespace(codigo_expediente="6.23/28510.0061"), resultado.lotes) == "2"


def _registrar_expediente(db_session, codigo_expediente: str) -> None:
    db_session.add(Expediente(codigo_expediente=codigo_expediente))
    db_session.commit()


def _crear_familia_0112(db_session):
    return _crear_expediente_con_documentos(
        db_session, "6.21/28510.0112",
        [("CONTRATO_1", fx.CONTRATO_LOTE5_0113), ("CONTRATO_2", fx.CONTRATO_LOTE4_0112), ("ANEJO", fx.ANEJO_LOTE4_0112)],
    )


def _crear_familia_0051(db_session, codigo_expediente: str):
    return _crear_expediente_con_documentos(
        db_session, codigo_expediente,
        [
            ("ADJUDICACION", fx.PROPUESTA_SOLO_LOTE1_0051),
            ("CONTRATO_1", fx.CONTRATO_LOTE1_0060),
            ("CONTRATO_2", fx.CONTRATO_LOTE2_0061),
            ("ANEJO", fx.ANEJO_LOTES_Y_CRITERIOS_0051),
        ],
    )


def test_expediente_de_lote_cuyo_unico_documento_de_lotes_es_el_del_hermano(db_session):
    """`0061` (LOTE 2) comparte con su principal una Propuesta que solo
    nombra el LOTE 1: su propio lote sale de su Contrato. Del anejo se queda
    con la tabla del LOTE 2 (p.2 del fixture); la del LOTE 1 es de su
    hermano, y el anejo de criterios (p.3-4) no es de ningún lote."""
    expediente = _crear_familia_0051(db_session, "6.23/28510.0061")
    _registrar_expediente(db_session, "6.23/28510.0060")
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    resultado = ejecutar_extraccion_expediente(
        db_session, _StorageDirecta(), trabajo, model_provider=ProveedorModeloCabeceraPorContenido()
    )

    lotes = db_session.query(Lote).filter_by(expediente_id=expediente.id).all()
    assert [(l.identificador_lote, l.codigo_expediente_lote, l.baja_lote) for l in lotes] == [
        ("2", "6.23/28510.0061", Decimal("0.2510")),
    ]
    lineas = db_session.query(LineaCatalogo).filter_by(expediente_id=expediente.id).all()
    assert {l.pagina for l in lineas if l.lote_id == lotes[0].id} == {2}
    assert {l.pagina for l in lineas if l.lote_id is None} == {3, 4}
    assert resultado["lineas_de_lotes_hermanos"] > 0


def test_principal_registra_el_lote_de_su_segundo_contrato(db_session):
    expediente = _crear_familia_0051(db_session, "6.23/28510.0051")
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    ejecutar_extraccion_expediente(
        db_session, _StorageDirecta(), trabajo, model_provider=ProveedorModeloCabeceraPorContenido()
    )

    lotes = {l.identificador_lote: l for l in db_session.query(Lote).filter_by(expediente_id=expediente.id)}
    assert {k: l.codigo_expediente_lote for k, l in lotes.items()} == {"1": "6.23/28510.0060", "2": "6.23/28510.0061"}
    paginas = {
        k: {l.pagina for l in db_session.query(LineaCatalogo).filter_by(lote_id=lote.id)} for k, lote in lotes.items()
    }
    assert paginas["1"] and paginas["1"] <= {1, 2}
    assert paginas["2"] == {2}
    huerfanas = db_session.query(LineaCatalogo).filter_by(expediente_id=expediente.id, lote_id=None).all()
    assert {l.pagina for l in huerfanas} == {3, 4}


def test_expediente_de_lote_sin_documento_de_lotes_toma_su_lote_del_contrato(db_session):
    """`6.21/28510.0112` (LOTE 4) no tiene ningún documento de lotes: antes
    guardaba en su lote implícito "1" las tablas de todos los lotes del
    anejo que comparte con sus hermanos. Ahora su lote es el LOTE 4 de su
    Contrato (18,30 %), con su código; se queda con la tabla del LOTE 4 (p.3
    y su continuación p.4 del fixture); la del LOTE 5 es de `0113` (su
    Contrato también está archivado aquí); y la tabla sin cabecera de la
    p.2, que sigue al "Lote 1." de la p.1, no se le atribuye. El lote "1" de
    una pasada anterior, con sus líneas, desaparece."""
    expediente = _crear_familia_0112(db_session)
    _registrar_expediente(db_session, "6.21/28510.0113")
    viejo = Lote(expediente_id=expediente.id, identificador_lote="1")
    db_session.add(viejo)
    db_session.commit()
    db_session.add(LineaCatalogo(
        expediente_id=expediente.id, lote_id=viejo.id, clave_linea="vieja", orden_aparicion=0,
        codigo_precio="P-999", descripcion="línea del lote implícito de una pasada anterior",
    ))
    db_session.commit()
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    resultado = ejecutar_extraccion_expediente(
        db_session, _StorageDirecta(), trabajo, model_provider=ProveedorModeloCabeceraPorContenido()
    )

    lotes = db_session.query(Lote).filter_by(expediente_id=expediente.id).all()
    assert [(l.identificador_lote, l.codigo_expediente_lote, l.baja_lote) for l in lotes] == [
        ("4", "6.21/28510.0112", Decimal("0.1830")),
    ]
    lineas = db_session.query(LineaCatalogo).filter_by(expediente_id=expediente.id).all()
    propias = [l for l in lineas if l.lote_id == lotes[0].id]
    # p.5 del fixture (p.49 del original) empieza con el final de la tabla
    # del LOTE 4, antes del "Lote 5.": esas líneas heredan el LOTE 4.
    assert {l.pagina for l in propias} == {3, 4, 5}
    assert all(l.lote_heredado_de_pagina_anterior for l in propias if l.pagina != 3)
    assert not any(l.lote_del_expediente for l in propias)  # todas bajo su cabecera "Lote 4."
    sin_lote = [l for l in lineas if l.lote_id is None]
    assert {l.pagina for l in sin_lote} == {2}
    assert all("la última mención de lote antes de ella es la del LOTE 1" in l.motivo_revision for l in sin_lote)
    assert resultado["lineas_de_lotes_hermanos"] > 0
    assert db_session.query(LineaCatalogo).filter_by(codigo_precio="P-999").first() is None

    ids = sorted(l.id for l in lineas)
    ejecutar_extraccion_expediente(
        db_session, _StorageDirecta(), trabajo, model_provider=ProveedorModeloCabeceraPorContenido()
    )
    assert sorted(l.id for l in db_session.query(LineaCatalogo).filter_by(expediente_id=expediente.id)) == ids


def test_lineas_de_un_hermano_que_no_esta_en_el_catalogo_se_conservan_sin_lote(db_session):
    """Misma sesión: descartar las líneas de un lote hermano solo es no
    perder nada si están en el expediente del hermano. `6.21/28510.0066`
    (LOTE 2) guarda el Contrato del LOTE 1 (`0065`, fuera del catálogo) con
    su listado: descartarlo lo borraba de todas partes. Si el hermano no está,
    sus líneas se quedan en este expediente, sin lote y con el motivo."""
    expediente = _crear_familia_0112(db_session)  # sin registrar `0113`
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    resultado = ejecutar_extraccion_expediente(
        db_session, _StorageDirecta(), trabajo, model_provider=ProveedorModeloCabeceraPorContenido()
    )

    assert resultado["lineas_de_lotes_hermanos"] == 0
    del_hermano = [
        l for l in db_session.query(LineaCatalogo).filter_by(expediente_id=expediente.id, lote_id=None)
        if "LOTE 5 (6.21/28510.0113), otro lote de la licitación cuyo expediente no está en el catálogo"
        in (l.motivo_revision or "")
    ]
    assert del_hermano and {l.pagina for l in del_hermano} == {5}
    assert all("@p" in l.clave_linea for l in del_hermano)


# --- CONTEXTO.md sección 26: criterios de alcance del cliente ----------------


def test_detectar_contrato_obra_marca_tipo_contrato_obras():
    # Sin fixture PDF real con "Tipo de Contrato Obras" (ningún expediente
    # de este corpus lo es, CONTEXTO.md sección 26) -- se prueba a nivel del
    # helper, con `_Documento` sintético, igual que ya hace `docstring`.
    paginas = [PaginaTexto(numero=1, texto="Tipo de Contrato Obras\n")]
    doc = SimpleNamespace(id=1, nombre_archivo="anuncio.pdf")
    item = _Documento(documento=doc, tipo=TipoDocumento.anuncio_pcsp, paginas=paginas)
    campo = _detectar_contrato_obra([item])
    assert campo is not None
    assert campo.valor == "Obras"


def test_detectar_contrato_obra_ignora_suministros():
    paginas = [PaginaTexto(numero=1, texto="Tipo de Contrato Suministros\n")]
    doc = SimpleNamespace(id=1, nombre_archivo="anuncio.pdf")
    item = _Documento(documento=doc, tipo=TipoDocumento.anuncio_pcsp, paginas=paginas)
    assert _detectar_contrato_obra([item]) is None


def _doc_pcsp_global_sin_desglose(doc_id: int) -> _Documento:
    """Caso real que verificó el reproceso de `6.20/28510.0041`: el CONTRATO
    de un lote concreto puede seguir declarando el presupuesto GLOBAL de
    toda la licitación en su propia cabecera, sin repetir "Nº Lote: NNN" en
    ningún sitio -- `extraer_ventanas_multi_lote_pcsp` no lo detecta como
    multi-lote (no hay nada que detectar), así que sigue el camino de
    siempre: el importe de licitación que trae es el global, no el de este
    lote. La adjudicación, sin embargo, sí es la real de este lote (coincide
    con la de la ventana resuelta abajo) -- exactamente la mezcla real
    encontrada."""
    paginas = [
        PaginaTexto(
            numero=1,
            texto=(
                "Número de Expediente 6.20/28510.0041\n"
                "Presupuesto base de licitación\n"
                "Importe 26.620.000 EUR.\n"
                "Importe (sin impuestos) 22.000.000 EUR.\n"
                "Adjudicatario\n"
                "GLOBAL SA\n"
                "Importes de Adjudicación\n"
                "Importe total ofertado (sin impuestos) 500.000 EUR.\n"
            ),
        )
    ]
    doc = SimpleNamespace(id=doc_id, nombre_archivo="contrato.pdf")
    return _Documento(documento=doc, tipo=TipoDocumento.anuncio_pcsp, paginas=paginas)


def _doc_pcsp_multi_lote_resuelto(doc_id: int) -> _Documento:
    """El Anuncio de adjudicación real, con "Nº Lote: NNN" repetido -- el
    bloque del lote 2 (el que coincidirá con `nombre_proyecto`) trae el
    importe de licitación REAL de ese lote (500.000, no el global)."""
    paginas = [
        PaginaTexto(
            numero=1,
            texto=(
                "Nº Lote: 001\n"
                "Objeto del Contrato: Suministro de repuestos. Lote 1: Otro sitio\n"
                "Presupuesto base de licitación\n"
                "Importe 121.000 EUR.\n"
                "Importe (sin impuestos) 100.000 EUR.\n"
                "Adjudicatario\n"
                "OTRO SA\n"
                "Importes de Adjudicación\n"
                "Importe total ofertado (sin impuestos) 100.000 EUR.\n"
                "Nº Lote: 002\n"
                "Objeto del Contrato: Suministro de repuestos. Lote 2: Mi sitio\n"
                "Presupuesto base de licitación\n"
                "Importe 605.000 EUR.\n"
                "Importe (sin impuestos) 500.000 EUR.\n"
                "Adjudicatario\n"
                "LOTE DOS SA\n"
                "Importes de Adjudicación\n"
                "Importe total ofertado (sin impuestos) 500.000 EUR.\n"
            ),
        )
    ]
    doc = SimpleNamespace(id=doc_id, nombre_archivo="adjudicacion.pdf")
    return _Documento(documento=doc, tipo=TipoDocumento.anuncio_pcsp, paginas=paginas)


def test_importe_resuelto_por_lote_gana_al_global_sin_importar_el_orden(db_session):
    # Hallazgo real verificando el reproceso de `6.20/28510.0041`: "el
    # primer valor no nulo gana" dejaba fijo el importe de licitación
    # GLOBAL si ese documento se procesaba antes que el que sí resuelve el
    # bloque de este lote -- probado en los dos órdenes posibles.
    for orden, docs in enumerate([
        [_doc_pcsp_global_sin_desglose(1), _doc_pcsp_multi_lote_resuelto(2)],
        [_doc_pcsp_multi_lote_resuelto(1), _doc_pcsp_global_sin_desglose(2)],
    ]):
        expediente = Expediente(
            codigo_expediente=f"6.20/28510.004{orden}",
            nombre_proyecto="Suministro de repuestos. Lote 2: Mi sitio",
        )
        db_session.add(expediente)
        db_session.commit()

        importe_licitacion, importe_adjudicacion, _baja, adjudicatario, _motivo, _detectado = (
            _extraer_campos_expediente(db_session, expediente, docs)
        )

        assert importe_licitacion == Decimal("500000"), f"orden {orden}"
        assert importe_adjudicacion == Decimal("500000"), f"orden {orden}"
        assert adjudicatario == "LOTE DOS SA", f"orden {orden}"


def _doc_contrato_con_baja(doc_id: int, codigo_propio: str, baja_pct: str, adjudicatario: str) -> _Documento:
    """Caso real, sesión de medición del alcance parte 2: dos CONTRATOs
    distintos (uno por lote real), cada uno vinculado a VARIOS expedientes
    hermanos (6.23/28510.0139 y sus dos pedidos), cada uno declarando sin
    ambigüedad su propio "Contrato nº" y una baja distinta."""
    paginas = [
        PaginaTexto(
            numero=1,
            texto=(
                f"OBJETO DEL CONTRATO\nContrato nº: {codigo_propio}\n"
                f"ADJUDICATARIO: {adjudicatario}\n"
                f"La baja económica ofertada del {baja_pct}% será aplicable a todos los precios unitarios.\n"
            ),
        )
    ]
    doc = SimpleNamespace(id=doc_id, nombre_archivo="contrato.pdf")
    return _Documento(documento=doc, tipo=TipoDocumento.contrato, paginas=paginas)


def test_baja_declarada_en_documento_compartido_se_atribuye_por_contrato_no(db_session):
    # Caso real: 6.24/28510.0017 (Contrato nº propio, baja 5,07 %) y
    # 6.24/28510.0018 (Contrato nº propio, baja 0,40 %) -- los DOS
    # documentos están vinculados a los dos expedientes (comparten
    # DocumentoExpediente), pero cada uno solo debe tomar SU propia baja.
    docs = [
        _doc_contrato_con_baja(1, "6.24/28510.0017", "5,07", "UTE SUMINISTRO LA GINETA"),
        _doc_contrato_con_baja(2, "6.24/28510.0018", "0,40", "PORFIDOS DEL MEDITERRANEO S A"),
    ]

    expediente_17 = Expediente(codigo_expediente="6.24/28510.0017")
    db_session.add(expediente_17)
    db_session.commit()
    _, _, baja_17, _, motivo_17, _ = _extraer_campos_expediente(db_session, expediente_17, docs)
    assert baja_17.baja == Decimal("0.0507")
    assert motivo_17 is None

    expediente_18 = Expediente(codigo_expediente="6.24/28510.0018")
    db_session.add(expediente_18)
    db_session.commit()
    _, _, baja_18, _, motivo_18, _ = _extraer_campos_expediente(db_session, expediente_18, docs)
    assert baja_18.baja == Decimal("0.0040")
    assert motivo_18 is None


def test_baja_declarada_en_documento_compartido_sin_confirmacion_propia_se_invalida(db_session):
    # El expediente "padre" (6.23/28510.0139) también está vinculado a los
    # dos CONTRATOs, pero ninguno declara SU código -- ninguna de las dos
    # bajas es confirmadamente suya, así que ninguna se usa (`INVALIDADO`,
    # no una elegida a ciegas por prioridad de documento).
    docs = [
        _doc_contrato_con_baja(1, "6.24/28510.0017", "5,07", "UTE SUMINISTRO LA GINETA"),
        _doc_contrato_con_baja(2, "6.24/28510.0018", "0,40", "PORFIDOS DEL MEDITERRANEO S A"),
    ]
    expediente = Expediente(codigo_expediente="6.23/28510.0139")
    db_session.add(expediente)
    db_session.commit()

    _, _, baja, _, motivo, _ = _extraer_campos_expediente(db_session, expediente, docs)

    assert baja is INVALIDADO
    assert motivo is not None
    assert "documento(s) compartido(s) con expediente(s) hermano(s)" in motivo


def test_baja_declarada_sin_ningun_codigo_propio_sigue_como_siempre(db_session):
    # La inmensa mayoría del corpus: un CONTRATO propio de un único
    # expediente, sin "Contrato nº" en absoluto (o el mismo código que el
    # expediente) -- el mecanismo nuevo no debe cambiar nada aquí.
    docs = [_doc_contrato_con_baja(1, "6.24/28510.9999", "54,00", "PROVEEDOR SA")]
    expediente = Expediente(codigo_expediente="6.24/28510.9999")
    db_session.add(expediente)
    db_session.commit()

    _, _, baja, _, motivo, _ = _extraer_campos_expediente(db_session, expediente, docs)

    assert baja.baja == Decimal("0.5400")
    assert motivo is None


def test_detectar_documento_adjudicacion_no_relacionado_avisa_cuando_no_menciona_el_expediente():
    # Caso real, Bloque 4 (sesión de auditoría 2026-09-09): `6.24/28510.0216`
    # tiene un documento nombrado ADJUDICACION_...pdf, clasificado `otro`
    # (una plantilla no reconocida), cuyo texto menciona otros expedientes
    # reales pero nunca el propio -- quedaba `completado` sin ningún aviso.
    paginas = [PaginaTexto(
        numero=1,
        texto="ACUERDO DEL CONSEJO DE ADMINISTRACIÓN\nExpediente 3.22/27510.0135\nExpediente 3.22/27510.0133\n",
    )]
    doc = SimpleNamespace(id=1, ruta_almacenamiento="6.24_28510.0216/ADJUDICACION_2765fcc0730e7a73.pdf")
    item = _Documento(documento=doc, tipo=TipoDocumento.otro, paginas=paginas)
    aviso = _detectar_documento_adjudicacion_no_relacionado([item], "6.24/28510.0216", None)
    assert aviso is not None
    assert "ADJUDICACION_2765fcc0730e7a73.pdf" in aviso


def test_detectar_documento_adjudicacion_no_relacionado_no_avisa_si_menciona_el_propio_expediente():
    # Caso real, `6.22/28510.0126`: el mismo tipo de plantilla (boletín de
    # Consejo de Administración, varios contratos aprobados a la vez) SÍ
    # menciona el expediente propio -- documento genuinamente relevante,
    # solo de una plantilla que el clasificador todavía no reconoce. No debe
    # avisar.
    paginas = [PaginaTexto(
        numero=17,
        texto="LOTE 2 – SUR (EXPEDIENTE Nº 6.22/28510.0126)\n% BAJA 23,90%\n",
    )]
    doc = SimpleNamespace(id=1, ruta_almacenamiento="6.22_28510.0126/ADJUDICACION_5c030c40c37b1ba9.pdf")
    item = _Documento(documento=doc, tipo=TipoDocumento.otro, paginas=paginas)
    assert _detectar_documento_adjudicacion_no_relacionado([item], "6.22/28510.0126", None) is None


def test_detectar_documento_adjudicacion_no_relacionado_no_avisa_si_menciona_la_matriz():
    paginas = [PaginaTexto(numero=1, texto="Expediente matriz 6.20/28510.0001\n")]
    doc = SimpleNamespace(id=1, ruta_almacenamiento="ADJUDICACION_abc.pdf")
    item = _Documento(documento=doc, tipo=TipoDocumento.otro, paginas=paginas)
    assert _detectar_documento_adjudicacion_no_relacionado([item], "6.20/28510.0099", "6.20/28510.0001") is None


def test_detectar_documento_adjudicacion_no_relacionado_no_avisa_sin_ningun_codigo_legible():
    # Un documento sin ningún código de expediente reconocible (escaneado, o
    # una plantilla sin ese dato) no es evidencia de nada -- sería
    # indistinguible de un falso positivo de extracción.
    paginas = [PaginaTexto(numero=1, texto="Documento sin ningún código de expediente reconocible.\n")]
    doc = SimpleNamespace(id=1, ruta_almacenamiento="ADJUDICACION_abc.pdf")
    item = _Documento(documento=doc, tipo=TipoDocumento.otro, paginas=paginas)
    assert _detectar_documento_adjudicacion_no_relacionado([item], "6.20/28510.0099", None) is None


def test_detectar_documento_adjudicacion_no_relacionado_ignora_documentos_no_adjudicacion():
    # Un PLIEGO o ANEJO que por casualidad no mencione el propio expediente
    # no es sospechoso -- solo se comprueba el que el scraper etiquetó como
    # ADJUDICACION en el nombre de fichero.
    paginas = [PaginaTexto(numero=1, texto="Expediente 6.20/28510.0001\n")]
    doc = SimpleNamespace(id=1, ruta_almacenamiento="ANEJO_abc.pdf")
    item = _Documento(documento=doc, tipo=TipoDocumento.anejo, paginas=paginas)
    assert _detectar_documento_adjudicacion_no_relacionado([item], "6.20/28510.0099", None) is None


def test_detectar_contrato_obra_ignora_documentos_que_no_son_anuncio_pcsp():
    # El campo "Tipo de Contrato" también aparece en el "Documento de
    # Pliegos" (misma familia de formulario, CONTEXTO.md sección 3), pero solo
    # se mira en documentos ya clasificados como `anuncio_pcsp` -- no hace
    # falta más para el corpus real y evita depender de un tipo que además
    # puede saltarse por `es_pliego_sin_precios`.
    paginas = [PaginaTexto(numero=1, texto="Tipo de Contrato Obras\n")]
    doc = SimpleNamespace(id=1, nombre_archivo="documento_de_pliegos.pdf")
    item = _Documento(documento=doc, tipo=TipoDocumento.pliego, paginas=paginas)
    assert _detectar_contrato_obra([item]) is None


# --- Auditoría de ficheros huérfanos (2026-09-06): 6.23/28510.0135, 8 lotes
# reales, ningún Anuncio PCSP en el expediente -- el único documento con
# "Nº de Lotes: 8" es un "Documento de Pliegos", clasificado `pliego`. Antes
# de esta sesión, `_detectar_numero_lotes_pcsp` solo miraba
# `TipoDocumento.anuncio_pcsp`, así que la cobertura parcial (1 de 8) nunca
# se detectaba para este expediente -- se quedaba con el motivo genérico "no
# se extrajo ninguna línea de catálogo", que no explica que hay 7 lotes más
# sin ningún dato. ---


def test_detectar_numero_lotes_pcsp_lo_encuentra_en_documento_de_pliegos():
    paginas = [PaginaTexto(numero=1, texto="Número de Expediente 3.23/28510.0135\nNº de Lotes: 8\n")]
    doc = SimpleNamespace(id=1, nombre_archivo="documento_de_pliegos.pdf")
    item = _Documento(documento=doc, tipo=TipoDocumento.pliego, paginas=paginas, marcador="documento de pliegos")

    assert _detectar_numero_lotes_pcsp([item]) == 8


def test_detectar_numero_lotes_pcsp_ignora_pliego_de_clausulas_administrativas():
    # Un PCAP también es `TipoDocumento.pliego`, pero no comparte la anatomía
    # de etiquetas fijas del formulario PCSP -- de ahí que haga falta
    # comprobar el marcador exacto, no basta con el tipo.
    paginas = [PaginaTexto(numero=1, texto="Nº de Lotes: 8\n")]
    doc = SimpleNamespace(id=1, nombre_archivo="pcap.pdf")
    item = _Documento(
        documento=doc, tipo=TipoDocumento.pliego, paginas=paginas, marcador="pliego de clausulas administrativas"
    )

    assert _detectar_numero_lotes_pcsp([item]) is None


def test_sin_documento_de_lotes_el_contrato_propio_da_el_importe_de_su_lote(db_session):
    """Sesión 2026-09-15: `6.21/28510.0112` no tiene adjudicación; su lote
    (LOTE 4) sale de su Contrato, y ahora también su importe (710.000,00 €),
    trazado a la p.2 del Contrato."""
    expediente = _crear_expediente_con_documentos(
        db_session, "6.21/28510.0112",
        [("CONTRATO_1", fx.CONTRATO_LOTE5_0113), ("CONTRATO_2", fx.CONTRATO_LOTE4_0112_CON_IMPORTE)],
    )
    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), SimpleNamespace(expediente_id=expediente.id))

    lote = db_session.query(Lote).filter_by(expediente_id=expediente.id).one()
    assert (lote.identificador_lote, lote.importe_adjudicacion) == ("4", Decimal("710000.00"))
    db_session.refresh(expediente)
    assert expediente.importe_adjudicacion == Decimal("710000.00")
    traza = db_session.query(TrazaOrigen).filter_by(
        entidad_tipo="lote", entidad_id=lote.id, campo="importe_adjudicacion"
    ).one()
    assert traza.pagina == 2


# --- Bloque 2, sesión 2026-09-18 (tercera parte): los lotes que declara el
# --- propio cuadro de precios -------------------------------------------


class _LoteFalso:
    def __init__(self, identificador, baja=None, licitacion=None, adjudicacion=None):
        self.identificador_lote = identificador
        self.baja_lote = baja
        self.importe_licitacion = licitacion
        self.importe_adjudicacion = adjudicacion


class _ExpedienteFalso:
    def __init__(self, declarados, titulo=None):
        self.lotes_totales_declarados = declarados
        # Sesión 2026-09-19 (segunda parte): `_lotes_candidatos_del_cuadro`
        # mira el título para no confundir el sentinela "1" con un lote real
        # llamado "Lote 1" (ver su docstring). Sin título, no hay confusión
        # posible y el comportamiento es el de siempre.
        self.nombre_proyecto = titulo


class _ResultadoFalso:
    def __init__(self, identificadores):
        self.lineas = [{"identificador_lote": i} for i in identificadores]


def test_se_intenta_cuando_declara_n_lotes_y_no_conoce_ninguno():
    """`6.26/28510.0064`: declara 6 lotes, no tiene adjudicación que los
    desglose y su cuadro de precios trae las seis cabeceras "LOTE N"."""
    candidatos = _lotes_candidatos_del_cuadro(
        _ExpedienteFalso(6), [_LoteFalso(LOTE_UNICO)], lote_propio=None
    )
    assert candidatos == {"1": None, "2": None, "3": None, "4": None, "5": None, "6": None}


def test_no_se_intenta_con_un_solo_lote_declarado():
    assert _lotes_candidatos_del_cuadro(_ExpedienteFalso(1), [_LoteFalso(LOTE_UNICO)], None) is None
    assert _lotes_candidatos_del_cuadro(_ExpedienteFalso(None), [_LoteFalso(LOTE_UNICO)], None) is None


def test_no_se_intenta_si_ya_hay_lotes_identificados_por_numero():
    lotes = [_LoteFalso("1"), _LoteFalso("2")]
    assert _lotes_candidatos_del_cuadro(_ExpedienteFalso(2), lotes, None) is None


def test_no_se_intenta_si_el_expediente_es_uno_de_los_lotes():
    assert _lotes_candidatos_del_cuadro(_ExpedienteFalso(6), [_LoteFalso(LOTE_UNICO)], "3") is None


def test_no_se_parte_un_lote_que_ya_lleva_datos_atribuidos():
    """Partir en N un lote que ya tiene baja o importe convertiría un dato del
    conjunto de la licitación en un dato del lote 1."""
    from decimal import Decimal as _D

    con_baja = [_LoteFalso(LOTE_UNICO, baja=_D("0.10"))]
    con_licitacion = [_LoteFalso(LOTE_UNICO, licitacion=_D("1000"))]
    con_adjudicacion = [_LoteFalso(LOTE_UNICO, adjudicacion=_D("900"))]
    assert _lotes_candidatos_del_cuadro(_ExpedienteFalso(6), con_baja, None) is None
    assert _lotes_candidatos_del_cuadro(_ExpedienteFalso(6), con_licitacion, None) is None
    assert _lotes_candidatos_del_cuadro(_ExpedienteFalso(6), con_adjudicacion, None) is None


def test_el_intento_solo_vale_si_ninguna_fila_queda_huerfana():
    """La garantía que hace que esto no pueda quitar filas del entregable: una
    sola huérfana y se descarta el intento entero."""
    candidatos = {"1": None, "2": None}
    assert _el_cuadro_declara_todos_los_lotes(_ResultadoFalso(["1", "2", "1"]), candidatos) is True
    assert _el_cuadro_declara_todos_los_lotes(_ResultadoFalso(["1", None]), candidatos) is False


def test_el_intento_solo_vale_si_cubre_todos_los_lotes_declarados():
    candidatos = {"1": None, "2": None, "3": None}
    assert _el_cuadro_declara_todos_los_lotes(_ResultadoFalso(["1", "2"]), candidatos) is False
    assert _el_cuadro_declara_todos_los_lotes(_ResultadoFalso(["1", "2", "3"]), candidatos) is True
    assert _el_cuadro_declara_todos_los_lotes(_ResultadoFalso([]), candidatos) is False
