"""Bloque 1, ejecución incremental (CONTEXTO.md sección 23): decisiones de
frescura sin abrir ningún documento ni tocar la cascada de extracción."""
from datetime import datetime, timedelta, timezone

from app.mantenimiento.frescura import (
    VERSION_LOGICA_EXTRACCION,
    contar_lineas_catalogo,
    debe_descargar,
    debe_estampar_extraccion,
    debe_extraer,
    detectar_crecimiento_sin_cambios,
    documentos_sin_cambios,
    estampar_descarga_exitosa,
    estampar_extraccion,
    huella_documentos,
)
from app.models import Documento, EstadoExpediente, Expediente, Lote, LineaCatalogo


def _documento(hash_: str) -> Documento:
    return Documento(
        tipo_documento="anejo", hash=hash_, ruta_almacenamiento=f"x/{hash_}.pdf",
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


# --- Resumibilidad del ciclo de mantenimiento (sesión 2026-09-11): un
# `mantenimiento_ciclo` reclamado como huérfano y reintentado no debe volver
# a extraer un expediente que un intento ANTERIOR de ese mismo ciclo ya
# resolvió con éxito. ---


def test_debe_extraer_ya_resuelto_por_este_mismo_ciclo_se_salta_incluso_forzado():
    ciclo_creado_en = datetime.now(timezone.utc) - timedelta(minutes=90)
    docs = [_documento("h1")]
    exp = _expediente(
        extraido_en=datetime.now(timezone.utc) - timedelta(minutes=5),
        version_logica_extraccion=VERSION_LOGICA_EXTRACCION,
        huella_documentos=huella_documentos(docs),
    )
    assert debe_extraer(exp, docs, forzar=True, ciclo_creado_en=ciclo_creado_en) is False


def test_debe_extraer_obsoleto_desde_antes_del_ciclo_se_extrae_igual():
    ciclo_creado_en = datetime.now(timezone.utc) - timedelta(minutes=5)
    docs = [_documento("h1")]
    exp = _expediente(
        extraido_en=datetime.now(timezone.utc) - timedelta(days=30),
        version_logica_extraccion=VERSION_LOGICA_EXTRACCION,
        huella_documentos=huella_documentos(docs),
    )
    assert debe_extraer(exp, docs, forzar=True, ciclo_creado_en=ciclo_creado_en) is True


def test_debe_extraer_nunca_extraido_con_ciclo_creado_en_se_extrae():
    exp = _expediente(extraido_en=None)
    ciclo_creado_en = datetime.now(timezone.utc) - timedelta(minutes=90)
    assert debe_extraer(exp, [_documento("h1")], forzar=True, ciclo_creado_en=ciclo_creado_en) is True


def test_debe_extraer_sin_ciclo_creado_en_se_comporta_como_antes():
    docs = [_documento("h1")]
    exp = _expediente(
        extraido_en=datetime.now(timezone.utc),
        version_logica_extraccion=VERSION_LOGICA_EXTRACCION,
        huella_documentos=huella_documentos(docs),
    )
    assert debe_extraer(exp, docs, forzar=True) is True
    assert debe_extraer(exp, docs, forzar=False) is False


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


# --- Comprobación permanente de integridad del catálogo (auditoría
# 2026-09-05, docs/correccion-defectos-auditoria.md, CONTEXTO.md sección 9.9,
# encargo bloque 1 punto 4) ---


def test_documentos_sin_cambios_nunca_extraido_antes_cuenta_como_cambio():
    exp = _expediente(huella_documentos=None)
    assert documentos_sin_cambios(exp, [_documento("h1")]) is False


def test_documentos_sin_cambios_misma_huella():
    docs = [_documento("h1"), _documento("h2")]
    exp = _expediente(huella_documentos=huella_documentos(docs))
    assert documentos_sin_cambios(exp, docs) is True


def test_documentos_sin_cambios_huella_distinta():
    exp = _expediente(huella_documentos=huella_documentos([_documento("h1")]))
    assert documentos_sin_cambios(exp, [_documento("h1"), _documento("h2")]) is False


def test_detectar_crecimiento_sin_cambios_no_crece():
    assert detectar_crecimiento_sin_cambios(10, 10) is None
    assert detectar_crecimiento_sin_cambios(10, 8) is None


def test_detectar_crecimiento_sin_cambios_crece():
    aviso = detectar_crecimiento_sin_cambios(10, 14)
    assert aviso is not None
    assert "10 -> 14" in aviso


def test_contar_lineas_catalogo(db_session):
    exp = _expediente()
    db_session.add(exp)
    db_session.commit()
    lote = Lote(expediente_id=exp.id, identificador_lote="1")
    db_session.add(lote)
    db_session.commit()
    db_session.add_all(
        [
            LineaCatalogo(
                expediente_id=exp.id, lote_id=lote.id, clave_linea="P-001", orden_aparicion=0,
                descripcion="A", precio_unitario=1,
            ),
            LineaCatalogo(
                expediente_id=exp.id, lote_id=None, clave_linea="P-002", orden_aparicion=1,
                descripcion="B", precio_unitario=2,
            ),
        ]
    )
    db_session.commit()

    assert contar_lineas_catalogo(db_session, exp.id) == 2
