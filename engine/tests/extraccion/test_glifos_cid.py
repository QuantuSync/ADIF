"""Bloque 2, sesión 2026-09-18 (tercera parte): cifras que llegan como
identificadores de glifo. Las cadenas de estos tests son literales del
`ANEJO_1.pdf` de `6.26/28510.0064` (p.25-26), copiadas del `fragmento` que
guardó el sistema."""
from decimal import Decimal

import pytest

from app.extraccion.glifos_cid import (
    descodificar,
    descodificar_fila,
    desplazamientos_posibles,
    tiene_glifos_cid,
)

# "11,9700 €" y "359.100,00 €" con la fuente sin ToUnicode del documento real.
_PRECIO_P1 = "(cid:1005)(cid:1005),(cid:1013)(cid:1011)(cid:1004)(cid:1004) €"
_TOTAL_P1 = "(cid:1007)(cid:1009)(cid:1013).(cid:1005)(cid:1004)(cid:1004),(cid:1004)(cid:1004) €"
# "13,5000 €" y "364.500,00 €"
_PRECIO_P2 = "(cid:1005)(cid:1007),(cid:1009)(cid:1004)(cid:1004)(cid:1004) €"
_TOTAL_P2 = "(cid:1007)(cid:1010)(cid:1008).(cid:1009)(cid:1004)(cid:1004),(cid:1004)(cid:1004) €"

_MAPEO = {"cantidad": 3, "precio_unitario": 4}


def _fila(precio, total, cantidad="30.000"):
    return ["P-1", "Balasto sobre camión en cantera", "t", cantidad, precio, total]


def test_detecta_los_glifos():
    assert tiene_glifos_cid(_PRECIO_P1) is True
    assert tiene_glifos_cid("11,97 €") is False
    assert tiene_glifos_cid(None) is False


def test_el_desplazamiento_sale_de_los_propios_identificadores():
    # Los diez dígitos presentes entre las dos celdas: un único candidato.
    assert desplazamientos_posibles([_PRECIO_P1, _TOTAL_P1]) == [1004]


def test_descodificar_traduce_cada_glifo_a_su_digito():
    assert descodificar(_PRECIO_P1, 1004) == "11,9700 €"
    assert descodificar(_TOTAL_P1, 1004) == "359.100,00 €"


def test_la_fila_se_descodifica_porque_su_aritmetica_cuadra():
    """30.000 × 11,97 = 359.100,00, que es el importe que trae la propia fila."""
    resultado = descodificar_fila(_fila(_PRECIO_P1, _TOTAL_P1), 3, 4)

    assert resultado is not None
    assert resultado.desplazamiento == 1004
    assert resultado.celdas[4] == "11,9700 €"
    assert resultado.celdas[5] == "359.100,00 €"
    assert "30.000 × 11,97 = 359.100" in resultado.comprobacion


def test_segunda_fila_real_del_mismo_cuadro():
    resultado = descodificar_fila(_fila(_PRECIO_P2, _TOTAL_P2, cantidad="27.000"), 3, 4)

    assert resultado is not None
    assert resultado.celdas[4] == "13,5000 €"


def test_sin_importe_que_lo_confirme_no_se_descodifica():
    """La regla entera: sin la cuenta que lo demuestre no se escribe ningún
    número. La fila se queda como estaba y acaba en revisión."""
    fila = ["P-1", "Balasto sobre camión en cantera", "t", "30.000", _PRECIO_P1, ""]

    assert descodificar_fila(fila, 3, 4) is None


def test_un_importe_que_no_cuadra_no_vale():
    total_falso = "(cid:1005)(cid:1004)(cid:1004),(cid:1004)(cid:1004) €"  # 100,00
    fila = _fila(_PRECIO_P1, total_falso)

    assert descodificar_fila(fila, 3, 4) is None


def test_mas_de_diez_glifos_distintos_no_son_cifras():
    """Una celda de texto en glifos (un título sin ToUnicode) no es un número:
    sus identificadores no caben en diez consecutivos."""
    texto = "".join(f"(cid:{n})" for n in range(1000, 1020))

    assert desplazamientos_posibles([texto]) == []
    assert descodificar_fila(["P-1", "x", "t", "30.000", texto, texto], 3, 4) is None


def test_sin_glifos_no_toca_nada():
    assert descodificar_fila(["P-1", "x", "t", "30.000", "11,97 €", "359.100,00 €"], 3, 4) is None


def test_sin_columna_de_precio_no_hay_nada_que_descodificar():
    assert descodificar_fila(_fila(_PRECIO_P1, _TOTAL_P1), 3, None) is None


def test_la_cantidad_desplazada_por_una_columna_fantasma_sigue_valiendo():
    """La forma real de las tablas de este documento: la cabecera llama
    CANTIDADES a la columna 4 y el valor cae en la 3. La prueba es la
    multiplicación, no la posición."""
    fila = ["P-1", "Balasto sobre camión en cantera", "t", "30.000", "", _PRECIO_P1, _TOTAL_P1]
    resultado = descodificar_fila(fila, 4, 5)

    assert resultado is not None
    assert resultado.celdas[5] == "11,9700 €"


def test_la_linea_de_catalogo_sale_con_su_precio_y_la_evidencia_literal():
    from app.catalogo import construir_linea_catalogo

    linea = construir_linea_catalogo(
        _fila(_PRECIO_P1, _TOTAL_P1),
        {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": 2,
         "cantidad": 3, "precio_unitario": 4},
        pagina=25, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0,
    )

    assert linea["precio_unitario"] == Decimal("11.9700")
    assert linea["cantidad"] == Decimal("30000")
    # El fragmento conserva el texto LITERAL del documento (la evidencia), con
    # la marca delante de que las cifras se descodificaron y con qué cuenta.
    assert "(cid:1005)" in linea["fragmento"]
    assert "cifras descodificadas de identificadores de glifo" in linea["fragmento"]
    assert "359.100" in linea["fragmento"]
    # Y no se manda a revisión: la fila se ha confirmado a sí misma.
    assert linea["motivo_revision"] is None
