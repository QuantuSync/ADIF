from app.extraccion.texto import (
    VERSION_LOGICA_TEXTO,
    PaginaTexto,
    es_documento_escaneado,
    extraer_texto,
    extraer_texto_cacheado,
)
from app.models import CacheTextoDocumento
from tests import fixtures as fx


def test_documento_con_texto_normal_no_se_marca_escaneado():
    paginas = extraer_texto(fx.ANEJO_PRECIOS_GUANTES)
    assert es_documento_escaneado(paginas) is False


def test_documento_escaneado_real_se_detecta():
    # CONTEXTO.md sección 3: el único documento escaneado confirmado del
    # corpus real (100 páginas, cada una una imagen a página completa, sin
    # ningún carácter de texto ni con pdfplumber ni con pypdf).
    paginas = extraer_texto(fx.DOCUMENTO_ESCANEADO_SIN_TEXTO)
    assert es_documento_escaneado(paginas) is True


def test_documento_sin_paginas_no_se_marca_escaneado():
    # Caso distinto: sin páginas en absoluto no es "escaneado", es vacío.
    assert es_documento_escaneado([]) is False


def test_umbral_deja_margen_a_un_artefacto_suelto():
    paginas = [PaginaTexto(numero=1, texto=""), PaginaTexto(numero=2, texto="   ")]
    assert es_documento_escaneado(paginas) is True

    paginas_con_texto_real = [PaginaTexto(numero=1, texto="PLIEGO DE PRESCRIPCIONES TÉCNICAS")]
    assert es_documento_escaneado(paginas_con_texto_real) is False


# Bloque 6, sesión de rendimiento (CONTEXTO.md sección 16, `docs/sesion-2026-
# 09-12-defecto-mapeo-calidad-interfaz-rendimiento.md` bloque 4): la caché de
# texto por hash de documento -- perfilado real, ~99% del tiempo de un
# reproceso estaba aquí.


def test_extraer_texto_cacheado_no_llama_al_pdf_en_un_acierto(db_session):
    llamadas = []

    def _obtener_pdf():
        llamadas.append(1)
        return fx.ANEJO_PRECIOS_GUANTES

    primera = extraer_texto_cacheado(db_session, "hash-guantes-1", _obtener_pdf)
    segunda = extraer_texto_cacheado(db_session, "hash-guantes-1", _obtener_pdf)

    assert len(llamadas) == 1  # la segunda vez viene de la caché, no vuelve a abrir el PDF
    assert primera == segunda
    assert primera == extraer_texto(fx.ANEJO_PRECIOS_GUANTES)


def test_extraer_texto_cacheado_guarda_una_fila_por_hash(db_session):
    extraer_texto_cacheado(db_session, "hash-guantes-2", lambda: fx.ANEJO_PRECIOS_GUANTES)

    fila = db_session.get(CacheTextoDocumento, "hash-guantes-2")
    assert fila is not None
    assert fila.version_logica_texto == VERSION_LOGICA_TEXTO
    assert fila.num_paginas == len(fila.paginas)


def test_extraer_texto_cacheado_recalcula_si_la_version_cambio(db_session):
    llamadas = []

    def _obtener_pdf():
        llamadas.append(1)
        return fx.ANEJO_PRECIOS_GUANTES

    extraer_texto_cacheado(db_session, "hash-guantes-3", _obtener_pdf)
    fila = db_session.get(CacheTextoDocumento, "hash-guantes-3")
    fila.version_logica_texto = "version-vieja-de-antes-de-un-cambio-en-extraer_texto"
    db_session.commit()

    extraer_texto_cacheado(db_session, "hash-guantes-3", _obtener_pdf)

    assert len(llamadas) == 2  # la versión desactualizada no cuenta como acierto
    fila_actualizada = db_session.get(CacheTextoDocumento, "hash-guantes-3")
    assert fila_actualizada.version_logica_texto == VERSION_LOGICA_TEXTO


def test_extraer_texto_cacheado_distingue_documentos_por_hash(db_session):
    guantes = extraer_texto_cacheado(db_session, "hash-a", lambda: fx.ANEJO_PRECIOS_GUANTES)
    escaneado = extraer_texto_cacheado(db_session, "hash-b", lambda: fx.DOCUMENTO_ESCANEADO_SIN_TEXTO)

    assert guantes != escaneado
    assert db_session.get(CacheTextoDocumento, "hash-a") is not None
    assert db_session.get(CacheTextoDocumento, "hash-b") is not None
