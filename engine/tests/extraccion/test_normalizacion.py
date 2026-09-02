from decimal import Decimal

import pytest

from app.extraccion.normalizacion import (
    parsear_importe_es,
    parsear_numero_es,
    parsear_porcentaje_es,
)


def test_miles_y_decimales():
    # CLAUDE.md sección 8: el ejemplo que float() rompe.
    assert parsear_numero_es("1.234.567,89") == Decimal("1234567.89")


def test_solo_miles_sin_decimales():
    # "145.100 EUR." -> 145100, no 145.1: el punto es de miles, no decimal,
    # porque no hay coma en el número.
    assert parsear_numero_es("145.100") == Decimal("145100")


def test_importe_con_simbolo_euro_y_espacios():
    assert parsear_importe_es(" 138.000,00 € ") == Decimal("138000.00")


def test_importe_sin_separador_de_miles():
    assert parsear_importe_es("55.400,00") == Decimal("55400.00")


def test_porcentaje_devuelve_fraccion():
    assert parsear_porcentaje_es("54,00 %") == Decimal("0.5400")
    assert parsear_porcentaje_es("0,50%") == Decimal("0.0050")


def test_cadena_vacia_es_error():
    with pytest.raises(ValueError):
        parsear_numero_es("")


def test_cadena_sin_digitos_es_error():
    with pytest.raises(ValueError):
        parsear_numero_es("N/A")
