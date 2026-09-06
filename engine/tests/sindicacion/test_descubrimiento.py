"""Bloque 2 (CONTEXTO.md sección 24): descubrimiento de expedientes nuevos por
sindicación y detección de cambio de estado, contra un ZIP local sintético
(`ruta_zip=...`, nunca red real en un test)."""
from datetime import datetime, timezone

from app.models import Expediente, EstadoTrabajo, SindicacionExpediente, TrabajoCola
from app.sindicacion.descubrimiento import descubrir_novedades
from tests.sindicacion.fixtures import construir_zip, entrada_xml


def test_expediente_nuevo_se_da_de_alta(tmp_path, db_session, monkeypatch):
    monkeypatch.setenv("SINDICACION_DEPARTAMENTOS_ADIF", "28510")
    from app import config
    monkeypatch.setattr(config.settings, "sindicacion_departamentos_adif", "28510")

    zip_path = construir_zip(
        tmp_path / "prueba.zip",
        [entrada_xml("6.24/28510.0088", "ADIF - Presidencia", "PUB", "2024-08-05T15:07:29+02:00", "2000000", "2420000")],
    )

    resumen = descubrir_novedades(db_session, periodo="202408", ruta_zip=zip_path)

    assert resumen.expedientes_nuevos == 1
    assert resumen.expedientes_adif_total == 1
    assert resumen.expedientes_filtrados == 1
    expediente = db_session.query(Expediente).filter_by(codigo_expediente="6.24/28510.0088").one()
    assert expediente.estado.value == "pendiente"
    fila = db_session.query(SindicacionExpediente).filter_by(codigo_expediente="6.24/28510.0088").one()
    assert fila.estado_pcsp == "PUB"
    assert fila.periodo_zip == "202408"


def test_departamento_fuera_de_lista_no_se_da_de_alta(tmp_path, db_session, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "sindicacion_departamentos_adif", "28510")

    zip_path = construir_zip(
        tmp_path / "prueba.zip",
        [
            entrada_xml("6.24/28510.0088", "ADIF - Presidencia", "PUB", "2024-08-01T00:00:00+02:00", "1", "1"),
            entrada_xml("3.24/20830.0154", "ADIF Alta Velocidad - Consejo de Administración", "PUB", "2024-08-01T00:00:00+02:00", "1", "1"),
        ],
    )

    resumen = descubrir_novedades(db_session, periodo="202408", ruta_zip=zip_path)

    assert resumen.expedientes_adif_total == 2
    assert resumen.expedientes_filtrados == 1
    assert db_session.query(Expediente).filter_by(codigo_expediente="3.24/20830.0154").one_or_none() is None


def test_organo_no_adif_se_ignora(tmp_path, db_session, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "sindicacion_departamentos_adif", "28510")

    zip_path = construir_zip(
        tmp_path / "prueba.zip",
        [entrada_xml("310/2024", "Alcaldía del Ayuntamiento de Cistierna", "PUB", "2024-08-01T00:00:00+02:00", "1", "1")],
    )

    resumen = descubrir_novedades(db_session, periodo="202408", ruta_zip=zip_path)

    assert resumen.expedientes_adif_total == 0
    assert resumen.expedientes_nuevos == 0


def test_cambio_de_estado_en_expediente_existente_reencola_descarga(tmp_path, db_session, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "sindicacion_departamentos_adif", "28510")

    expediente = Expediente(codigo_expediente="6.24/28510.0088")
    db_session.add(expediente)
    db_session.commit()
    db_session.add(
        SindicacionExpediente(
            codigo_expediente="6.24/28510.0088", expediente_id=expediente.id,
            actualizado_en=datetime(2024, 8, 1, tzinfo=timezone.utc), estado_pcsp="PUB", periodo_zip="202408",
        )
    )
    db_session.commit()

    zip_path = construir_zip(
        tmp_path / "prueba.zip",
        [entrada_xml("6.24/28510.0088", "ADIF - Presidencia", "ADJ", "2024-08-14T10:44:21+02:00", "2000000", "2420000")],
    )

    resumen = descubrir_novedades(db_session, periodo="202408", ruta_zip=zip_path)

    assert resumen.expedientes_con_cambio_estado == 1
    assert resumen.expedientes_nuevos == 0
    trabajos = db_session.query(TrabajoCola).filter_by(tipo="descargar_expediente", expediente_id=expediente.id).all()
    assert len(trabajos) == 1
    assert trabajos[0].estado == EstadoTrabajo.pendiente
    fila = db_session.query(SindicacionExpediente).filter_by(codigo_expediente="6.24/28510.0088").one()
    assert fila.estado_pcsp == "ADJ"


def test_mismo_estado_no_reencola_nada(tmp_path, db_session, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "sindicacion_departamentos_adif", "28510")

    expediente = Expediente(codigo_expediente="6.24/28510.0088")
    db_session.add(expediente)
    db_session.commit()
    db_session.add(
        SindicacionExpediente(
            codigo_expediente="6.24/28510.0088", expediente_id=expediente.id,
            actualizado_en=datetime(2024, 8, 1, tzinfo=timezone.utc), estado_pcsp="PUB", periodo_zip="202408",
        )
    )
    db_session.commit()

    zip_path = construir_zip(
        tmp_path / "prueba.zip",
        [entrada_xml("6.24/28510.0088", "ADIF - Presidencia", "PUB", "2024-08-14T10:44:21+02:00", "1", "1")],
    )

    resumen = descubrir_novedades(db_session, periodo="202408", ruta_zip=zip_path)

    assert resumen.expedientes_sin_cambios == 1
    assert db_session.query(TrabajoCola).filter_by(tipo="descargar_expediente").count() == 0


def test_no_regresa_a_un_dato_de_sindicacion_mas_viejo(tmp_path, db_session, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "sindicacion_departamentos_adif", "28510")

    expediente = Expediente(codigo_expediente="6.24/28510.0088")
    db_session.add(expediente)
    db_session.commit()
    db_session.add(
        SindicacionExpediente(
            codigo_expediente="6.24/28510.0088", expediente_id=expediente.id,
            actualizado_en=datetime(2024, 8, 20, tzinfo=timezone.utc), estado_pcsp="RES",
            importe_licitacion_sin_impuestos="2000000", periodo_zip="202408",
        )
    )
    db_session.commit()

    # Entrada "más vieja" que lo ya guardado (p.ej. se reprocesa el mismo
    # periodo desde el principio): no debe pisar el dato más reciente.
    zip_path = construir_zip(
        tmp_path / "prueba.zip",
        [entrada_xml("6.24/28510.0088", "ADIF - Presidencia", "PUB", "2024-08-05T00:00:00+02:00", "1", "1")],
    )

    resumen = descubrir_novedades(db_session, periodo="202408", ruta_zip=zip_path)

    assert resumen.expedientes_con_cambio_estado == 0
    fila = db_session.query(SindicacionExpediente).filter_by(codigo_expediente="6.24/28510.0088").one()
    assert fila.estado_pcsp == "RES"
    assert str(fila.importe_licitacion_sin_impuestos) == "2000000.0000"
