"""Bloque 2, sesión 2026-09-19 (decisión del cliente, acotada): un precio
unitario solo puede reescribirse desde la columna de importes del documento
cuando se cumplen LAS DOS condiciones a la vez.

El caso real que lo motiva es `6.17/28510.0056` p.19 (leída por reconocimiento
óptico): `P-7` trae precio 56.555,91 € e importe 451.647,28 € para 8 unidades,
y 451.647,28 / 8 = 56.455,91 -- con esa cifra el lote suma 2.975.673,96 €,
exactamente el Presupuesto de Ejecución Material que el propio cuadro declara
al pie. Las filas de abajo son las ocho reales de ese cuadro.
"""
from decimal import Decimal

import pytest

from app.catalogo import (
    CAMPO_IMPORTE,
    MARCA_PRECIO_DESDE_IMPORTE,
    MOTIVO_IMPORTE_SIN_CERRAR_EL_LOTE,
    MOTIVO_PRECIO_DESDE_IMPORTE,
    corregir_precio_con_importe_del_documento,
    importes_de_pie_de_tabla,
)
from app.extraccion.mapeo_cabecera import completar_columna_importe

# Cabecera real de `6.17/28510.0056_ANEJO_f43bcf5fce86b094.pdf` p.19.
_CABECERA = [
    "PRESUPUESTO Ref CAPÍTULO I.- SUMINISTRO DE DESVÍOS COMPLETOS",
    "UD",
    "Denominación",
    "P. Ejecución Material",
    "IMPORTE",
]
_MAPEO = {
    "codigo_precio": 0,
    "cantidad": 1,
    "descripcion": 2,
    "precio_unitario": 3,
    "matricula": None,
    "unidad_medida": None,
}
# (código, cantidad, precio impreso, importe impreso)
_FILAS_0056_LOTE_1 = [
    ("P-1", "8", "112.509,28 €", "900.074,24 €"),
    ("P-2", "14", "88.882,55 €", "1.244.355,70 €"),
    ("P-3", "1", "79.379,15 €", "79.379,15 €"),
    ("P-4", "1", "64.202,03 €", "64.202,03 €"),
    ("P-5", "2", "58.738,52 €", "117.477,04 €"),
    ("P-6", "62", "1.105,46 €", "68.538,52 €"),
    # El dígito mal leído: 451.647,28 / 8 = 56.455,91, no 56.555,91.
    ("P-7", "8", "56.555,91 €", "451.647,28 €"),
    ("P-8", "1", "50.000,00 €", "50.000,00 €"),
]
_PIE_0056_LOTE_1 = [
    ["Presupuesto de Ejecución Material", "", "", "2.975.673,96 €", ""],
    ["Gastos Generales (9%)", "", "", "267.810,66 €", ""],
    ["Beneficio Industrial (6%)", "", "", "178.540,44 €", ""],
    ["Suma", "", "", "3.422.025,06 €", ""],
    ["IVA (21%)", "", "", "718.625,26 €", ""],
    ["Presupuesto Base de Licitación", "", "", "4.140.650,32 €", ""],
]


def _linea(codigo, cantidad, precio, importe, lote="1", baja=None):
    return {
        "codigo_precio": codigo,
        "descripcion": f"material {codigo}",
        "cantidad": Decimal(cantidad),
        "precio_unitario": Decimal(precio),
        "precio_adjudicado": None,
        "baja_lote": baja,
        "importe_documento": Decimal(importe) if importe is not None else None,
        "identificador_lote": lote,
        "motivo_revision": None,
        "fragmento": f"{codigo} | {cantidad} | {precio} | {importe}",
    }


def _lineas_0056_lote_1(baja=None):
    return [
        _linea(
            codigo,
            cantidad,
            precio.replace(".", "").replace(",", ".").replace(" €", ""),
            importe.replace(".", "").replace(",", ".").replace(" €", ""),
            baja=baja,
        )
        for codigo, cantidad, precio, importe in _FILAS_0056_LOTE_1
    ]


def test_la_columna_de_importe_se_reconoce_por_su_nombre_y_solo_si_esta_libre():
    assert completar_columna_importe(_CABECERA, dict(_MAPEO))[CAMPO_IMPORTE] == 4
    # "IMPORTE UNITARIO" es un precio unitario, no el total del renglón: no
    # es esta columna (ver `_NOMBRES_COLUMNA_IMPORTE`).
    cabecera_unitario = ["Código", "Ud", "Denominación", "Precio", "Importe unitario"]
    assert completar_columna_importe(cabecera_unitario, dict(_MAPEO)).get(CAMPO_IMPORTE) is None
    # Dos candidatas: no se adivina.
    cabecera_doble = ["Código", "Ud", "Denominación", "Precio", "Importe", "Total"]
    assert completar_columna_importe(cabecera_doble, dict(_MAPEO)).get(CAMPO_IMPORTE) is None
    # La columna que ya reclama otro campo del catálogo no se roba.
    mapeo_con_importe_como_precio = {**_MAPEO, "precio_unitario": 4}
    assert completar_columna_importe(_CABECERA, mapeo_con_importe_como_precio).get(CAMPO_IMPORTE) is None


def test_los_totales_del_pie_del_cuadro_se_recogen_todos():
    mapeo = completar_columna_importe(_CABECERA, dict(_MAPEO))
    totales = importes_de_pie_de_tabla(_PIE_0056_LOTE_1, mapeo)
    assert Decimal("2975673.96") in totales
    assert Decimal("3422025.06") in totales
    assert Decimal("4140650.32") in totales


def test_0056_lote_1_corrige_el_digito_porque_cierra_el_presupuesto_de_ejecucion_material():
    lineas = _lineas_0056_lote_1()
    corregidas, solo_primera = corregir_precio_con_importe_del_documento(
        lineas, {"1": [Decimal("2975673.96"), Decimal("3422025.06")]}
    )
    assert (corregidas, solo_primera) == (1, 0)
    p7 = next(l for l in lineas if l["codigo_precio"] == "P-7")
    assert p7["precio_unitario"] == Decimal("56455.91")
    assert p7["precio_corregido_desde_importe"] is True
    assert MOTIVO_PRECIO_DESDE_IMPORTE in p7["motivo_revision"]
    assert p7["fragmento"].startswith(MARCA_PRECIO_DESDE_IMPORTE)
    # Con el precio corregido el lote suma su Presupuesto de Ejecución
    # Material al céntimo: esa es la prueba, no el parecido de la cifra.
    assert sum(l["cantidad"] * l["precio_unitario"] for l in lineas) == Decimal("2975673.96")
    # Y ninguna otra línea se toca.
    assert all(
        l.get("precio_corregido_desde_importe") is None for l in lineas if l["codigo_precio"] != "P-7"
    )
    # La marca transitoria nunca llega a la base de datos.
    assert all("importe_documento" not in l for l in lineas)


def test_el_precio_adjudicado_se_recalcula_con_el_precio_corregido():
    lineas = _lineas_0056_lote_1(baja=Decimal("0.10"))
    corregir_precio_con_importe_del_documento(lineas, {"1": [Decimal("2975673.96")]})
    p7 = next(l for l in lineas if l["codigo_precio"] == "P-7")
    assert p7["precio_adjudicado"] == Decimal("56455.91") * Decimal("0.90")


def test_sin_total_declarado_no_se_reescribe_nada_y_la_linea_va_a_revision():
    """Condición 2 incumplida: el documento no publica ningún total del lote."""
    lineas = _lineas_0056_lote_1()
    corregidas, solo_primera = corregir_precio_con_importe_del_documento(lineas, {})
    assert (corregidas, solo_primera) == (0, 1)
    p7 = next(l for l in lineas if l["codigo_precio"] == "P-7")
    assert p7["precio_unitario"] == Decimal("56555.91")
    assert p7.get("precio_corregido_desde_importe") is None
    assert MOTIVO_IMPORTE_SIN_CERRAR_EL_LOTE in p7["motivo_revision"]


def test_un_total_que_no_cuadra_tampoco_basta():
    lineas = _lineas_0056_lote_1()
    # Un céntimo de diferencia: no cuadra, no se corrige.
    corregidas, solo_primera = corregir_precio_con_importe_del_documento(
        lineas, {"1": [Decimal("2975673.97")]}
    )
    assert (corregidas, solo_primera) == (0, 1)
    assert next(l for l in lineas if l["codigo_precio"] == "P-7")["precio_unitario"] == Decimal("56555.91")


def test_sin_cantidad_en_alguna_fila_el_lote_no_se_puede_cerrar():
    """Los cuadros a los que el documento no les publica cantidad para todas
    sus filas (`6.25/28510.0097` lotes 2 y 3, `6.22/28510.0094` lote 2) no
    pueden cumplir la condición 2: no se toca ningún precio suyo."""
    lineas = _lineas_0056_lote_1()
    lineas[0]["cantidad"] = None
    corregidas, solo_primera = corregir_precio_con_importe_del_documento(
        lineas, {"1": [Decimal("2975673.96")]}
    )
    assert (corregidas, solo_primera) == (0, 1)


@pytest.mark.parametrize("cantidad, importe", [("3", "100.00"), ("7", "1.00"), ("0", "100.00")])
def test_una_division_con_residuo_no_demuestra_ningun_precio(cantidad, importe):
    """Condición 1 incumplida: `importe / cantidad` no es exacto. Redondear
    aquí sería inventar justo la cifra que esta regla existe para no
    inventar."""
    lineas = [_linea("P-1", cantidad, "1.00", importe)]
    corregidas, solo_primera = corregir_precio_con_importe_del_documento(
        lineas, {"1": [Decimal(importe)]}
    )
    assert (corregidas, solo_primera) == (0, 0)
    assert lineas[0]["precio_unitario"] == Decimal("1.00")


def test_un_precio_que_ya_cuadra_con_su_importe_no_se_toca():
    lineas = [_linea("P-1", "8", "100.00", "800.00")]
    corregidas, solo_primera = corregir_precio_con_importe_del_documento(
        lineas, {"1": [Decimal("800.00")]}
    )
    assert (corregidas, solo_primera) == (0, 0)
    assert lineas[0].get("precio_corregido_desde_importe") is None


def test_cada_lote_se_cierra_contra_su_propio_total():
    """Dos lotes en el mismo documento: el total de uno no vale para el otro."""
    lote_1 = [_linea("P-1", "2", "10.00", "30.00", lote="1")]
    lote_2 = [_linea("P-1", "2", "10.00", "50.00", lote="2")]
    corregidas, solo_primera = corregir_precio_con_importe_del_documento(
        lote_1 + lote_2, {"1": [Decimal("30.00")], "2": [Decimal("30.00")]}
    )
    assert (corregidas, solo_primera) == (1, 1)
    assert lote_1[0]["precio_unitario"] == Decimal("15.00")
    assert lote_2[0]["precio_unitario"] == Decimal("10.00")
