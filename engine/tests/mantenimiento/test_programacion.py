"""Bloque 3 (CONTEXTO.md sección 25): ejecución programada — sin solaparse
consigo misma, con histórico consultable en `trabajos_cola`."""
from datetime import datetime, timedelta, timezone

from app import config
from app.mantenimiento.programacion import (
    DISPARADO_POR_MANUAL,
    DISPARADO_POR_PROGRAMADO,
    obtener_estado,
    obtener_estado_copia,
    verificar_y_lanzar_ciclo_programado,
    verificar_y_lanzar_copia_programada,
)
from app.models import EstadoTrabajo, TrabajoCola


def _trabajo(db, *, tipo: str, hace_segundos: float, estado=EstadoTrabajo.completado, disparado_por=None) -> TrabajoCola:
    trabajo = TrabajoCola(
        tipo=tipo,
        estado=estado,
        payload={"disparado_por": disparado_por} if disparado_por else None,
        created_at=datetime.now(timezone.utc) - timedelta(seconds=hace_segundos),
    )
    db.add(trabajo)
    db.commit()
    db.refresh(trabajo)
    return trabajo


def _trabajo_ciclo(db, *, hace_segundos: float, estado=EstadoTrabajo.completado, disparado_por=None) -> TrabajoCola:
    return _trabajo(db, tipo="mantenimiento_ciclo", hace_segundos=hace_segundos, estado=estado, disparado_por=disparado_por)


def _trabajo_copia(db, *, hace_segundos: float, estado=EstadoTrabajo.completado, disparado_por=None) -> TrabajoCola:
    return _trabajo(db, tipo="copia_seguridad", hace_segundos=hace_segundos, estado=estado, disparado_por=disparado_por)


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


# Copias de seguridad automáticas (sesión 2026-09-06): mismo mecanismo que
# el ciclo de mantenimiento de arriba (programacion.py lo generalizó por
# tipo de trabajo para esto exactamente) -- mismos siete casos, sobre
# `copia_seguridad` y las variables BACKUP_*.


def test_copia_nunca_corrio_lanza_ahora(db_session, monkeypatch):
    monkeypatch.setattr(config.settings, "backup_intervalo_segundos", 3600.0)
    monkeypatch.setattr(config.settings, "backup_activo", True)

    lanzado = verificar_y_lanzar_copia_programada(db_session)

    assert lanzado is not None
    assert lanzado.tipo == "copia_seguridad"
    assert lanzado.payload["disparado_por"] == DISPARADO_POR_PROGRAMADO


def test_copia_no_lanza_antes_de_tiempo(db_session, monkeypatch):
    monkeypatch.setattr(config.settings, "backup_intervalo_segundos", 3600.0)
    monkeypatch.setattr(config.settings, "backup_activo", True)
    _trabajo_copia(db_session, hace_segundos=10)

    lanzado = verificar_y_lanzar_copia_programada(db_session)

    assert lanzado is None


def test_copia_lanza_cuando_toca(db_session, monkeypatch):
    monkeypatch.setattr(config.settings, "backup_intervalo_segundos", 60.0)
    monkeypatch.setattr(config.settings, "backup_activo", True)
    _trabajo_copia(db_session, hace_segundos=120)

    lanzado = verificar_y_lanzar_copia_programada(db_session)

    assert lanzado is not None


def test_copia_no_solapa_con_una_en_curso(db_session, monkeypatch):
    monkeypatch.setattr(config.settings, "backup_intervalo_segundos", 1.0)
    monkeypatch.setattr(config.settings, "backup_activo", True)
    _trabajo_copia(db_session, hace_segundos=100, estado=EstadoTrabajo.en_proceso)

    lanzado = verificar_y_lanzar_copia_programada(db_session)

    assert lanzado is None
    assert db_session.query(TrabajoCola).count() == 1


def test_copia_no_lanza_si_ciclo_de_mantenimiento_esta_en_curso(db_session, monkeypatch):
    """Los dos tipos de trabajo no se pisan entre sí: "sin solaparse consigo
    mismo" es por tipo, no global -- un ciclo de mantenimiento largo en
    curso no debe bloquear la copia diaria."""
    monkeypatch.setattr(config.settings, "backup_intervalo_segundos", 1.0)
    monkeypatch.setattr(config.settings, "backup_activo", True)
    _trabajo_ciclo(db_session, hace_segundos=100, estado=EstadoTrabajo.en_proceso)

    lanzado = verificar_y_lanzar_copia_programada(db_session)

    assert lanzado is not None


def test_copia_desactivada_nunca_lanza(db_session, monkeypatch):
    monkeypatch.setattr(config.settings, "backup_intervalo_segundos", 1.0)
    monkeypatch.setattr(config.settings, "backup_activo", False)
    _trabajo_copia(db_session, hace_segundos=100)

    lanzado = verificar_y_lanzar_copia_programada(db_session)

    assert lanzado is None


def test_obtener_estado_copia(db_session, monkeypatch):
    monkeypatch.setattr(config.settings, "backup_intervalo_segundos", 86400.0)
    trabajo = _trabajo_copia(db_session, hace_segundos=10, disparado_por=DISPARADO_POR_MANUAL)

    estado = obtener_estado_copia(db_session)

    assert estado.ultima_ejecucion.id == trabajo.id
    assert estado.en_curso is False
    assert estado.intervalo_segundos == 86400.0
    assert estado.proxima_ejecucion > datetime.now(timezone.utc)
