from decimal import Decimal

from app.extraccion.campos_pcsp import CampoAnclado, extraer_campos_anuncio_pcsp, importe_como_decimal
from app.extraccion.invalidado import INVALIDADO
from app.extraccion.texto import PaginaTexto, extraer_texto
from tests import fixtures as fx


def test_anuncio_con_matriz_extrae_los_dos_codigos():
    # CONTEXTO.md sección 7: el anuncio PCSP trae los dos códigos en campos
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

    # Trazabilidad: cada campo sabe de qué página salió (CONTEXTO.md 9.10).
    assert campos.numero_expediente.pagina == 1
    assert campos.importe_licitacion.pagina == 1
    assert campos.adjudicatario.pagina == 2


def test_tipo_contrato_ausente_en_pedido_derivado_no_revienta():
    # CONTEXTO.md sección 26, criterio del cliente sobre obra: este fixture real
    # es un pedido derivado de acuerdo marco (CONTEXTO.md sección 20) -- declara
    # "Sistema de Contratación: Contrato basado en un Acuerdo Marco", no el
    # campo "Tipo de Contrato" de un anuncio de licitación directa. Ausente es
    # el resultado correcto aquí, no un fallo del patrón (ver el caso
    # sintético de más abajo para el campo cuando sí aparece).
    campos = extraer_campos_anuncio_pcsp(extraer_texto(fx.ANUNCIO_PCSP_CON_MATRIZ))
    assert campos.tipo_contrato is None


def test_matriz_por_identificador_contrato_original_cuando_falta_la_forma_estricta():
    # Sesión de descubrimiento inverso, caso real `6.26/28510.0014`: ni el
    # Anuncio de adjudicación ni el de formalización de este pedido traían
    # la sección "Licitación basada en el acuerdo marco" (verificado contra
    # los dos documentos reales) — solo "Identificador contrato original",
    # en "Proceso de Licitación", con el mismo dato. Sin este fallback la
    # matriz quedaba sin extraer aunque el documento sí la declarara.
    texto = (
        "Número de Expediente 6.26/28510.0014\n"
        "Sistema de Contratación Contrato basado en un Acuerdo Marco\n"
        "Proceso de Licitación\n"
        "Identificador contrato original 6.25/28510.0016\n"
        "Procedimiento Abierto\n"
    )
    campos = extraer_campos_anuncio_pcsp([PaginaTexto(numero=1, texto=texto)])

    assert campos.codigo_matriz.valor == "6.25/28510.0016"


def test_forma_estricta_manda_sobre_la_alternativa_si_ambas_aparecen():
    # Verificado también contra un documento real (`6.24/28510.0040`): los
    # dos campos coinciden cuando ambos aparecen, pero por si algún día no
    # coincidieran, la forma estricta (más específica, dedicada a este dato)
    # es la que manda -- nunca la alternativa en silencio.
    texto = (
        "Licitación basada en el acuerdo marco\n"
        "Expediente 6.23/28510.0018\n"
        "Proceso de Licitación\n"
        "Identificador contrato original 6.23/28510.0018\n"
    )
    campos = extraer_campos_anuncio_pcsp([PaginaTexto(numero=1, texto=texto)])

    assert campos.codigo_matriz.valor == "6.23/28510.0018"


def test_anuncio_sin_matriz_no_inventa_una():
    # CONTEXTO.md sección 7: "El sistema nunca inventa una matriz."
    paginas = extraer_texto(fx.ANUNCIO_PCSP_SIN_MATRIZ)
    campos = extraer_campos_anuncio_pcsp(paginas)

    assert campos.codigo_matriz is None
    assert campos.numero_expediente.valor == "6.24/28510.0193"
    assert importe_como_decimal(campos.importe_licitacion) == Decimal("600000")
    assert importe_como_decimal(campos.importe_adjudicacion) == Decimal("600000")
    assert campos.adjudicatario.valor == "Enclavamientos Señaliza Ferroviaria"


def test_importe_como_decimal_de_campo_ausente_es_none():
    assert importe_como_decimal(None) is None


def test_importe_como_decimal_no_interpretable_degrada_a_invalidado():
    # Bloque 3, sesión 2026-09-10: expediente real 6.20/28510.0062 del
    # reproceso completo -- un literal encontrado por la etiqueta fija pero
    # que `parsear_numero_es` rechaza (agrupación de miles inválida) no debe
    # propagar la excepción y tumbar el expediente entero (CONTEXTO.md
    # sección 12), sin try/except alrededor de esta llamada en el
    # orquestador.
    campo = CampoAnclado(valor="1.10", pagina=3, fragmento="Importe: 1.10")

    assert importe_como_decimal(campo) is INVALIDADO


def test_importe_como_decimal_invalidado_pasa_tal_cual():
    assert importe_como_decimal(INVALIDADO) is INVALIDADO


def test_numero_lotes_en_anuncio_sin_desglose_por_lote():
    # Sesión de identidad de lote (CONTEXTO.md sección 27): 6.23/28510.0139 es
    # el caso más peligroso -- "Nº de Lotes: 2" confirma que la licitación
    # tiene 2 lotes, pero este mismo documento nunca desglosa cuál es cuál
    # (eso vive, si vive en algún sitio, en una Propuesta LC.27 o Resolución
    # que este expediente no tiene). Este campo es la única fuente de
    # "cuántos lotes" para ese caso.
    campos = extraer_campos_anuncio_pcsp(extraer_texto(fx.ANUNCIO_PCSP_DOS_LOTES_SIN_DESGLOSE))
    assert campos.numero_lotes.valor == "2"


def test_tipo_contrato_obras_sintetico():
    # Sin fixture PDF real con "Tipo de Contrato Obras" en este corpus
    # (CONTEXTO.md sección 26: el único departamento visto, 28510, es
    # "Suministros") -- caso sintético para no dejar la rama sin probar.
    from app.extraccion.texto import PaginaTexto

    paginas = [PaginaTexto(numero=1, texto="Número de Expediente 6.24/28510.9999\nTipo de Contrato Obras\n")]
    campos = extraer_campos_anuncio_pcsp(paginas)
    assert campos.tipo_contrato.valor == "Obras"
