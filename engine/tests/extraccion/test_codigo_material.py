from app.extraccion.codigo_material import derivar_codigo_material


def test_deriva_del_sustantivo_principal():
    assert derivar_codigo_material("BRIDA PARA JUNTA ORDINARIA. 42,5 KG/M") == "BRIDA"
    assert derivar_codigo_material("GUANTE CONTRA RIESGO ELECTRICO.") == "GUANTE"


def test_sin_vocabulario_conocido_no_inventa():
    assert derivar_codigo_material("CONTADOR DE EJES") is None


def test_descripcion_vacia_no_revienta():
    assert derivar_codigo_material("") is None
