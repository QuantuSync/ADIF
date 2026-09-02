from decimal import Decimal

from app.extraccion.campos_pcsp import extraer_campos_anuncio_pcsp, importe_como_decimal
from app.extraccion.texto import extraer_texto
from tests import fixtures as fx


def test_anuncio_con_matriz_extrae_los_dos_codigos():
    # CLAUDE.md sección 7: el anuncio PCSP trae los dos códigos en campos
    # fijos — Número de Expediente y, si viene de un acuerdo marco, MATRIZ.
    paginas = extraer_texto(fx.ANUNCIO_PCSP_CON_MATRIZ)
    campos = extraer_campos_anuncio_pcsp(paginas)

    assert campos.numero_expediente.valor == "6.24/28510.0103"
    assert campos.codigo_matriz.valor == "2.18/04703.0019"
    assert importe_como_decimal(campos.importe_licitacion) == Decimal("145100")
    assert importe_como_decimal(campos.importe_adjudicacion) == Decimal("145100")
    assert campos.adjudicatario.valor == "SIEL CONFECCIONES SL"
    assert campos.objeto_contrato.valor == (
        "Pedido nº 7 acuerdo marco de suministro de equipos de protección individual. Lote "
        "2. Polos de manga corta, polos de manga larga y sudaderas de alta visibilidad"
    )

    # Trazabilidad: cada campo sabe de qué página salió (CLAUDE.md 9.10).
    assert campos.numero_expediente.pagina == 1
    assert campos.importe_licitacion.pagina == 1
    assert campos.adjudicatario.pagina == 2


def test_anuncio_sin_matriz_no_inventa_una():
    # CLAUDE.md sección 7: "El sistema nunca inventa una matriz."
    paginas = extraer_texto(fx.ANUNCIO_PCSP_SIN_MATRIZ)
    campos = extraer_campos_anuncio_pcsp(paginas)

    assert campos.codigo_matriz is None
    assert campos.numero_expediente.valor == "6.24/28510.0193"
    assert importe_como_decimal(campos.importe_licitacion) == Decimal("600000")
    assert importe_como_decimal(campos.importe_adjudicacion) == Decimal("600000")
    assert campos.adjudicatario.valor == "Enclavamientos Señaliza Ferroviaria"


def test_importe_como_decimal_de_campo_ausente_es_none():
    assert importe_como_decimal(None) is None
