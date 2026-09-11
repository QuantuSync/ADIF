"""Bloque 1, sesión 2026-09-11: cola de candidatos de matrícula -- calcula
opciones, nunca asigna nada por su cuenta (CONTEXTO.md, análisis previo de
la sesión del maestro de materiales: "nunca una asignación automática, ni
siquiera para el 8,6% de coincidencia exacta")."""
from app.extraccion.candidatos_matricula import calcular_candidatos
from app.models import CandidatoMatricula, Expediente, LineaCatalogo, Lote, MaestroMaterial


def _expediente_y_lote(db, codigo="6.24/28510.0001"):
    expediente = Expediente(codigo_expediente=codigo)
    db.add(expediente)
    db.commit()
    lote = Lote(expediente_id=expediente.id, identificador_lote="1")
    db.add(lote)
    db.commit()
    return expediente, lote


def _linea(db, expediente_id, lote_id, descripcion, matricula=None, clave="P-1"):
    linea = LineaCatalogo(
        expediente_id=expediente_id, lote_id=lote_id, clave_linea=clave, orden_aparicion=0,
        descripcion=descripcion, matricula=matricula, precio_unitario=1,
    )
    db.add(linea)
    db.commit()
    return linea


def _maestro(db, matricula, descripcion):
    m = MaestroMaterial(matricula=matricula, descripcion=descripcion)
    db.add(m)
    db.commit()
    return m


def test_coincidencia_exacta_normalizada(db_session):
    expediente, lote = _expediente_y_lote(db_session)
    linea = _linea(db_session, expediente.id, lote.id, "BRIDA DE SUJECION TIPO A")
    _maestro(db_session, "612345678", "Brida de sujeción tipo A")

    resumen = calcular_candidatos(db_session)

    assert resumen.lineas_sin_matricula == 1
    assert resumen.lineas_con_candidato == 1
    assert resumen.lineas_sin_candidato == 0
    candidatos = db_session.query(CandidatoMatricula).filter_by(linea_catalogo_id=linea.id).all()
    assert len(candidatos) == 1
    assert candidatos[0].matricula_candidata == "612345678"
    assert candidatos[0].exacto is True
    assert float(candidatos[0].similitud) == 1.0


def test_alta_similitud_no_exacta(db_session):
    expediente, lote = _expediente_y_lote(db_session)
    linea = _linea(db_session, expediente.id, lote.id, "TORNILLO CABEZA HEXAGONAL M22X325 MM")
    _maestro(db_session, "612345678", "TORNILLO CABEZA HEXAGONAL M22X320 MM")

    resumen = calcular_candidatos(db_session)

    assert resumen.lineas_con_candidato == 1
    candidatos = db_session.query(CandidatoMatricula).filter_by(linea_catalogo_id=linea.id).all()
    assert len(candidatos) == 1
    assert candidatos[0].exacto is False
    assert float(candidatos[0].similitud) >= 0.85


def test_sin_parecido_razonable_no_da_candidato(db_session):
    expediente, lote = _expediente_y_lote(db_session)
    linea = _linea(db_session, expediente.id, lote.id, "Balasto sobre camión en cantera")
    _maestro(db_session, "612345678", "Brida de sujeción tipo A")

    resumen = calcular_candidatos(db_session)

    assert resumen.lineas_sin_candidato == 1
    assert resumen.lineas_con_candidato == 0
    assert db_session.query(CandidatoMatricula).filter_by(linea_catalogo_id=linea.id).count() == 0


def test_linea_con_matricula_no_entra_en_el_calculo(db_session):
    expediente, lote = _expediente_y_lote(db_session)
    _linea(db_session, expediente.id, lote.id, "BRIDA DE SUJECION TIPO A", matricula="612345678")
    _maestro(db_session, "612345678", "Brida de sujeción tipo A")

    resumen = calcular_candidatos(db_session)

    assert resumen.lineas_sin_matricula == 0
    assert resumen.candidatos_generados == 0


def test_denominacion_ambigua_da_varios_candidatos(db_session):
    # Caso real del análisis previo: 2.388 denominaciones del maestro (8,3%)
    # identifican más de una matrícula -- una coincidencia exacta de texto
    # con dos matrículas reales distintas debe ofrecer las dos, nunca elegir
    # una a ciegas.
    expediente, lote = _expediente_y_lote(db_session)
    linea = _linea(db_session, expediente.id, lote.id, "BRIDA DE SUJECION TIPO A")
    _maestro(db_session, "612345678", "Brida de sujeción tipo A")
    _maestro(db_session, "612345679", "Brida de sujeción tipo A")

    resumen = calcular_candidatos(db_session)

    assert resumen.lineas_con_candidato == 1
    candidatos = db_session.query(CandidatoMatricula).filter_by(linea_catalogo_id=linea.id).all()
    assert {c.matricula_candidata for c in candidatos} == {"612345678", "612345679"}
    assert all(c.exacto for c in candidatos)


def test_recalcular_no_duplica(db_session):
    expediente, lote = _expediente_y_lote(db_session)
    _linea(db_session, expediente.id, lote.id, "BRIDA DE SUJECION TIPO A")
    _maestro(db_session, "612345678", "Brida de sujeción tipo A")

    calcular_candidatos(db_session)
    resumen2 = calcular_candidatos(db_session)

    assert resumen2.candidatos_generados == 1
    assert db_session.query(CandidatoMatricula).count() == 1


def test_recalcular_retira_candidatos_de_linea_que_ya_gano_matricula(db_session):
    expediente, lote = _expediente_y_lote(db_session)
    linea = _linea(db_session, expediente.id, lote.id, "BRIDA DE SUJECION TIPO A")
    _maestro(db_session, "612345678", "Brida de sujeción tipo A")
    calcular_candidatos(db_session)
    assert db_session.query(CandidatoMatricula).count() == 1

    linea.matricula = "612345678"
    db_session.commit()
    resumen = calcular_candidatos(db_session)

    assert resumen.candidatos_generados == 0
    assert db_session.query(CandidatoMatricula).count() == 0


def test_maestro_sin_denominacion_se_ignora(db_session):
    expediente, lote = _expediente_y_lote(db_session)
    _linea(db_session, expediente.id, lote.id, "BRIDA DE SUJECION TIPO A")
    _maestro(db_session, "612345678", None)

    resumen = calcular_candidatos(db_session)

    assert resumen.lineas_sin_candidato == 1
