"""Bloque 6, sesión de comparación documento-vs-listado interno: segunda vía
de ingesta de documentos (`app.ingesta_local`), para expedientes vigentes en
el SAP del cliente que no están publicados en la Plataforma. Usa fixtures de
PDF reales (`tests/fixtures`) para probar la comprobación cruzada contra el
código declarado, no solo el nombre de carpeta."""
from __future__ import annotations

import shutil

from app.ingesta_local import codigo_expediente_desde_carpeta, ingerir_carpeta_local
from app.interfaces.document_storage import LocalDiskStorage
from app.models import Documento, DocumentoExpediente, Expediente, OrigenDocumento, TrabajoCola
from tests import fixtures as fx


def test_codigo_expediente_desde_carpeta_formato_valido():
    assert codigo_expediente_desde_carpeta("6.24_28510.0088") == "6.24/28510.0088"


def test_codigo_expediente_desde_carpeta_formato_invalido():
    assert codigo_expediente_desde_carpeta("expedientes_varios") is None
    assert codigo_expediente_desde_carpeta("6.24-28510.0088") is None


def _storage(tmp_path):
    return LocalDiskStorage(str(tmp_path / "almacen"))


def test_sin_ruta_configurada_no_hace_nada(db_session, tmp_path):
    resumen = ingerir_carpeta_local(db_session, _storage(tmp_path), None)
    assert resumen.configurado is False
    assert resumen.carpetas_leidas == 0


def test_ruta_configurada_pero_carpeta_ausente_no_hace_nada(db_session, tmp_path):
    resumen = ingerir_carpeta_local(db_session, _storage(tmp_path), str(tmp_path / "no_existe"))
    assert resumen.configurado is True
    assert resumen.carpetas_leidas == 0


def test_carpeta_sin_codigo_reconocible_se_salta(db_session, tmp_path):
    raiz = tmp_path / "entrada"
    (raiz / "documentos_varios").mkdir(parents=True)
    resumen = ingerir_carpeta_local(db_session, _storage(tmp_path), str(raiz))
    assert resumen.carpetas_leidas == 1
    assert resumen.carpetas_sin_codigo_reconocible == 1
    assert db_session.query(Expediente).count() == 0


def test_documento_sin_codigo_propio_se_enlaza_por_carpeta(db_session, tmp_path):
    # ANEJO_PRECIOS_GUANTES es un cuadro de precios real: no declara ningún
    # "Número de Expediente" ni "Contrato nº" en su texto -- el único caso
    # real y mayoritario del corpus (CONTEXTO.md sección 3), y el que más
    # importa: es justo el documento que alimenta el catálogo.
    raiz = tmp_path / "entrada"
    carpeta = raiz / "6.24_28510.0008"
    carpeta.mkdir(parents=True)
    shutil.copy(fx.ANEJO_PRECIOS_GUANTES, carpeta / "cuadro de precios.pdf")

    resumen = ingerir_carpeta_local(db_session, _storage(tmp_path), str(raiz))

    assert resumen.carpetas_leidas == 1
    assert resumen.expedientes_nuevos == 1
    assert resumen.documentos_nuevos == 1
    assert resumen.enlaces_nuevos == 1
    assert resumen.documentos_codigo_declarado_distinto == 0
    assert resumen.expedientes_reencolados == 1

    expediente = db_session.query(Expediente).filter_by(codigo_expediente="6.24/28510.0008").one()
    assert expediente.aviso_ingesta_manual is None
    documento = db_session.query(Documento).one()
    assert documento.origen == OrigenDocumento.manual
    enlace = db_session.query(DocumentoExpediente).one()
    assert enlace.nombre_archivo == "cuadro de precios.pdf"
    assert db_session.query(TrabajoCola).filter_by(tipo="extraer_expediente", expediente_id=expediente.id).count() == 1


def test_reprocesar_la_misma_carpeta_no_duplica_nada(db_session, tmp_path):
    raiz = tmp_path / "entrada"
    carpeta = raiz / "6.24_28510.0008"
    carpeta.mkdir(parents=True)
    shutil.copy(fx.ANEJO_PRECIOS_GUANTES, carpeta / "cuadro de precios.pdf")
    storage = _storage(tmp_path)

    ingerir_carpeta_local(db_session, storage, str(raiz))
    resumen_2 = ingerir_carpeta_local(db_session, storage, str(raiz))

    assert resumen_2.expedientes_nuevos == 0
    assert resumen_2.expedientes_existentes == 1
    assert resumen_2.documentos_nuevos == 0
    assert resumen_2.documentos_ya_conocidos == 1
    assert resumen_2.enlaces_nuevos == 0
    assert resumen_2.expedientes_reencolados == 0  # nada nuevo, no se vuelve a encolar
    assert db_session.query(Documento).count() == 1
    assert db_session.query(DocumentoExpediente).count() == 1
    assert db_session.query(TrabajoCola).count() == 1  # solo el de la primera pasada


def test_expediente_ya_existente_recibe_documento_nuevo(db_session, tmp_path):
    expediente = Expediente(codigo_expediente="6.24/28510.0008")
    db_session.add(expediente)
    db_session.commit()

    raiz = tmp_path / "entrada"
    carpeta = raiz / "6.24_28510.0008"
    carpeta.mkdir(parents=True)
    shutil.copy(fx.ANEJO_PRECIOS_GUANTES, carpeta / "cuadro de precios.pdf")

    resumen = ingerir_carpeta_local(db_session, _storage(tmp_path), str(raiz))

    assert resumen.expedientes_nuevos == 0
    assert resumen.expedientes_existentes == 1
    assert resumen.documentos_nuevos == 1
    assert db_session.query(Expediente).count() == 1  # no se duplica la fila del expediente


def test_documento_declara_codigo_distinto_al_de_su_carpeta_no_se_enlaza(db_session, tmp_path):
    # Caso real que motiva la comprobación cruzada (CONTEXTO.md sección 20):
    # ANUNCIO_PCSP_CON_MATRIZ se archivó bajo la carpeta de su MATRIZ
    # ("2.18_04703.0019") pero su propio "Número de Expediente" declarado es
    # "6.24/28510.0103" -- exactamente la trampa que una carpeta mal puesta
    # por la macro del cliente podría reproducir.
    raiz = tmp_path / "entrada"
    carpeta = raiz / "2.18_04703.0019"
    carpeta.mkdir(parents=True)
    shutil.copy(fx.ANUNCIO_PCSP_CON_MATRIZ, carpeta / "anuncio.pdf")

    resumen = ingerir_carpeta_local(db_session, _storage(tmp_path), str(raiz))

    assert resumen.expedientes_nuevos == 1
    assert resumen.documentos_nuevos == 0
    assert resumen.enlaces_nuevos == 0
    assert resumen.documentos_codigo_declarado_distinto == 1
    assert resumen.expedientes_reencolados == 0
    assert db_session.query(Documento).count() == 0  # no se guarda el fichero sin resolver el conflicto

    expediente = db_session.query(Expediente).filter_by(codigo_expediente="2.18/04703.0019").one()
    assert expediente.aviso_ingesta_manual is not None
    assert "6.24/28510.0103" in expediente.aviso_ingesta_manual


def test_documento_declara_el_mismo_codigo_de_su_carpeta_se_enlaza(db_session, tmp_path):
    raiz = tmp_path / "entrada"
    carpeta = raiz / "6.24_28510.0103"
    carpeta.mkdir(parents=True)
    shutil.copy(fx.ANUNCIO_PCSP_CON_MATRIZ, carpeta / "anuncio.pdf")

    resumen = ingerir_carpeta_local(db_session, _storage(tmp_path), str(raiz))

    assert resumen.documentos_nuevos == 1
    assert resumen.enlaces_nuevos == 1
    assert resumen.documentos_codigo_declarado_distinto == 0
    expediente = db_session.query(Expediente).filter_by(codigo_expediente="6.24/28510.0103").one()
    assert expediente.aviso_ingesta_manual is None


def test_aviso_de_ingesta_se_limpia_si_la_pasada_siguiente_ya_no_encuentra_nada(db_session, tmp_path):
    # Mismo criterio que motivó el bloque 2 de esta sesión (motivo_revision):
    # un aviso calculado en una pasada no debe quedarse pegado si la
    # siguiente pasada ya no tiene nada que decir.
    raiz = tmp_path / "entrada"
    carpeta = raiz / "2.18_04703.0019"
    carpeta.mkdir(parents=True)
    shutil.copy(fx.ANUNCIO_PCSP_CON_MATRIZ, carpeta / "anuncio.pdf")
    storage = _storage(tmp_path)
    ingerir_carpeta_local(db_session, storage, str(raiz))
    expediente = db_session.query(Expediente).filter_by(codigo_expediente="2.18/04703.0019").one()
    assert expediente.aviso_ingesta_manual is not None

    (carpeta / "anuncio.pdf").unlink()
    shutil.copy(fx.ANEJO_PRECIOS_GUANTES, carpeta / "otro_documento.pdf")

    ingerir_carpeta_local(db_session, storage, str(raiz))

    db_session.refresh(expediente)
    assert expediente.aviso_ingesta_manual is None


def test_ficheros_no_pdf_se_ignoran(db_session, tmp_path):
    raiz = tmp_path / "entrada"
    carpeta = raiz / "6.24_28510.0008"
    carpeta.mkdir(parents=True)
    (carpeta / "notas.txt").write_text("no es un pdf")

    resumen = ingerir_carpeta_local(db_session, _storage(tmp_path), str(raiz))

    assert resumen.expedientes_nuevos == 1
    assert resumen.documentos_nuevos == 0
    assert resumen.enlaces_nuevos == 0
