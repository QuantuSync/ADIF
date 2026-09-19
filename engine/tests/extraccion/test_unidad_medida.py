import pytest

from app.extraccion.unidad_medida import es_unidad_conocida, limpiar_unidad, normalizar_unidad


# Los 36 valores del catálogo real (barrido de la sesión 2026-09-15, cuarta
# parte) que sí son unidades.
@pytest.mark.parametrize("valor", [
    "UD.", "UN", "€/UD", "ud", "UD", "M", "Kg", "t", "T", "m", "Ud.", "Txkm", "t x km", "€/transporte",
    "PA", "€/Ton", "KG", "m3", "€/m", "m³", "€/h", "€/Ton*mes", "€/Ton*km", "m3xkm", "dm3**", "DM3",
    "UD/día", "m²", "dm3", "Hora", "Mes", "Elemento x mes", "P", "h.", "Unidad", "UNIDAD",
])
def test_unidades_del_corpus(valor):
    assert es_unidad_conocida(valor)


@pytest.mark.parametrize("valor", [
    "Fibra monomodo", "Fibra monomodo Fibra monomodo", "Precio mensual", "ud ud ud",
    "03PAI-032-01", "DIN 934", "1.000,00 €", "956", "", "€/", "001", "Mixto",
])
def test_lo_que_no_es_una_unidad(valor):
    assert not es_unidad_conocida(valor)


@pytest.mark.parametrize("valor, esperado", [
    ("€/UD", "UD"), ("€/Ton*km", "Ton*km"), ("€ / h", "h"), ("€/transporte", "transporte"),
    ("dm3**", "dm3"), ("dm3", "dm3"), ("UD.", "UD."), ("€/", None), ("**", None),
])
def test_limpiar_unidad(valor, esperado):
    assert limpiar_unidad(valor) == esperado


def test_unidades_del_maestro_de_sap():
    for valor in ("UN", "M", "KG", "PAA", "L", "P", "CJ", "BTO", "M3", "LC", "ROL", "T", "CA", "TS", "CAR",
                  "M-2", "UTR"):
        assert es_unidad_conocida(valor), valor


# Sesión 2026-09-16 (noche): los valores del catálogo real, a su forma única.
@pytest.mark.parametrize("valor, esperado", [
    ("UD.", "ud"), ("UN", "ud"), ("UD", "ud"), ("ud", "ud"), ("Ud.", "ud"), ("Unidad", "ud"),
    ("M", "m"), ("m", "m"), ("Kg", "kg"), ("KG", "kg"),
    ("t", "t"), ("T", "t"), ("Ton", "t"),
    ("Txkm", "t·km"), ("t x km", "t·km"), ("Ton*km", "t·km"), ("TXKM", "t·km"),
    ("Ton*mes", "t·mes"), ("m3xkm", "m3·km"), ("UD/día", "ud/día"),
    ("m3", "m3"), ("m³", "m3"), ("m²", "m2"), ("dm3", "dm3"), ("DM3", "dm3"),
    ("h", "h"), ("Hora", "h"), ("h.", "h"), ("Mes", "mes"), ("Elemento x mes", "elemento·mes"),
])
def test_normalizar_unidad_a_su_forma_unica(valor, esperado):
    assert normalizar_unidad(valor) == esperado


@pytest.mark.parametrize("valor", ["PA", "P", "transporte", "PAA", "CJ", "pieza"])
def test_normalizar_unidad_no_inventa_equivalencias(valor):
    # "PA" no es "ud", "P" y los códigos de SAP no tienen nombre completo,
    # "pieza" no se da por "ud".
    assert normalizar_unidad(valor) == valor


# Sesión 2026-09-19 (séptima parte, bloque 3): "ml" SÍ se unifica. La duda era
# "metro lineal o mililitro" y el corpus la deshace -- las tres líneas que la
# traen son obra civil medida a lo largo en un cuadro que usa m3 y m2 al lado
# (`6.17/28510.0007` p.20). Ver el docstring de `app.extraccion.unidad_medida`.
@pytest.mark.parametrize("valor", ["Ml", "ML", "ml", "m.l."])
def test_metro_lineal_se_unifica_con_metro(valor):
    assert normalizar_unidad(valor) == "m"


def test_normalizar_unidad_es_idempotente():
    for valor in ("UD.", "Txkm", "UD/día", "m³", "PA", "Elemento x mes"):
        assert normalizar_unidad(normalizar_unidad(valor)) == normalizar_unidad(valor)
