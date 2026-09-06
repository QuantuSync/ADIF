"""CLAUDE.md, encargo de esta sesión (Excel al cliente), punto 1: ninguna
convención de marcador de texto de la web viaja al Excel -- celda vacía en
su lugar, para no convertir una columna numérica en texto mixto."""
from app.exportacion import _categoria_motivo, _celda_matricula, _celda_numero, _celda_texto
from app.models import LineaCatalogo


def _linea(**kwargs) -> LineaCatalogo:
    base = dict(
        expediente_id=1, clave_linea="P-001", orden_aparicion=0,
        descripcion="BRIDA DE UNIÓN", matricula=None,
    )
    base.update(kwargs)
    return LineaCatalogo(**base)


def test_celda_matricula_presente():
    assert _celda_matricula(_linea(matricula="601020180")) == "601020180"


def test_celda_matricula_partida_alzada_vacia():
    linea = _linea(descripcion="Partida alzada a justificar para imprevistos")
    assert _celda_matricula(linea) is None


def test_celda_matricula_ausente_vacia():
    linea = _linea(descripcion="BRIDA DE UNIÓN")
    assert _celda_matricula(linea) is None


def test_celda_texto_vacio_es_none():
    assert _celda_texto(None) is None
    assert _celda_texto("") is None
    assert _celda_texto("L01") == "L01"


def test_celda_numero_vacio_es_none():
    assert _celda_numero(None) is None


def test_celda_numero_devuelve_float():
    from decimal import Decimal
    assert _celda_numero(Decimal("0")) == 0.0
    assert _celda_numero(Decimal("12.5")) == 12.5


# Encargo de esta sesión: agrupar el motivo de las huérfanas excluidas del
# Excel en un puñado de categorías legibles (docstring de
# `app.extraccion.lote_tabla`, mismas cuatro redacciones reales).


def test_categoria_motivo_banda_vacia():
    motivo = "banda vacía: posible continuación de tabla partida entre páginas, sin inferir"
    assert _categoria_motivo(motivo) == "banda vacía: posible continuación de tabla partida entre páginas"


def test_categoria_motivo_varias_cabeceras():
    motivo = "varias cabeceras de lote en la franja que precede a esta tabla: ['2', '4']"
    assert _categoria_motivo(motivo) == "varias cabeceras de lote en la misma franja"


def test_categoria_motivo_ninguna_cabecera():
    motivo = "ninguna cabecera LOTE N encontrada en la franja que precede a esta tabla"
    assert _categoria_motivo(motivo) == "ninguna cabecera de lote reconocible en la franja"


def test_categoria_motivo_lote_no_declarado():
    motivo = "la tabla se asocia al LOTE 9, que no está entre los lotes declarados del expediente"
    assert _categoria_motivo(motivo) == "la tabla declara un lote no registrado en el expediente"


def test_categoria_motivo_sin_registrar():
    assert _categoria_motivo(None) == "(sin motivo registrado)"


def test_categoria_motivo_desconocido_cae_en_otro():
    assert _categoria_motivo("una redacción nueva que no existía todavía") == "otro motivo de ambigüedad"
