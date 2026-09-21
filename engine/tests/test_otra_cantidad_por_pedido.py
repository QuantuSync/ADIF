"""Sesión 2026-09-21 (tercera parte), bloque 4, encargo del cliente: en los
cuadros que solo traen «cantidad mínima por pedido» y «pedido inicial», la
Cantidad no se cambia, pero la fila dice en su motivo cuál de las dos es y qué
trae la otra."""
from decimal import Decimal

from app.catalogo import construir_lineas_desde_tabla, extraer_texto_otra_cantidad, texto_otra_cantidad
from app.extraccion.mapeo_cabecera import columna_de_la_otra_cantidad
from app.extraccion.tabla import TablaExtraida

# Cabecera cacheada 89 (`6.19/28510.0126`, grifas): la Cantidad es la mínima.
CABECERA_MINIMA = [
    "Nº MATRÍCULA", "REF.\nADIF", "DESCRIPCIÓN", "NORMATIVA\nAPLICABLE", "PLANO DE\nREFERENCIA",
    "CANTIDAD\nMINIMA A\nSUMINISTRAR\nPOR PEDIDO", "PEDIDO\nINICIAL", "PRECIO DE REFERENCIA",
]
MAPEO_MINIMA = {"codigo_precio": None, "matricula": 0, "descripcion": 2, "unidad_medida": None,
                "cantidad": 5, "precio_unitario": 7}


def test_la_cantidad_es_la_minima_y_la_otra_es_el_pedido_inicial():
    assert columna_de_la_otra_cantidad(CABECERA_MINIMA, MAPEO_MINIMA) == 6


def test_la_cantidad_es_el_pedido_inicial_y_la_otra_es_la_minima():
    # Cabecera cacheada 88: el modelo dio la Cantidad al pedido inicial.
    cabecera = ["Nº\nMATRÍCULA", "REF. ADIF", "DESCRIPCIÓ\nN", "NORMATIVA\nAPLICABLE", "PLANO DE\nREFERENCIA",
                "CANTIDAD\nMÍNIMA A\nSUMINISTRAR\nPOR PEDIDO", "PEDIDO\nINICIAL", "PRECIO DE\nREFERENCIA"]
    mapeo = {**MAPEO_MINIMA, "cantidad": 6}
    assert columna_de_la_otra_cantidad(cabecera, mapeo) == 5


def test_periodo_en_vez_de_pedido_tambien_cuenta():
    cabecera = ["Nº MATRÍCULA", "REF. ADIF", "DESCRIPCIÓN", "NORMATIVA APLICABLE", "PLANO DE REFERENCIA",
                "CANTIDAD MÍNIMA A SUMINISTRAR POR PEDIDO", "PERÍODO INICIAL", "PRECIO UNITARIO DE REFERENCIA"]
    assert columna_de_la_otra_cantidad(cabecera, MAPEO_MINIMA) == 6


def test_con_cantidades_estimadas_la_cantidad_es_la_estimada_y_no_hay_nada_que_decir():
    # Cabecera cacheada 101: la Cantidad ya es la estimada de referencia.
    cabecera = ["Nº MATRÍCULA", "REF.\nADIF", "DESCRIPCIÓN", "NORMATIVA\nAPLICABLE", "PLANO DE\nREFERENCIA",
                "CANTIDAD MÍN.\nA SUMINISTRAR\nPOR PEDIDO\n(UDs)", "PEDIDO\nINICIAL\n(UDs)",
                "CANTIDADES\nESTIMADAS DE\nREFERENCIA", "PRECIO\nUNITARIO DE\nREFERENCIA"]
    assert columna_de_la_otra_cantidad(cabecera, {**MAPEO_MINIMA, "cantidad": 7, "precio_unitario": 8}) is None


def test_solo_la_minima_sin_pedido_inicial_no_dice_nada():
    cabecera = ["Nº MATRÍCULA", "DESCRIPCIÓN", "NORMATIVA APLICABLE", "PLANO DE REFERENCIA",
                "CANTIDAD MÍNIMA A SUMINISTRAR POR PEDIDO", "PRECIO DE REFERENCIA"]
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": None, "cantidad": 4,
             "precio_unitario": 5}
    assert columna_de_la_otra_cantidad(cabecera, mapeo) is None


def _tabla(filas):
    return TablaExtraida(cabecera=CABECERA_MINIMA, filas=filas, pagina=16, bbox=(0, 0, 1, 1))


def test_la_fila_dice_en_su_motivo_cual_es_y_que_trae_la_otra_sin_cambiar_la_cantidad():
    fila = ["643920160", "G3SHC95", "GRIFA PARA CABLE SUSTENTADOR", "ET 03.364.132.3", "03PPE-00301",
            "50", "200", "12,35 €"]
    otra = (6, "CANTIDAD MINIMA A SUMINISTRAR POR PEDIDO", "PEDIDO INICIAL")
    sin = construir_lineas_desde_tabla(_tabla([fila]), MAPEO_MINIMA, 1, 1, None, orden_inicial=0)
    con = construir_lineas_desde_tabla(_tabla([fila]), MAPEO_MINIMA, 1, 1, None, orden_inicial=0,
                                       otra_cantidad=otra)
    assert con[0]["cantidad"] == sin[0]["cantidad"] == Decimal("50")
    assert {k: v for k, v in con[0].items() if k != "motivo_revision"} == {
        k: v for k, v in sin[0].items() if k != "motivo_revision"
    }
    texto = extraer_texto_otra_cantidad(con[0]["motivo_revision"])
    assert texto == (
        "Cantidad: es la columna «CANTIDAD MINIMA A SUMINISTRAR POR PEDIDO» del cuadro, no la cantidad total a "
        "comprar; su columna «PEDIDO INICIAL» trae 200 en esta fila"
    )
    assert extraer_texto_otra_cantidad(sin[0]["motivo_revision"]) is None


def test_la_otra_columna_vacia_tambien_se_dice():
    assert texto_otra_cantidad("PEDIDO INICIAL", "CANTIDAD MÍNIMA POR PEDIDO", None).endswith(
        "su columna «CANTIDAD MÍNIMA POR PEDIDO» no trae ningún valor en esta fila"
    )
    assert extraer_texto_otra_cantidad(
        "otro motivo; " + texto_otra_cantidad("A", "B", None) + "; y otro"
    ) == texto_otra_cantidad("A", "B", None)


def test_en_la_pagina_de_continuacion_la_nota_sigue_aunque_la_rejilla_cambie():
    # Grifas, escaneado: la página siguiente trae una columna vacía de más al
    # principio, y el mapeo toma como Cantidad el pedido inicial.
    from app.extraccion.pipeline_anejo import _otra_cantidad_por_su_forma

    vigente = (6, (), ("CANTIDAD MINIMA A SUMINISTRAR POR PEDIDO", "PEDIDO INICIAL"), 8, 5)
    misma = [["643", "G1T", "GRIFA", "ET", "NAE", "10", "2637", "47,90 €"]]
    assert _otra_cantidad_por_su_forma(misma, {"cantidad": 5}, vigente) == (6, False)
    desplazada = [["", "643", "G1T", "GRIFA", "ET", "NAE", "10", "2637", "47,90 €"]]
    assert _otra_cantidad_por_su_forma(desplazada, {"cantidad": 7}, vigente) == (6, True)
    assert _otra_cantidad_por_su_forma(desplazada, {"cantidad": 3}, vigente) is None
    con_texto = [["", "643", "G1T", "GRIFA", "ET", "NAE", "diez", "2637", "47,90 €"]]
    assert _otra_cantidad_por_su_forma(con_texto, {"cantidad": 7}, vigente) is None
