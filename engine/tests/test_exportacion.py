"""Bloque 3 (CLAUDE.md): ninguna celda vacía sin explicación, trasladado al
Excel de forma sobria (texto liso entre paréntesis, sin la tipografía de la
web)."""
from app.exportacion import _celda_matricula, _celda_no_consta_si_vacio
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


def test_celda_matricula_partida_alzada_no_aplica():
    linea = _linea(descripcion="Partida alzada a justificar para imprevistos")
    assert _celda_matricula(linea) == "(no aplica)"


def test_celda_matricula_ausente_no_consta():
    linea = _linea(descripcion="BRIDA DE UNIÓN")
    assert _celda_matricula(linea) == "(no consta)"


def test_celda_no_consta_si_vacio():
    assert _celda_no_consta_si_vacio(None) == "(no consta)"
    assert _celda_no_consta_si_vacio(0) == 0
    assert _celda_no_consta_si_vacio("L01") == "L01"
