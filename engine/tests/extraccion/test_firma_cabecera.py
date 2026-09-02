from app.extraccion.firma_cabecera import calcular_firma_cabecera


def test_misma_cabecera_misma_firma():
    a = calcular_firma_cabecera(["Código de Precio", "Descripción", "Precio Unitario"])
    b = calcular_firma_cabecera(["código de precio", "descripción", "precio unitario"])
    assert a == b


def test_cabecera_distinta_firma_distinta():
    a = calcular_firma_cabecera(["Código de Precio", "Descripción", "Precio Unitario"])
    b = calcular_firma_cabecera(["Código de Precio", "Descripción", "Precio de Referencia"])
    assert a != b


def test_orden_de_columnas_importa():
    a = calcular_firma_cabecera(["Código", "Descripción"])
    b = calcular_firma_cabecera(["Descripción", "Código"])
    assert a != b


def test_columna_fantasma_none_no_rompe_la_firma():
    a = calcular_firma_cabecera(["Código", None, "Descripción"])
    b = calcular_firma_cabecera(["Código", "", "Descripción"])
    assert a == b
