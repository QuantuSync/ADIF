from decimal import Decimal

import pytest

from app.extraccion.precios_unitarios import calcular_baja_efectiva


def test_caso_precios_unitarios_con_baja_declarada_no_da_cero():
    # CONTEXTO.md sección 4, el caso central del proyecto: licitación y
    # adjudicación iguales no significa baja 0 %.
    r = calcular_baja_efectiva(
        importe_licitacion=Decimal("1000000.00"),
        importe_adjudicacion=Decimal("1000000.00"),
        baja_declarada=Decimal("0.0050"),
    )
    assert r.caso_precios_unitarios is True
    assert r.baja == Decimal("0.0050")
    assert r.requiere_revision is False


def test_caso_precios_unitarios_sin_baja_declarada_va_a_revision():
    # CONTEXTO.md sección 12: "un sistema que sabe cuándo no sabe vale más...".
    r = calcular_baja_efectiva(
        importe_licitacion=Decimal("145100"),
        importe_adjudicacion=Decimal("145100"),
        baja_declarada=None,
    )
    assert r.caso_precios_unitarios is True
    assert r.requiere_revision is True
    assert r.baja is None


def test_caso_normal_deriva_baja_de_los_importes():
    r = calcular_baja_efectiva(
        importe_licitacion=Decimal("100000"),
        importe_adjudicacion=Decimal("80000"),
        baja_declarada=None,
    )
    assert r.caso_precios_unitarios is False
    assert r.requiere_revision is False
    assert r.baja == Decimal("0.2")


def test_caso_normal_con_baja_declarada_que_cuadra():
    r = calcular_baja_efectiva(
        importe_licitacion=Decimal("100000"),
        importe_adjudicacion=Decimal("80000"),
        baja_declarada=Decimal("0.20"),
    )
    assert r.requiere_revision is False
    assert r.baja == Decimal("0.20")


def test_baja_declarada_que_no_cuadra_se_da_por_buena():
    # CONTEXTO.md sección 26, criterio del cliente: lote + expediente + baja
    # declarada bastan, ya no se exige que cuadre con la baja por importes.
    r = calcular_baja_efectiva(
        importe_licitacion=Decimal("100000"),
        importe_adjudicacion=Decimal("80000"),
        baja_declarada=Decimal("0.50"),  # muy lejos del 20% que dan los importes
    )
    assert r.requiere_revision is False
    assert r.caso_precios_unitarios is False
    assert r.baja == Decimal("0.50")


def test_importe_licitacion_cero_es_error_no_caso_especial():
    with pytest.raises(ValueError):
        calcular_baja_efectiva(Decimal("0"), Decimal("0"), None)
