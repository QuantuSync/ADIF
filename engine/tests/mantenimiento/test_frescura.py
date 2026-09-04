"""Bloque 1, ejecución incremental (CLAUDE.md sección 23): decisiones de
frescura sin abrir ningún documento ni tocar la cascada de extracción."""
from datetime import datetime, timezone

from app.mantenimiento.frescura import (
    VERSION_LOGICA_EXTRACCION,
    debe_descargar,
    debe_estampar_extraccion,
    debe_extraer,
    estampar_descarga_exitosa,
    estampar_extraccion,
    huella_documentos,
)
from app.models import Documento, EstadoExpediente, Expediente


def _documento(hash_: str) -> Documento:
    return Documento(
        tipo_documento="anejo", hash=hash_, nombre_archivo=f"{hash_}.pdf", ruta_almacenamiento=f"x/{hash_}.pdf",
    )


def _expediente(**kwargs) -> Expediente:
    base = dict(codigo_expediente="6.24/28510.0001")
    base.update(kwargs)
    return Expediente(**base)


def test_huella_documentos_no_depende_del_orden():
    a = huella_documentos([_documento("h1"), _documento("h2")])
    b = huella_documentos([_documento("h2"), _documento("h1")])
    assert a == b


def test_huella_documentos_cambia_si_cambia_el_conjunto():
    a = huella_documentos([_documento("h1")])
    b = huella_documentos([_documento("h1"), _documento("h2")])
    assert a != b


def test_debe_descargar_sin_documentos():
    assert debe_descargar(_expediente(), []) is True


def test_debe_descargar_con_documentos_no_redescarga():
    assert debe_descargar(_expediente(), [_documento("h1")]) is False


def test_debe_extraer_nunca_extraido():
    exp = _expediente(extraido_en=None)
    assert debe_extraer(exp, [_documento("h1")], forzar=False) is True


def test_debe_extraer_sin_documentos_se_intenta_igual():
    """Un pedido derivado de acuerdo marco sin documentos propios
    (docs/analisis-corpus.md hallazgo 3) también necesita que se intente su
    extracción: es su único camino para cruzar con el Excel de códigos."""
    exp = _expediente(extraido_en=None)
    assert debe_extraer(exp, [], forzar=False) is True


def test_debe_extraer_ya_extraido_misma_version_misma_huella_no_reextrae():
    docs = [_documento("h1"), _documento("h2")]
    exp = _expediente(
        extraido_en=datetime.now(timezone.utc),
        version_logica_extraccion=VERSION_LOGICA_EXTRACCION,
        huella_documentos=huella_documentos(docs),
    )
    assert debe_extraer(exp, docs, forzar=False) is False


def test_debe_extraer_version_distinta_reextrae():
    docs = [_documento("h1")]
    exp = _expediente(
        extraido_en=datetime.now(timezone.utc),
        version_logica_extraccion="version-vieja",
        huella_documentos=huella_documentos(docs),
    )
    assert debe_extraer(exp, docs, forzar=False) is True


def test_debe_extraer_documento_nuevo_reextrae():
    docs_antes = [_documento("h1")]
    exp = _expediente(
        extraido_en=datetime.now(timezone.utc),
        version_logica_extraccion=VERSION_LOGICA_EXTRACCION,
        huella_documentos=huella_documentos(docs_antes),
    )
    docs_ahora = [_documento("h1"), _documento("h2")]
    assert debe_extraer(exp, docs_ahora, forzar=False) is True


def test_debe_extraer_forzado_reextrae_aunque_todo_coincida():
    docs = [_documento("h1")]
    exp = _expediente(
        extraido_en=datetime.now(timezone.utc),
        version_logica_extraccion=VERSION_LOGICA_EXTRACCION,
        huella_documentos=huella_documentos(docs),
    )
    assert debe_extraer(exp, docs, forzar=True) is True


def test_debe_estampar_extraccion_estados_terminales():
    for estado in (
        EstadoExpediente.completado,
        EstadoExpediente.pendiente_revision,
        EstadoExpediente.fallido,
    ):
        assert debe_estampar_extraccion(_expediente(estado=estado)) is True


def test_debe_estampar_extraccion_excluye_esperando_matriz_y_sin_publicar():
    assert debe_estampar_extraccion(_expediente(estado=EstadoExpediente.esperando_matriz)) is False
    assert debe_estampar_extraccion(_expediente(estado=EstadoExpediente.sin_publicar)) is False


def test_estampar_descarga_exitosa(db_session):
    exp = _expediente()
    db_session.add(exp)
    db_session.commit()

    estampar_descarga_exitosa(db_session, exp)

    assert exp.descargado_en is not None


def test_estampar_extraccion(db_session):
    exp = _expediente()
    db_session.add(exp)
    db_session.commit()
    docs = [_documento("h1")]

    estampar_extraccion(db_session, exp, docs)

    assert exp.extraido_en is not None
    assert exp.version_logica_extraccion == VERSION_LOGICA_EXTRACCION
    assert exp.huella_documentos == huella_documentos(docs)
