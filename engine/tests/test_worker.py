"""CONTEXTO.md sección 26 (regresión de 6.24/28510.0088): un desajuste con la
instantánea de sindicación ya no cambia `estado` ni `error` de un
expediente -- el PDF es el acto administrativo, la sindicación no tiene su
misma autoridad. Se guarda como aviso informativo aparte."""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from app.models import EstadoExpediente, Expediente, SindicacionExpediente
from app.worker import _contrastar_con_sindicacion, bucle_principal, procesar_sindicacion_backfill


def _expediente(db, **kwargs) -> Expediente:
    base = dict(codigo_expediente="6.24/28510.0088", estado=EstadoExpediente.completado)
    base.update(kwargs)
    exp = Expediente(**base)
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


def _fila_sindicacion(db, codigo, **kwargs) -> SindicacionExpediente:
    base = dict(codigo_expediente=codigo, actualizado_en=datetime.now(timezone.utc), periodo_zip="202408")
    base.update(kwargs)
    fila = SindicacionExpediente(**base)
    db.add(fila)
    db.commit()
    return fila


def test_desajuste_no_baja_de_completado_se_guarda_como_aviso(db_session):
    exp = _expediente(db_session, importe_licitacion=Decimal("1000000"))
    _fila_sindicacion(db_session, exp.codigo_expediente, importe_licitacion_sin_impuestos=Decimal("2000000"))

    _contrastar_con_sindicacion(db_session, exp)

    assert exp.estado == EstadoExpediente.completado
    assert exp.error is None
    assert exp.aviso_sindicacion is not None
    assert "licitación" in exp.aviso_sindicacion


def test_desajuste_sobre_expediente_en_revision_no_toca_su_error(db_session):
    exp = _expediente(
        db_session, estado=EstadoExpediente.pendiente_revision, error="motivo real, ajeno a sindicación",
        importe_licitacion=Decimal("1000000"),
    )
    _fila_sindicacion(db_session, exp.codigo_expediente, importe_licitacion_sin_impuestos=Decimal("2000000"))

    _contrastar_con_sindicacion(db_session, exp)

    assert exp.estado == EstadoExpediente.pendiente_revision
    assert exp.error == "motivo real, ajeno a sindicación"
    assert exp.aviso_sindicacion is not None


def test_sin_desajuste_aviso_queda_vacio(db_session):
    exp = _expediente(db_session, importe_licitacion=Decimal("1000000"))
    _fila_sindicacion(db_session, exp.codigo_expediente, importe_licitacion_sin_impuestos=Decimal("1000000"))

    _contrastar_con_sindicacion(db_session, exp)

    assert exp.estado == EstadoExpediente.completado
    assert exp.aviso_sindicacion is None


def test_reproceso_limpia_un_aviso_que_ya_no_aplica(db_session):
    exp = _expediente(db_session, importe_licitacion=Decimal("1000000"), aviso_sindicacion="aviso viejo")
    _fila_sindicacion(db_session, exp.codigo_expediente, importe_licitacion_sin_impuestos=Decimal("1000000"))

    _contrastar_con_sindicacion(db_session, exp)

    assert exp.aviso_sindicacion is None


def test_expediente_fallido_no_se_contrasta(db_session):
    exp = _expediente(db_session, estado=EstadoExpediente.fallido, error="fallo real de scraping")
    _fila_sindicacion(db_session, exp.codigo_expediente, importe_licitacion_sin_impuestos=Decimal("2000000"))

    _contrastar_con_sindicacion(db_session, exp)

    assert exp.aviso_sindicacion is None
    assert exp.error == "fallo real de scraping"


# Sesión de tolerancia a reinicios de dockerd (2026-09-06): un fallo de
# conexión transitorio dentro de una vuelta del bucle (no de un trabajo
# concreto, que ya aísla los suyos en app.queue.ejecutar_trabajo) mataba el
# proceso entero -- reproducido en vivo contra el stack real, reiniciando
# dockerd mientras el worker corría: `reclamar_trabajos_huerfanos` se topó
# con un DNS que aún no resolvía justo después de que `app.esperar_bd` ya
# hubiera comprobado conectividad, y la excepción sin atrapar tiró el
# proceso completo.
def test_bucle_principal_no_muere_por_un_fallo_de_conexion_transitorio(monkeypatch):
    marcador_fin_test = RuntimeError("fin del test: segunda vuelta alcanzada")
    vuelta = MagicMock(side_effect=[OperationalError("SELECT 1", {}, Exception("dns")), marcador_fin_test])
    monkeypatch.setattr("app.worker._vuelta_bucle_principal", vuelta)

    sesiones_cerradas = []

    def sesion_falsa():
        db = MagicMock()
        db.close.side_effect = lambda: sesiones_cerradas.append(db)
        return db

    monkeypatch.setattr("app.worker.SessionLocal", sesion_falsa)
    monkeypatch.setattr("app.worker.time.sleep", lambda s: None)

    with pytest.raises(RuntimeError, match="fin del test"):
        bucle_principal()

    # Dos vueltas: la primera falló por conexión y NO propagó -- si hubiera
    # matado el proceso, `vuelta` nunca se habría llamado una segunda vez.
    assert vuelta.call_count == 2
    assert len(sesiones_cerradas) == 2  # cada vuelta cierra su propia sesión, incluida la que falló


# Hallazgo real (aviso del cliente, sesión 2026-09-07, caso 6.26/28510.0014):
# nada llamaba nunca a descubrir_novedades con un mes pasado -- este trabajo
# de cola es el barrido explícito. Payload: `periodos` manda si viene, si no
# se resuelve `meses` (por defecto 12) con `periodos_recientes`.


def test_procesar_sindicacion_backfill_usa_periodos_explicitos(monkeypatch):
    llamado_con = {}

    def _backfill_falso(db, periodos):
        llamado_con["periodos"] = periodos
        from app.sindicacion.descubrimiento import ResumenBackfill
        return ResumenBackfill(periodos_procesados=list(periodos), expedientes_nuevos=3)

    monkeypatch.setattr("app.worker.descubrir_backfill", _backfill_falso)

    trabajo = SimpleNamespace(payload={"periodos": ["202501", "202412"]})
    resultado = procesar_sindicacion_backfill(MagicMock(), trabajo)

    assert llamado_con["periodos"] == ["202501", "202412"]
    assert resultado["expedientes_nuevos"] == 3


def test_procesar_sindicacion_backfill_resuelve_meses_por_defecto(monkeypatch):
    llamado_con = {}

    def _backfill_falso(db, periodos):
        llamado_con["periodos"] = periodos
        from app.sindicacion.descubrimiento import ResumenBackfill
        return ResumenBackfill(periodos_procesados=list(periodos))

    monkeypatch.setattr("app.worker.descubrir_backfill", _backfill_falso)
    monkeypatch.setattr("app.worker.periodos_recientes", lambda n: [f"periodo-{n}"])

    trabajo = SimpleNamespace(payload={"meses": 6})
    procesar_sindicacion_backfill(MagicMock(), trabajo)

    assert llamado_con["periodos"] == ["periodo-6"]


def test_procesar_sindicacion_backfill_sin_payload_usa_doce_meses(monkeypatch):
    llamado_con = {}

    def _backfill_falso(db, periodos):
        llamado_con["periodos"] = periodos
        from app.sindicacion.descubrimiento import ResumenBackfill
        return ResumenBackfill(periodos_procesados=list(periodos))

    monkeypatch.setattr("app.worker.descubrir_backfill", _backfill_falso)
    monkeypatch.setattr("app.worker.periodos_recientes", lambda n: [f"periodo-{n}"])

    trabajo = SimpleNamespace(payload=None)
    procesar_sindicacion_backfill(MagicMock(), trabajo)

    assert llamado_con["periodos"] == ["periodo-12"]
