"""Bloque 2, punto 4 (CLAUDE.md sección 24): contraste de importes entre lo
que extrajo la cascada de los PDFs y la instantánea de sindicación."""
from datetime import datetime, timezone
from decimal import Decimal

from app.models import Expediente, SindicacionExpediente
from app.sindicacion.contraste import contrastar_expediente


def _expediente(db, **kwargs) -> Expediente:
    base = dict(codigo_expediente="6.24/28510.0088")
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


def test_sin_fila_de_sindicacion_no_hay_nada_que_contrastar(db_session):
    exp = _expediente(db_session, importe_licitacion=Decimal("2000000"))
    assert contrastar_expediente(db_session, exp) is None


def test_importes_que_cuadran_no_dan_motivo(db_session):
    exp = _expediente(db_session, importe_licitacion=Decimal("2000000"), importe_adjudicacion=Decimal("1900000"))
    _fila_sindicacion(
        db_session, exp.codigo_expediente,
        importe_licitacion_sin_impuestos=Decimal("2000000"), importe_adjudicacion_sin_impuestos=Decimal("1900500"),
    )
    assert contrastar_expediente(db_session, exp) is None


def test_importe_licitacion_no_cuadra(db_session):
    exp = _expediente(db_session, importe_licitacion=Decimal("2000000"))
    _fila_sindicacion(db_session, exp.codigo_expediente, importe_licitacion_sin_impuestos=Decimal("1000000"))
    motivo = contrastar_expediente(db_session, exp)
    assert motivo is not None
    assert "licitación" in motivo


def test_importe_adjudicacion_no_cuadra(db_session):
    exp = _expediente(db_session, importe_adjudicacion=Decimal("500000"))
    _fila_sindicacion(db_session, exp.codigo_expediente, importe_adjudicacion_sin_impuestos=Decimal("100000"))
    motivo = contrastar_expediente(db_session, exp)
    assert motivo is not None
    assert "adjudicación" in motivo


def test_ambos_no_cuadran_da_los_dos_motivos(db_session):
    exp = _expediente(db_session, importe_licitacion=Decimal("2000000"), importe_adjudicacion=Decimal("500000"))
    _fila_sindicacion(
        db_session, exp.codigo_expediente,
        importe_licitacion_sin_impuestos=Decimal("1000000"), importe_adjudicacion_sin_impuestos=Decimal("100000"),
    )
    motivo = contrastar_expediente(db_session, exp)
    assert "licitación" in motivo and "adjudicación" in motivo


def test_sin_importe_extraido_todavia_no_contrasta(db_session):
    exp = _expediente(db_session)
    _fila_sindicacion(db_session, exp.codigo_expediente, importe_licitacion_sin_impuestos=Decimal("2000000"))
    assert contrastar_expediente(db_session, exp) is None
