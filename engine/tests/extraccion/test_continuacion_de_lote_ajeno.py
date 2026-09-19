"""Bloque 6, sesión 2026-09-19. De las 2.752 líneas que el encargo daba por
"deberían llevar lote" (causas C y D del análisis de huérfanas), medidas tabla
a tabla contra los documentos reales, prácticamente todas son la **página de
continuación del cuadro de un lote hermano**: la tabla anterior, contigua,
lleva una cabecera "LOTE N" que no está entre los lotes de este expediente, y
la siguiente no trae ningún rastro propio.

Atribuirlas al lote de este expediente metería el material del hermano en su
ficha -- exactamente el error que el bloque 3 quita de `6.22/28510.0011`-`0014`.
Así que siguen huérfanas; lo que cambia es que ahora la línea dice de qué
cuadro es, en vez de "no se encontró ninguna cabecera".
"""
from app.extraccion.lote_tabla import ResultadoAsociacionLote, asociar_lote_tabla


class _PaginaFalsa:
    """Lo mínimo que `asociar_lote_tabla` usa de una página de pdfplumber."""

    width = 600

    def __init__(self, texto_por_franja):
        self._texto = texto_por_franja

    def crop(self, caja):
        self._ultima = caja
        return self

    def extract_text(self):
        return self._texto


def _asociar(texto_banda, validos):
    return asociar_lote_tabla(
        _PaginaFalsa(texto_banda), 0.0, (0.0, 100.0, 600.0, 400.0), identificadores_validos=validos
    )


def test_la_tabla_de_un_lote_hermano_dice_de_que_lote_es():
    resultado = _asociar("ANEJO Nº 1. REFERENCIAS A SUMINISTRAR EN EL LOTE 1: ELECTRÓNICA", {"4", "5"})
    assert resultado.identificador_lote is None
    assert resultado.identificador_no_declarado == "1"
    assert resultado.elegible_para_herencia is False


def test_una_tabla_de_un_lote_propio_no_marca_ningun_lote_ajeno():
    resultado = _asociar("ANEJO Nº 4. REFERENCIAS A SUMINISTRAR EN EL LOTE 4: NOKIA", {"4", "5"})
    assert resultado.identificador_lote == "4"
    assert resultado.identificador_no_declarado is None


def test_una_franja_sin_rastro_sigue_siendo_elegible_para_herencia():
    """La página de continuación en sí no cambia: lo que cambia es lo que el
    orquestador sabe de la tabla anterior."""
    resultado = _asociar("4", {"4", "5"})
    assert resultado.identificador_lote is None
    assert resultado.elegible_para_herencia is True
    assert resultado.identificador_no_declarado is None


def test_el_campo_es_opcional_y_por_defecto_vacio():
    assert ResultadoAsociacionLote(None, None).identificador_no_declarado is None
