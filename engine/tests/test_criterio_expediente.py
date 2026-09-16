"""Criterio del cliente sobre qué código es del departamento
(`app.criterio_expediente`), compartido por las dos vías de descubrimiento."""
import pytest

from app.criterio_expediente import cumple_criterio, fragmento_en_codigo


@pytest.mark.parametrize(
    "codigo",
    ["6.26/28510.0016", "2.26/28510.5002/01", "28510.0001", "AM-28510-X", "6.26/28510"],
)
def test_codigos_del_departamento(codigo):
    assert fragmento_en_codigo(codigo, "28510") is True


@pytest.mark.parametrize(
    "codigo",
    [
        # Casos reales devueltos por el buscador de la Plataforma al buscar
        # "28510" (sesión 2026-09-16): los dígitos son parte de otro número.
        "PcPG/2026/828510",
        "EMER_HV_2020_62285100",
        "1285107",
    ],
)
def test_digitos_pegados_a_otros_digitos_no_son_el_departamento(codigo):
    assert fragmento_en_codigo(codigo, "28510") is False


def test_codigo_vacio_o_ausente():
    assert fragmento_en_codigo(None, "28510") is False
    assert fragmento_en_codigo("", "28510") is False
    assert fragmento_en_codigo("6.26/28510.0016", "") is False


def test_cumple_criterio_con_varios_departamentos():
    assert cumple_criterio("6.26/28520.0001", {"28510", "28520"}) is True
    assert cumple_criterio("6.26/04110.0001", {"28510", "28520"}) is False


def test_fragmento_con_separadores():
    """Un fragmento más fino ("6.26/28510") también pasa la guarda: lo que
    sigue es un punto, no un dígito."""
    assert fragmento_en_codigo("6.26/28510.0016", "6.26/28510") is True
    assert fragmento_en_codigo("6.26/285100016", "6.26/28510") is False
