"""Bloque 2 (CONTEXTO.md sección 24): descubrimiento de expedientes nuevos por
sindicación y detección de cambio de estado, contra un ZIP local sintético
(`ruta_zip=...`, nunca red real en un test)."""
from datetime import datetime, timezone

import pytest

from app.models import Expediente, EstadoTrabajo, SindicacionExpediente, TrabajoCola
from app.sindicacion.descubrimiento import descubrir_backfill, descubrir_novedades, periodos_recientes
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


# Bloque 4, sesión de comparación documento-vs-listado interno: el cliente
# planteó que puede haber contratos en ejecución de otro departamento --
# comprobado que `sindicacion_departamentos_adif` ya admite una lista
# separada por comas (`_departamentos_configurados`), no un único
# departamento fijo. Sin cambio de código, esta prueba lo deja verificado.
def test_admite_una_lista_de_varios_departamentos(tmp_path, db_session, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "sindicacion_departamentos_adif", "28510,28520")

    zip_path = construir_zip(
        tmp_path / "prueba.zip",
        [
            entrada_xml("6.24/28510.0088", "ADIF - Presidencia", "PUB", "2024-08-01T00:00:00+02:00", "1", "1"),
            entrada_xml("6.24/28520.0001", "ADIF - Presidencia", "PUB", "2024-08-01T00:00:00+02:00", "1", "1"),
            entrada_xml("3.24/20830.0154", "ADIF Alta Velocidad - Consejo de Administración", "PUB", "2024-08-01T00:00:00+02:00", "1", "1"),
        ],
    )

    resumen = descubrir_novedades(db_session, periodo="202408", ruta_zip=zip_path)

    assert resumen.expedientes_adif_total == 3
    assert resumen.expedientes_filtrados == 2
    assert db_session.query(Expediente).filter_by(codigo_expediente="6.24/28510.0088").one_or_none() is not None
    assert db_session.query(Expediente).filter_by(codigo_expediente="6.24/28520.0001").one_or_none() is not None
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


# Hallazgo real (aviso del cliente, sesión 2026-09-07, caso 6.26/28510.0014):
# nada llamaba nunca a `descubrir_novedades` con un periodo que no fuera el
# mes en curso -- `periodos_recientes` y `descubrir_backfill` cierran ese
# hueco, sin tocar `descubrir_novedades` en sí (ya aceptaba `periodo`).


def test_periodos_recientes_orden_mas_reciente_primero():
    periodos = periodos_recientes(3, hasta="202609")

    assert periodos == ["202609", "202608", "202607"]


def test_periodos_recientes_cruza_el_cambio_de_anio():
    periodos = periodos_recientes(4, hasta="202601")

    assert periodos == ["202601", "202512", "202511", "202510"]


def test_periodos_recientes_rechaza_n_menor_que_uno():
    with pytest.raises(ValueError):
        periodos_recientes(0)


def test_descubrir_backfill_agrega_varios_periodos(tmp_path, db_session, monkeypatch):
    # Sesión de límite de tasa (2026-09-07): pausa mínima real entre
    # periodos -- sin esto, el test tardaría de verdad varios segundos.
    monkeypatch.setattr("app.sindicacion.descubrimiento.time.sleep", lambda *_: None)
    from app import config
    monkeypatch.setattr(config.settings, "sindicacion_departamentos_adif", "28510")

    zip_agosto = construir_zip(
        tmp_path / "202408.zip",
        [entrada_xml("6.24/28510.0088", "ADIF - Presidencia", "PUB", "2024-08-05T15:07:29+02:00", "2000000", "2420000")],
    )
    zip_septiembre = construir_zip(
        tmp_path / "202409.zip",
        [entrada_xml("6.24/28510.0100", "ADIF - Presidencia", "PUB", "2024-09-05T15:07:29+02:00", "500000", "605000")],
    )

    def _descubrir_falso(db, periodo=None, ruta_zip=None):
        ruta = {"202408": zip_agosto, "202409": zip_septiembre}[periodo]
        return descubrir_novedades(db, periodo=periodo, ruta_zip=ruta)

    monkeypatch.setattr("app.sindicacion.descubrimiento.descubrir_novedades", _descubrir_falso)

    resumen = descubrir_backfill(db_session, ["202409", "202408"])

    assert resumen.periodos_procesados == ["202409", "202408"]
    assert resumen.periodos_con_error == {}
    assert resumen.expedientes_nuevos == 2
    codigos = {e.codigo_expediente for e in db_session.query(Expediente).all()}
    assert {"6.24/28510.0088", "6.24/28510.0100"} <= codigos


def test_descubrir_backfill_aisla_el_fallo_de_un_periodo(db_session, monkeypatch):
    # Sesión de límite de tasa (2026-09-07): un periodo que sigue fallando
    # ahora se reintenta `_REINTENTOS_POR_PERIODO` veces (con espera
    # creciente real entre intentos) antes de darlo por perdido -- sin
    # anular `time.sleep`, este test tardaría varios minutos.
    monkeypatch.setattr("app.sindicacion.descubrimiento.time.sleep", lambda *_: None)
    llamados = []

    def _descubrir_falso(db, periodo=None, ruta_zip=None):
        llamados.append(periodo)
        if periodo == "202501":
            raise RuntimeError("ZIP no publicado para este periodo")
        from app.sindicacion.descubrimiento import ResumenDescubrimiento
        return ResumenDescubrimiento(periodo=periodo, expedientes_nuevos=1)

    monkeypatch.setattr("app.sindicacion.descubrimiento.descubrir_novedades", _descubrir_falso)

    resumen = descubrir_backfill(db_session, ["202503", "202502", "202501"])

    # El fallo de un periodo no interrumpe la tanda: los otros dos se
    # intentan igual. "202501" se reintenta 3 veces (mismo error cada vez)
    # antes de darse por vencido.
    assert llamados == ["202503", "202502", "202501", "202501", "202501"]
    assert resumen.periodos_procesados == ["202503", "202502"]
    assert resumen.periodos_con_error == {"202501": "ZIP no publicado para este periodo"}
    assert resumen.expedientes_nuevos == 2


def test_descubrir_backfill_recupera_tras_un_fallo_transitorio(db_session, monkeypatch):
    # Distingue un bloqueo transitorio real (se recupera solo al reintentar)
    # de un mes genuinamente sin publicar (sección de arriba): si el
    # segundo intento tiene éxito, el periodo cuenta como procesado, no
    # como error.
    monkeypatch.setattr("app.sindicacion.descubrimiento.time.sleep", lambda *_: None)
    intentos_202501 = []

    def _descubrir_falso(db, periodo=None, ruta_zip=None):
        from app.sindicacion.descubrimiento import ResumenDescubrimiento
        if periodo == "202501":
            intentos_202501.append(1)
            if len(intentos_202501) < 2:
                raise RuntimeError("la Plataforma devolvió una página de bloqueo/límite de tasa reconocible")
        return ResumenDescubrimiento(periodo=periodo, expedientes_nuevos=1)

    monkeypatch.setattr("app.sindicacion.descubrimiento.descubrir_novedades", _descubrir_falso)

    resumen = descubrir_backfill(db_session, ["202501"])

    assert len(intentos_202501) == 2
    assert resumen.periodos_procesados == ["202501"]
    assert resumen.periodos_con_error == {}
    assert resumen.expedientes_nuevos == 1
