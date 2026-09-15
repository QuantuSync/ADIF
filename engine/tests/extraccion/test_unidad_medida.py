import pytest

from app.extraccion.unidad_medida import es_unidad_conocida, limpiar_unidad


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
