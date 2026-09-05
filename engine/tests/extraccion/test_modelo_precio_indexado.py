from decimal import Decimal

from app.extraccion.modelo_precio_indexado import detectar_modelo_precio_indexado
from app.extraccion.texto import PaginaTexto

# Texto real (recortado), verificado contra los tres expedientes de la
# segunda familia de baja (6.23/28510.0018, 6.23/28510.0102,
# 6.25/28510.0016), todos Acuerdo Marco de suministro de carril nuevo.
_FRAGMENTO_REAL = """
Fórmula de aplicación para el cálculo de los precios ofertados para cada pedido:
Las ofertas para cada pedido resultarán de:
a) Para el precio P-1: El cálculo del valor del carril en el momento, t, se obtiene con la
fórmula siguiente:
P-1(t)= P-1(Oferta presentada por el licitador) * Kt * Coeficiente de baja
Siendo:
Kt =0,26. Et/Eo +0,33. St/So +0,41
• Coeficiente de baja: Ofertado por el licitador para cada pedido, debe de ser un
valor menor o igual a 1.
"""


def test_detecta_marcador_y_no_hay_coeficiente_en_esta_pagina():
    resultado = detectar_modelo_precio_indexado([PaginaTexto(numero=3, texto=_FRAGMENTO_REAL)])
    assert resultado is not None
    assert resultado.pagina == 3
    assert resultado.coeficiente_transformacion is None


def test_extrae_el_coeficiente_de_transformacion_de_otra_pagina():
    pagina_adjudicacion = PaginaTexto(
        numero=1,
        texto=(
            "se eleva propuesta de adjudicación a la empresa ARCELORMITTAL ESPAÑA, S.A., "
            "con un coeficiente de transformación para el P-1 de 1,276 y con un coeficiente "
            "de transformación para P-2 a P-13 de 1,276, por un importe de adjudicar de:"
        ),
    )
    pagina_formula = PaginaTexto(numero=3, texto=_FRAGMENTO_REAL)

    resultado = detectar_modelo_precio_indexado([pagina_adjudicacion, pagina_formula])

    assert resultado is not None
    assert resultado.coeficiente_transformacion == Decimal("1.276")


def test_tolera_el_espacio_suelto_real_de_6_25_28510_0016():
    # "La oferta económica determina un coeficiente de transformación para
    # el P-1 de 1, 276" -- espacio colado por la extracción del PDF real.
    pagina = PaginaTexto(
        numero=2,
        texto=(
            "La oferta económica determina un coeficiente de transformación para el P-1 de 1, 276 "
            "y con un coeficiente de transformación para P-2 a P-13 de 1,276.\n" + _FRAGMENTO_REAL
        ),
    )
    resultado = detectar_modelo_precio_indexado([pagina])
    assert resultado is not None
    assert resultado.coeficiente_transformacion == Decimal("1.276")


def test_documento_sin_el_marcador_no_detecta_nada():
    pagina = PaginaTexto(numero=1, texto="con una baja económica del 54,00 % a precios unitarios licitados")
    assert detectar_modelo_precio_indexado([pagina]) is None
