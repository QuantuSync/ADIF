"""Sesión 2026-09-21, bloque 2: el listado interno de ADIF de expedientes en
ejecución, con la fecha de firma del acta de inicio, y su columna en la hoja
"Conciliación"."""
from datetime import date, datetime, timezone

import pytest

from app import config
from app.conciliacion import EN_EJECUCION_SIN_FECHA, construir_conciliacion, describir_registro_publicado
from app.extraccion.en_ejecucion_adif import cargar_en_ejecucion_adif, elegir_fichero, leer_listado
from app.models import EstadoExpediente, Expediente, SindicacionExpediente

LISTADO = (
    "Nº Expediente;Firma acta de inicio\n"
    "6.26/28510.0073;24/08/2026\n"
    "6.25/28510.0265;\n"
    "6.25/28510.5001/01;26/03/2025\n"
    "4.25/27520.0191;01/06/2026\n"
    "6.24/28510.0008 ;22/07/2024\n"
)


@pytest.fixture(autouse=True)
def _departamento_28510(monkeypatch):
    monkeypatch.setattr(config.settings, "sindicacion_departamentos_adif", "28510")


def test_lee_el_listado_tal_como_lo_manda_adif():
    filas, no_legibles, sin_codigo = leer_listado(LISTADO.encode("utf-8"))
    assert [f.codigo_expediente for f in filas] == [
        "6.26/28510.0073", "6.25/28510.0265", "6.25/28510.5001/01", "4.25/27520.0191", "6.24/28510.0008",
    ]
    assert filas[0].acta_inicio == date(2026, 8, 24)
    assert filas[1].acta_inicio is None  # en blanco en el listado: no se inventa
    assert (no_legibles, sin_codigo) == ([], 0)


def test_tolera_windows_1252_y_otro_separador():
    contenido = "Nº Expediente,Firma acta de inicio\n6.26/28510.0073,24/08/2026\n".encode("cp1252")
    filas, _, _ = leer_listado(contenido)
    assert [(f.codigo_expediente, f.acta_inicio) for f in filas] == [("6.26/28510.0073", date(2026, 8, 24))]


def test_una_fecha_que_no_se_lee_se_devuelve_y_no_se_inventa():
    filas, no_legibles, _ = leer_listado("Nº Expediente;Firma acta de inicio\n6.26/28510.0073;agosto\n".encode())
    assert filas[0].acta_inicio is None
    assert no_legibles == ["6.26/28510.0073: agosto"]


def test_elige_la_version_mas_reciente_por_la_fecha_del_nombre(tmp_path):
    for nombre in ("expedientes_en_ejecucion_adif_20260921.csv", "expedientes_en_ejecucion_adif_20261005.csv",
                   "otro_fichero_20991231.csv"):
        (tmp_path / nombre).write_text(LISTADO, encoding="utf-8")
    assert elegir_fichero(str(tmp_path)).name == "expedientes_en_ejecucion_adif_20261005.csv"
    assert elegir_fichero(None) is None


def _expediente(db, codigo, **campos):
    campos.setdefault("estado", EstadoExpediente.completado)
    expediente = Expediente(codigo_expediente=codigo, **campos)
    db.add(expediente)
    db.flush()
    return expediente


def test_carga_solo_el_departamento_y_no_da_de_alta_expedientes(db_session, tmp_path):
    (tmp_path / "expedientes_en_ejecucion_adif_20260921.csv").write_text(LISTADO, encoding="utf-8")
    a = _expediente(db_session, "6.26/28510.0073")
    b = _expediente(db_session, "6.25/28510.0265")
    otro_dpto = _expediente(db_session, "4.25/27520.0191")
    db_session.commit()
    resumen = cargar_en_ejecucion_adif(db_session, str(tmp_path))
    assert resumen.fichero == "expedientes_en_ejecucion_adif_20260921.csv"
    assert (resumen.filas_leidas, resumen.del_departamento, resumen.otros_departamentos) == (5, 4, 1)
    assert (resumen.cargados, resumen.sin_fecha_de_acta) == (2, 1)
    assert sorted(resumen.codigos_sin_expediente) == ["6.24/28510.0008", "6.25/28510.5001/01"]
    assert db_session.query(Expediente).count() == 3  # ninguno nuevo
    assert (a.en_ejecucion_adif, a.acta_inicio_adif) == (True, date(2026, 8, 24))
    assert (b.en_ejecucion_adif, b.acta_inicio_adif) == (True, None)
    assert otro_dpto.en_ejecucion_adif is None  # fuera del alcance
    assert a.en_ejecucion_adif_listado == "expedientes_en_ejecucion_adif_20260921.csv"
    # No toca ninguna de las otras fuentes de estado.
    assert a.estado_adif is None and a.estado_contrato_sap is None


def test_una_version_nueva_sustituye_entera_a_la_anterior(db_session, tmp_path):
    (tmp_path / "expedientes_en_ejecucion_adif_20260921.csv").write_text(LISTADO, encoding="utf-8")
    a = _expediente(db_session, "6.26/28510.0073")
    b = _expediente(db_session, "6.25/28510.0265")
    db_session.commit()
    cargar_en_ejecucion_adif(db_session, str(tmp_path))
    (tmp_path / "expedientes_en_ejecucion_adif_20261005.csv").write_text(
        "Nº Expediente;Firma acta de inicio\n6.25/28510.0265;01/10/2026\n", encoding="utf-8"
    )
    resumen = cargar_en_ejecucion_adif(db_session, str(tmp_path))
    db_session.refresh(a)
    db_session.refresh(b)
    assert (resumen.cargados, resumen.retirados) == (1, 1)
    assert a.en_ejecucion_adif is None and a.acta_inicio_adif is None
    assert (b.acta_inicio_adif, b.en_ejecucion_adif_listado) == (
        date(2026, 10, 1), "expedientes_en_ejecucion_adif_20261005.csv"
    )


def test_la_columna_de_conciliacion_no_decide_que_consta_publicado(db_session):
    # Publicado (está en la sindicación) y en el listado de ADIF.
    publicado = _expediente(db_session, "6.26/28510.0073", en_ejecucion_adif=True,
                            acta_inicio_adif=date(2026, 8, 24))
    db_session.add(SindicacionExpediente(
        codigo_expediente="6.26/28510.0073", expediente_id=publicado.id, periodo_zip="202608",
        actualizado_en=datetime(2026, 8, 1, tzinfo=timezone.utc), estado_pcsp="RES",
    ))
    sin_fecha = _expediente(db_session, "6.25/28510.0265", en_ejecucion_adif=True, descargado_en=datetime.now())
    # En el listado de ADIF pero sin ninguna prueba de estar publicado: no entra.
    _expediente(db_session, "6.25/28510.0250", en_ejecucion_adif=True, acta_inicio_adif=date(2026, 1, 1))
    _expediente(db_session, "6.25/28510.0194", estado=EstadoExpediente.sin_publicar, en_ejecucion_adif=True)
    db_session.commit()
    filas = {f.codigo_expediente: f for f in construir_conciliacion(db_session, {})}
    assert set(filas) == {"6.26/28510.0073", "6.25/28510.0265"}
    assert filas["6.26/28510.0073"].en_ejecucion_adif == "24/08/2026"
    assert filas["6.25/28510.0265"].en_ejecucion_adif == EN_EJECUCION_SIN_FECHA
    # La Situación es la misma que sin el listado.
    sin_listado = {}
    for expediente in (publicado, sin_fecha):
        expediente.en_ejecucion_adif = None
        expediente.acta_inicio_adif = None
    db_session.commit()
    for fila in construir_conciliacion(db_session, {}):
        sin_listado[fila.codigo_expediente] = fila
    assert {c: f.situacion for c, f in filas.items()} == {c: f.situacion for c, f in sin_listado.items()}
    assert all(f.en_ejecucion_adif is None for f in sin_listado.values())


def test_el_resumen_dice_de_que_listado_sale_la_columna(db_session):
    from app.exportacion import _nota_en_ejecucion_adif

    _expediente(db_session, "6.26/28510.0073", en_ejecucion_adif=True, acta_inicio_adif=date(2026, 8, 24),
                en_ejecucion_adif_listado="expedientes_en_ejecucion_adif_20260921.csv",
                descargado_en=datetime.now())
    db_session.commit()
    filas = construir_conciliacion(db_session, {})
    nota = _nota_en_ejecucion_adif(describir_registro_publicado(db_session, filas))
    assert "expedientes_en_ejecucion_adif_20260921.csv" in nota
    assert "18/09/2026" in nota and "21/09/2026" in nota
    assert "NO sale de la Plataforma" in nota
    assert "La llevan 1 expedientes" in nota
