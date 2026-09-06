"""Integración bloque 1 + bloque 2 (CONTEXTO.md sección 24): un expediente
descubierto por sindicación en un ciclo entra en el mismo bucle de decisión
de frescura de ESE mismo ciclo, sin esperar al siguiente."""
from app.mantenimiento.ciclo import ejecutar_ciclo_mantenimiento
from app.models import Expediente
from app.queue import encolar_trabajo
from tests.sindicacion.fixtures import construir_zip, entrada_xml


def test_expediente_descubierto_se_procesa_en_el_mismo_ciclo(tmp_path, db_session, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "sindicacion_departamentos_adif", "28510")

    zip_path = construir_zip(
        tmp_path / "prueba.zip",
        [entrada_xml("6.24/28510.0088", "ADIF - Presidencia", "PUB", "2024-08-05T15:07:29+02:00", "1", "1")],
    )

    descargas = []
    manejadores = {"descargar_expediente": lambda db, t: descargas.append(t.expediente_id) or {}}
    trabajo = encolar_trabajo(
        db_session, tipo="mantenimiento_ciclo",
        payload={"sindicacion_desactivada": False, "sindicacion_periodo": "202408", "sindicacion_ruta_zip": str(zip_path)},
    )

    resumen = ejecutar_ciclo_mantenimiento(db_session, storage=None, model_provider=None, manejadores=manejadores, trabajo=trabajo)

    assert resumen["nuevos_descubiertos"] == 1
    expediente = db_session.query(Expediente).filter_by(codigo_expediente="6.24/28510.0088").one()
    assert descargas == [expediente.id]
    assert resumen["descargas_lanzadas"] == 1


def test_fallo_de_descubrimiento_no_impide_el_resto_del_ciclo(tmp_path, db_session):
    """Un periodo sin ZIP real (fichero inexistente) no debe tirar el resto
    del ciclo -- el descubrimiento falla, se registra el error, y el bucle
    de frescura de siempre sigue evaluando lo que ya había."""
    exp = Expediente(codigo_expediente="6.24/28510.0001")
    db_session.add(exp)
    db_session.commit()

    trabajo = encolar_trabajo(
        db_session, tipo="mantenimiento_ciclo",
        payload={
            "sindicacion_desactivada": False, "sindicacion_periodo": "999999",
            "sindicacion_ruta_zip": str(tmp_path / "no-existe.zip"),
        },
    )

    resumen = ejecutar_ciclo_mantenimiento(db_session, storage=None, model_provider=None, manejadores={}, trabajo=trabajo)

    assert "error" in resumen["descubrimiento"]
    assert resumen["expedientes_evaluados"] == 1
