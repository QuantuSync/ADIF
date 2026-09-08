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
    _detectar_numero_lotes_pcsp,
    ejecutar_extraccion_expediente,
)
from app.extraccion.texto import PaginaTexto
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


def test_expediente_0139_sin_ningun_desglose_por_lote_marca_cobertura_cero(db_session):
    """El caso más peligroso de la sesión (encargo explícito del cliente):
    6.23/28510.0139 confirma "Nº de Lotes: 2" en su Anuncio PCSP pero no
    trae ninguna Propuesta LC.27 ni Resolución que desglose por lote --
    antes de esta sesión figuraba `completado` sin haber identificado ni un
    solo lote de los 2 que el propio documento confirma que existen."""
    expediente = _crear_expediente_con_documentos(
        db_session, "6.23/28510.0139", [("ADJUDICACION", fx.ANUNCIO_PCSP_DOS_LOTES_SIN_DESGLOSE)],
    )
    trabajo = SimpleNamespace(expediente_id=expediente.id)

    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(expediente)
    assert expediente.lotes_totales_declarados == 2
    assert expediente.estado == EstadoExpediente.pendiente_revision
    assert "cobertura parcial: 0 de 2" in expediente.error


def test_reprocesar_expediente_con_sentinela_previo_lo_sustituye(db_session):
    """Idempotencia (CONTEXTO.md sección 9.9) al migrar al arreglo de
    identidad de lote: un expediente que ya tenía el lote implícito único
    (de antes de esta sesión) con líneas de catálogo colgando de él no debe
    dejarlas conviviendo con los datos correctos una vez que se reprocesa y
    se detecta que en realidad es multi-lote."""
    expediente = _crear_expediente_con_documentos(
        db_session, "6.24/28510.0088",
        [("ADJUDICACION", fx.PROPUESTA_LC27_UTE), ("ANEJO", fx.ANEJO_PRECIOS_TRAVIESAS)],
    )
    lote_sentinela = Lote(expediente_id=expediente.id, identificador_lote=LOTE_UNICO, baja_lote=Decimal("0.9999"))
    db_session.add(lote_sentinela)
    db_session.commit()
    db_session.add(LineaCatalogo(
        expediente_id=expediente.id, lote_id=lote_sentinela.id,
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
