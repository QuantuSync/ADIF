"""Bloque 3 (CLAUDE.md sección 25): ejecución programada — sin solaparse
consigo misma, con histórico consultable en `trabajos_cola`."""
from datetime import datetime, timedelta, timezone

from app import config
from app.mantenimiento.programacion import (
    DISPARADO_POR_MANUAL,
    DISPARADO_POR_PROGRAMADO,
    obtener_estado,
    verificar_y_lanzar_ciclo_programado,
)
from app.models import EstadoTrabajo, TrabajoCola


def _trabajo_ciclo(db, *, hace_segundos: float, estado=EstadoTrabajo.completado, disparado_por=None) -> TrabajoCola:
    trabajo = TrabajoCola(
        tipo="mantenimiento_ciclo",
        estado=estado,
        payload={"disparado_por": disparado_por} if disparado_por else None,
        created_at=datetime.now(timezone.utc) - timedelta(seconds=hace_segundos),
    )
    db.add(trabajo)
    db.commit()
    db.refresh(trabajo)
    return trabajo


def test_nunca_corrio_lanza_ahora(db_session, monkeypatch):
    monkeypatch.setattr(config.settings, "mantenimiento_intervalo_segundos", 3600.0)
    monkeypatch.setattr(config.settings, "mantenimiento_programado_activo", True)

    lanzado = verificar_y_lanzar_ciclo_programado(db_session)

    assert lanzado is not None
    assert lanzado.payload["disparado_por"] == DISPARADO_POR_PROGRAMADO


def test_no_lanza_antes_de_tiempo(db_session, monkeypatch):
    monkeypatch.setattr(config.settings, "mantenimiento_intervalo_segundos", 3600.0)
    monkeypatch.setattr(config.settings, "mantenimiento_programado_activo", True)
    _trabajo_ciclo(db_session, hace_segundos=10)

    lanzado = verificar_y_lanzar_ciclo_programado(db_session)

    assert lanzado is None


def test_lanza_cuando_toca(db_session, monkeypatch):
    monkeypatch.setattr(config.settings, "mantenimiento_intervalo_segundos", 60.0)
    monkeypatch.setattr(config.settings, "mantenimiento_programado_activo", True)
    _trabajo_ciclo(db_session, hace_segundos=120)

    lanzado = verificar_y_lanzar_ciclo_programado(db_session)

    assert lanzado is not None


def test_no_solapa_con_uno_en_curso(db_session, monkeypatch):
    monkeypatch.setattr(config.settings, "mantenimiento_intervalo_segundos", 1.0)
    monkeypatch.setattr(config.settings, "mantenimiento_programado_activo", True)
    _trabajo_ciclo(db_session, hace_segundos=100, estado=EstadoTrabajo.en_proceso)

    lanzado = verificar_y_lanzar_ciclo_programado(db_session)

    assert lanzado is None
    assert db_session.query(TrabajoCola).count() == 1


def test_no_solapa_con_uno_pendiente_disparado_a_mano(db_session, monkeypatch):
    """Da igual el origen del que ya está en cola: "sin solaparse consigo
    mismo" no distingue entre un ciclo programado y uno lanzado a mano."""
    monkeypatch.setattr(config.settings, "mantenimiento_intervalo_segundos", 1.0)
    monkeypatch.setattr(config.settings, "mantenimiento_programado_activo", True)
    _trabajo_ciclo(db_session, hace_segundos=100, estado=EstadoTrabajo.pendiente, disparado_por=DISPARADO_POR_MANUAL)

    lanzado = verificar_y_lanzar_ciclo_programado(db_session)

    assert lanzado is None


def test_desactivado_nunca_lanza(db_session, monkeypatch):
    monkeypatch.setattr(config.settings, "mantenimiento_intervalo_segundos", 1.0)
    monkeypatch.setattr(config.settings, "mantenimiento_programado_activo", False)
    _trabajo_ciclo(db_session, hace_segundos=100)

    lanzado = verificar_y_lanzar_ciclo_programado(db_session)

    assert lanzado is None


def test_obtener_estado(db_session, monkeypatch):
    monkeypatch.setattr(config.settings, "mantenimiento_intervalo_segundos", 3600.0)
    trabajo = _trabajo_ciclo(db_session, hace_segundos=10, disparado_por=DISPARADO_POR_MANUAL)

    estado = obtener_estado(db_session)

    assert estado.ultima_ejecucion.id == trabajo.id
    assert estado.en_curso is False
    assert estado.intervalo_segundos == 3600.0
    assert estado.proxima_ejecucion > datetime.now(timezone.utc)
