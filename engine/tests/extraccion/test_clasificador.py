from decimal import Decimal

from app.extraccion.clasificador import clasificar
from app.extraccion.texto import PaginaTexto, extraer_texto
from app.models import TipoDocumento
from tests import fixtures as fx


def _paginas(*textos: str) -> list[PaginaTexto]:
    return [PaginaTexto(numero=i + 1, texto=t) for i, t in enumerate(textos)]


# --- Fixtures reales -------------------------------------------------------


def test_anuncio_pcsp_con_matriz():
    r = clasificar(extraer_texto(fx.ANUNCIO_PCSP_CON_MATRIZ))
    assert r.tipo == TipoDocumento.anuncio_pcsp
    assert r.confianza >= Decimal("0.9")
    assert r.pagina == 1


def test_anuncio_pcsp_sin_matriz():
    r = clasificar(extraer_texto(fx.ANUNCIO_PCSP_SIN_MATRIZ))
    assert r.tipo == TipoDocumento.anuncio_pcsp


def test_propuesta_lc27():
    r = clasificar(extraer_texto(fx.PROPUESTA_LC27_PRECIOS_UNITARIOS))
    assert r.tipo == TipoDocumento.propuesta_lc27
    assert r.confianza >= Decimal("0.9")


def test_propuesta_lc27_ute():
    r = clasificar(extraer_texto(fx.PROPUESTA_LC27_UTE))
    assert r.tipo == TipoDocumento.propuesta_lc27


def test_resolucion_adjudicacion():
    r = clasificar(extraer_texto(fx.RESOLUCION_ADJUDICACION))
    assert r.tipo == TipoDocumento.resolucion_adjudicacion
    assert r.confianza >= Decimal("0.9")


def test_contrato():
    r = clasificar(extraer_texto(fx.CONTRATO_PRECIOS_UNITARIOS))
    assert r.tipo == TipoDocumento.contrato


def test_anejo_con_pliego_dentro_clasifica_como_pliego():
    # CLAUDE.md sección 5: por marcadores de texto, no por nombre de fichero.
    # Estos ficheros se llaman "*_ANEJO_1.pdf" en la Plataforma pero su
    # contenido es el Pliego de Prescripciones Técnicas completo (ver
    # docstring de app.extraccion.clasificador) — clasificarlos como `pliego`
    # es lo correcto, no un fallo.
    r_guantes = clasificar(extraer_texto(fx.ANEJO_PRECIOS_GUANTES))
    r_traviesas = clasificar(extraer_texto(fx.ANEJO_PRECIOS_TRAVIESAS))
    assert r_guantes.tipo == TipoDocumento.pliego
    assert r_traviesas.tipo == TipoDocumento.pliego


# --- Casos sintéticos (sin fixture PDF real en este corpus fijo) -----------


def test_pliego_documento_de_pliegos_indice():
    paginas = _paginas("Documento de Pliegos\nNúmero de Expediente 6.24/28510.0008\n")
    r = clasificar(paginas)
    assert r.tipo == TipoDocumento.pliego


def test_anejo_suelto_criterios_tecnicos():
    paginas = _paginas("CRITERIOS TÉCNICOS PARA EL SUMINISTRO DE GUANTES CONTRA RIESGO ELECTRICO\n")
    r = clasificar(paginas)
    assert r.tipo == TipoDocumento.anejo


def test_resolucion_sin_verbo_resuelve_tiene_menos_confianza():
    # Título de resolución presente, pero sin "RESUELVE" cerca: se clasifica
    # igual pero con menos confianza que la resolución "completa".
    completa = _paginas("RESOLUCIÓN DE ADJUDICACIÓN\nRESUELVE: adjudicar el contrato...")
    incompleta = _paginas("Se cita la RESOLUCIÓN DE ADJUDICACIÓN del expediente anterior.")
    r_completa = clasificar(completa)
    r_incompleta = clasificar(incompleta)
    assert r_completa.tipo == TipoDocumento.resolucion_adjudicacion
    assert r_incompleta.tipo == TipoDocumento.resolucion_adjudicacion
    assert r_completa.confianza > r_incompleta.confianza


def test_plantilla_desconocida_no_se_fuerza_a_una_familia():
    # Tercera plantilla real vista en el corpus (L9_CM.32-FE,
    # "INFORME-PROPUESTA DE ADJUDICACIÓN DE CONTRATO") que no encaja en
    # ninguna regla todavía: debe caer en `otro`, no clasificarse a la fuerza
    # como propuesta_lc27 solo porque también es una propuesta.
    paginas = _paginas(
        "L9_CM.32-FE\nINFORME-PROPUESTA DE ADJUDICACIÓN DE CONTRATO\n"
        "Denominación del Contrato: SUMINISTRO DE FUSIBLES PROTISTORES\n"
    )
    r = clasificar(paginas)
    assert r.tipo == TipoDocumento.otro
    assert r.confianza == Decimal("0")


def test_documento_vacio():
    r = clasificar([])
    assert r.tipo == TipoDocumento.otro
    assert r.pagina is None
