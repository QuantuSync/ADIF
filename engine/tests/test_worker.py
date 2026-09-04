"""CLAUDE.md sección 26 (regresión de 6.24/28510.0088): un desajuste con la
instantánea de sindicación ya no cambia `estado` ni `error` de un
expediente -- el PDF es el acto administrativo, la sindicación no tiene su
misma autoridad. Se guarda como aviso informativo aparte."""
from datetime import datetime, timezone
from decimal import Decimal

from app.models import EstadoExpediente, Expediente, SindicacionExpediente
from app.worker import _contrastar_con_sindicacion


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
