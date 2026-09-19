"""Bloque 3, sesión 2026-09-19 (tercera parte) -- los cuadros de precios que
no publican cantidad, decisión del cliente sobre los 15 expedientes de
documentos escaneados.

Tres cambios, los tres acotados y con su contraejemplo:

1. `app.extraccion.tabla._filas_cuadro_sin_codigo` ya no exige columna de
   cantidad, y en su lugar exige la cuenta de la fila cuando el cuadro trae
   IMPORTE además de PRECIO, y un mínimo de filas cuando no trae cantidad.
2. `app.extraccion.localizador._tiene_linea_cabecera_cuadro` reconoce una
   cabecera de descripción + precio sin cantidad, con un tope de tokens para
   no casar con prosa, y se comprueba también en la rama de densidad alta.
3. El grupo de marcadores "descripcion" admite "designacion"/"denominacion",
   los otros dos nombres reales de la misma columna.
"""
from app.extraccion.localizador import (
    _tiene_linea_cabecera_cuadro,
    localizar_paginas_candidatas,
)
from app.extraccion.tabla import _filas_cuadro_sin_codigo
from app.extraccion.texto import PaginaTexto

# Cuadro real de `6.18/28510.0071` ANEJO_1 p.12 (leído por reconocimiento
# óptico): designación, plano y precio, sin cantidad ni código de precio.
CUADRO_0071 = [
    ["Designación", "Plano", "PRECIO"],
    ["ESCUADRA P/PANTALLA CUADRADA/REDONDA", "P16.4622.00", "2,27 €"],
    ["SOPORTE ANGULAR PARA PANTALLAS ROMBOIDALES", "P16.4623.00", "7,29 €"],
    ["PLETINA DE SUJECION P/CARTEL O CARTELON, L=353 a 553", "P16.4621.00", "6,50 €"],
]


def test_acepta_un_cuadro_de_designacion_plano_y_precio():
    datos = _filas_cuadro_sin_codigo(CUADRO_0071)
    assert datos is not None and len(datos) == 3


def test_con_menos_de_tres_filas_y_sin_cantidad_no_se_acepta():
    """Sin columna de cantidad la señal es más débil: dos filas de
    "descripción + importe" no se distinguen de un resumen de presupuesto."""
    assert _filas_cuadro_sin_codigo(CUADRO_0071[:3]) is None


def test_un_cuadro_de_un_solo_articulo_con_cantidad_sigue_entrando():
    """No se regresa la sesión 2026-09-15 (`3.24/28510.0027`): con columna de
    cantidad, una sola fila basta."""
    filas = [
        ["Concepto", "Cantidad", "Precio", "Total"],
        ["Compresor", "1", "18.000,00€", "18.000,00€"],
    ]
    datos = _filas_cuadro_sin_codigo(filas)
    assert datos is not None and len(datos) == 1


def test_la_fila_que_no_cuadra_con_su_importe_corta_la_tabla():
    """Condición del cliente: cuando el cuadro trae IMPORTE además de PRECIO,
    cantidad × precio tiene que dar el importe. La segunda fila no cuadra
    (3 × 10,00 = 30,00, no 99,00), así que no entra ni ella ni lo que sigue."""
    filas = [
        ["Descripción", "Cantidad", "Precio", "Importe"],
        ["Pieza buena", "2", "10,00 €", "20,00 €"],
        ["Pieza mala", "3", "10,00 €", "99,00 €"],
        ["Pieza buena tambien", "4", "10,00 €", "40,00 €"],
    ]
    datos = _filas_cuadro_sin_codigo(filas)
    assert datos is not None and len(datos) == 1
    assert datos[0][0] == "Pieza buena"


def test_sin_columna_de_importe_no_hay_nada_que_comprobar():
    filas = [
        ["Descripción", "Cantidad", "Precio"],
        ["Pieza", "2", "10,00 €"],
        ["Otra", "3", "11,00 €"],
    ]
    assert len(_filas_cuadro_sin_codigo(filas)) == 2


def test_una_tabla_sin_columna_de_precio_no_es_un_cuadro():
    filas = [
        ["Denominación", "Código"],
        ["Pantalla de anuncio", "P16.5096.00"],
        ["Cartelón indicador", "P16.5326.00"],
        ["Señal de parada", "P1D"],
    ]
    assert _filas_cuadro_sin_codigo(filas) is None


def test_el_pie_de_totales_sigue_cortando_la_tabla():
    filas = [
        ["Designación", "Plano", "PRECIO"],
        ["Pieza uno", "P1", "1,00 €"],
        ["Pieza dos", "P2", "2,00 €"],
        ["Pieza tres", "P3", "3,00 €"],
        ["TOTAL", "", "6,00 €"],
    ]
    assert len(_filas_cuadro_sin_codigo(filas)) == 3


def test_reconoce_la_cabecera_de_cuadro_sin_cantidad():
    assert _tiene_linea_cabecera_cuadro("adif\nDesignación Plano PRECIO\nESCUADRA P16.4622.00 2,27 €")


def test_la_prosa_de_un_pliego_no_es_una_cabecera_de_cuadro():
    """El tope de tokens es lo que sustituye a la exigencia de cantidad: una
    frase larga que menciona de pasada la descripción y el precio no abre la
    página."""
    prosa = (
        "Los precios unitarios de los artículos a suministrar se entenderán "
        "referidos a la descripción que figura en el presente pliego de "
        "prescripciones tecnicas y sus anejos"
    )
    assert not _tiene_linea_cabecera_cuadro(prosa)


def test_la_pagina_de_cuadro_con_densidad_alta_se_abre():
    """`6.18/28510.0071` p.12: densidad 0,26 (diez veces el umbral) y un solo
    grupo de marcadores. Antes se quedaba fuera de las candidatas."""
    texto = (
        "adif\n"
        "Designación Plano PRECIO\n"
        "ESCUADRA P/PANTALLA CUADRADA P16.4622.00 2,27 €\n"
        "SOPORTE ANGULAR PARA PANTALLAS P16.4623.00 7,29 €\n"
        "PLETINA DE SUJECION P/CARTEL P16.4621.00 6,50 €\n"
    )
    resultado = localizar_paginas_candidatas([PaginaTexto(numero=12, texto=texto)])
    assert [c.numero for c in resultado.candidatas] == [12]


def test_designacion_cuenta_como_grupo_de_descripcion():
    """`6.18/28510.0064` p.10: su cabecera es un cuadro de precios de libro y
    solo se le reconocía el grupo "precio"."""
    texto = (
        "MATRÍC. DESIGNACIÓN ACREDITACIÓN FERROVIARIA ET CRÍTICO "
        "PLANO DE REFERENCIA PRECIO DE REFERENCIA\n"
        "695200001 PARARRAYOS DE OXIDO METALICO 03.364.001.1 ALTO P16.1 350,00 €\n"
    )
    resultado = localizar_paginas_candidatas([PaginaTexto(numero=10, texto=texto)])
    assert [c.numero for c in resultado.candidatas] == [10]
