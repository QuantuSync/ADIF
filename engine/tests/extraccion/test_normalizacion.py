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


def test_identificadores_de_glifo_sin_decodificar_es_error_claro():
    # Sesión de rodaje 2026-09-03, expediente 6.25/28510.0028: una fuente sin
    # ToUnicode hace que pdfplumber devuelva "(cid:1004)..." en vez de
    # dígitos. Sin esta comprobación, los dígitos del propio identificador
    # cuelan como si fueran el número real y producen un valor absurdo.
    with pytest.raises(ValueError, match="identificadores de glifo"):
        parsear_numero_es("(cid:1004)(cid:853)(cid:1005)(cid:1009)(cid:1008)(cid:1004)(cid:3)(cid:934)")


def test_valor_duplicado_con_salto_de_linea_se_colapsa_si_coincide():
    # Expediente 6.23/28510.0051: una celda mal extraída trae el mismo
    # importe repetido, separado por un salto de línea. Dos comas en el
    # mismo literal rompen el reparto entero/decimales si no se colapsa antes.
    assert parsear_importe_es("306.351,49 €\n306.351,49 €") == Decimal("306351.49")


def test_valor_duplicado_que_no_coincide_sigue_siendo_error():
    # Si las dos líneas no coinciden, no se adivina cuál es la buena: el
    # parseo debe seguir fallando para que el llamador la mande a revisión.
    with pytest.raises(ValueError):
        parsear_numero_es("306.351,49\n412.000,00")
