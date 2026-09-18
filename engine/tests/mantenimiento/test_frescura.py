"""Bloque 1, ejecución incremental (CONTEXTO.md sección 23): decisiones de
frescura sin abrir ningún documento ni tocar la cascada de extracción."""
from datetime import datetime, timedelta, timezone

import pytest

from app.mantenimiento.frescura import (
    VERSION_LOGICA_BUSQUEDA,
    VERSION_LOGICA_EXTRACCION,
    anio_del_codigo,
    contar_lineas_catalogo,
    debe_descargar,
    debe_estampar_extraccion,
    debe_extraer,
    debe_rebuscar_sin_publicar,
    detectar_crecimiento_sin_cambios,
    documentos_sin_cambios,
    estampar_descarga_exitosa,
    estampar_extraccion,
    huella_documentos,
    plazo_sin_publicar,
    sin_publicar_confirmado,
    sin_publicar_reintento_desde,
)
from app.models import Documento, EstadoExpediente, Expediente, Lote, LineaCatalogo
from app.schemas import ExpedienteOut


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


# --- Sesión 2026-09-15: `sin_publicar` deja de ser definitivo.

_PLAZO = timedelta(days=14)
_AHORA = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


def _sin_publicar(en=None, version=None) -> Expediente:
    return _expediente(
        estado=EstadoExpediente.sin_publicar, sin_publicar_en=en, sin_publicar_version_busqueda=version,
    )


def test_sin_publicar_confirmado_solo_con_la_version_de_busqueda_vigente():
    assert sin_publicar_confirmado(_sin_publicar(_AHORA, VERSION_LOGICA_BUSQUEDA)) is True
    # Negativo de antes del arreglo del 2026-09-07 (sin versión) u otra versión.
    assert sin_publicar_confirmado(_sin_publicar(_AHORA, None)) is False
    assert sin_publicar_confirmado(_sin_publicar(_AHORA, "anterior")) is False
    # Ni siquiera aplica a un expediente que no está sin publicar.
    assert sin_publicar_confirmado(_expediente(sin_publicar_version_busqueda=VERSION_LOGICA_BUSQUEDA)) is False


def test_sin_publicar_confirmado_se_rebusca_pasado_el_plazo():
    reciente = _sin_publicar(_AHORA - timedelta(days=13), VERSION_LOGICA_BUSQUEDA)
    vencido = _sin_publicar(_AHORA - timedelta(days=14), VERSION_LOGICA_BUSQUEDA)

    assert debe_rebuscar_sin_publicar(reciente, _PLAZO, _AHORA) is False
    assert sin_publicar_reintento_desde(reciente, _PLAZO) == _AHORA + timedelta(days=1)
    assert debe_rebuscar_sin_publicar(vencido, _PLAZO, _AHORA) is True


def test_sin_publicar_sin_confirmar_se_rebusca_en_seguida():
    # Marcado hace un minuto, pero con la búsqueda que confundía un bloqueo
    # con "no publicado": no espera ningún plazo.
    assert debe_rebuscar_sin_publicar(_sin_publicar(_AHORA - timedelta(minutes=1), None), _PLAZO, _AHORA) is True
    # Sin fecha: tampoco.
    assert debe_rebuscar_sin_publicar(_sin_publicar(None, VERSION_LOGICA_BUSQUEDA), _PLAZO, _AHORA) is True


def test_fecha_sin_huso_se_lee_como_utc():
    # SQLite devuelve las fechas sin huso.
    exp = _sin_publicar(datetime(2026, 9, 1, 12, 0), VERSION_LOGICA_BUSQUEDA)
    assert debe_rebuscar_sin_publicar(exp, _PLAZO, _AHORA) is True


def test_solo_se_rebusca_lo_que_esta_sin_publicar():
    assert debe_rebuscar_sin_publicar(_expediente(estado=EstadoExpediente.fallido), _PLAZO, _AHORA) is False
    assert sin_publicar_reintento_desde(_expediente(estado=EstadoExpediente.completado), _PLAZO) is None


def test_api_distingue_negativo_confirmado_y_de_antes(db_session):
    # Expediente de 2024 a propósito: con uno del año en curso el plazo es el
    # corto (`plazo_sin_publicar`) y este test dependería del año en que se
    # ejecute. El plazo corto tiene sus propios tests, más abajo.
    confirmado = _expediente(
        codigo_expediente="6.24/28510.0101", estado=EstadoExpediente.sin_publicar,
        sin_publicar_en=datetime(2026, 9, 15, tzinfo=timezone.utc), sin_publicar_version_busqueda=VERSION_LOGICA_BUSQUEDA,
    )
    de_antes = _expediente(
        codigo_expediente="6.24/28510.0102", estado=EstadoExpediente.sin_publicar,
        sin_publicar_en=datetime(2026, 9, 7, 17, 17, tzinfo=timezone.utc),
    )
    normal = _expediente(codigo_expediente="6.24/28510.0103", estado=EstadoExpediente.completado)
    db_session.add_all([confirmado, de_antes, normal])
    db_session.commit()

    salida = {e.codigo_expediente: ExpedienteOut.model_validate(e).model_dump() for e in (confirmado, de_antes, normal)}

    assert salida["6.24/28510.0101"]["sin_publicar_confirmado"] is True
    assert salida["6.24/28510.0101"]["sin_publicar_reintento_desde"] == datetime(2026, 9, 29, tzinfo=timezone.utc)
    assert salida["6.24/28510.0102"]["sin_publicar_confirmado"] is False
    assert salida["6.24/28510.0102"]["sin_publicar_reintento_desde"].replace(tzinfo=timezone.utc) == datetime(
        2026, 9, 7, 17, 17, tzinfo=timezone.utc
    )
    assert salida["6.24/28510.0103"]["sin_publicar_confirmado"] is None
    assert salida["6.24/28510.0103"]["sin_publicar_reintento_desde"] is None


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
    exp = _expediente(
        huella_documentos=huella_documentos(docs),
        version_logica_extraccion=VERSION_LOGICA_EXTRACCION,
    )
    assert documentos_sin_cambios(exp, docs) is True


def test_documentos_sin_cambios_huella_distinta():
    exp = _expediente(
        huella_documentos=huella_documentos([_documento("h1")]),
        version_logica_extraccion=VERSION_LOGICA_EXTRACCION,
    )
    assert documentos_sin_cambios(exp, [_documento("h1"), _documento("h2")]) is False


def test_documentos_sin_cambios_con_logica_de_extraccion_nueva():
    """Sesión 2026-09-16: los documentos son los mismos pero la cascada ya no
    los lee igual. Crecer es lo esperado, no una duplicación -- si esto
    devolviera `True`, `app.worker.procesar_extraer_expediente` marcaría con
    un `error` de "posible duplicación" justo a los expedientes que un
    arreglo acaba de recuperar (pasó de verdad con `6.26/28510.0004`,
    `6.23/28510.0034` y `6.24/28510.0048`)."""
    docs = [_documento("h1"), _documento("h2")]
    exp = _expediente(
        huella_documentos=huella_documentos(docs),
        version_logica_extraccion="2026-01-01.viejo",
    )
    assert documentos_sin_cambios(exp, docs) is False


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


# --- Sesión 2026-09-18 (tercera parte): el plazo depende del año ------------


@pytest.mark.parametrize(
    "codigo, esperado",
    [
        ("6.26/28510.0057", 2026),
        ("2.24/04110.0036", 2024),
        ("19/28510", 2019),          # forma inusual, año delante sin punto
        ("28510/2023", 2023),        # forma inusual, año detrás
        ("28510Z/2018", 2018),
        ("2.26/28510.5002/01", 2026),
        ("28510", None),             # sin año legible: no se adivina
        ("", None),
        (None, None),
    ],
)
def test_anio_del_codigo(codigo, esperado):
    assert anio_del_codigo(codigo) == esperado


def test_el_expediente_del_anio_en_curso_se_rebusca_con_el_plazo_corto():
    """El caso real: `6.26/28510.0057` se buscó el 16/09 y no estaba; el 18/09
    ya estaba publicado. Con catorce días se habría encontrado el 30/09."""
    reciente = _sin_publicar(_AHORA - timedelta(days=4), VERSION_LOGICA_BUSQUEDA)
    reciente.codigo_expediente = "6.26/28510.0057"

    assert plazo_sin_publicar(reciente, _PLAZO, _AHORA) == timedelta(days=3)
    assert debe_rebuscar_sin_publicar(reciente, _PLAZO, _AHORA) is True


def test_el_expediente_viejo_sigue_con_el_plazo_largo():
    """Cada búsqueda evitada cuenta contra una Plataforma lenta: uno de 2014
    lleva una década sin publicarse y no merece una búsqueda cada tres días."""
    viejo = _sin_publicar(_AHORA - timedelta(days=4), VERSION_LOGICA_BUSQUEDA)
    viejo.codigo_expediente = "6.14/28510.0126"

    assert plazo_sin_publicar(viejo, _PLAZO, _AHORA) == _PLAZO
    assert debe_rebuscar_sin_publicar(viejo, _PLAZO, _AHORA) is False


def test_el_del_anio_anterior_tambien_cuenta_como_reciente():
    del_anio_anterior = _sin_publicar(_AHORA - timedelta(days=4), VERSION_LOGICA_BUSQUEDA)
    del_anio_anterior.codigo_expediente = "6.25/28510.0175"

    assert plazo_sin_publicar(del_anio_anterior, _PLAZO, _AHORA) == timedelta(days=3)


def test_un_codigo_sin_año_legible_usa_el_plazo_largo():
    """Conservador a propósito: lo que no se sabe leer no se rebusca más a
    menudo, se rebusca menos."""
    raro = _sin_publicar(_AHORA - timedelta(days=4), VERSION_LOGICA_BUSQUEDA)
    raro.codigo_expediente = "28510"

    assert plazo_sin_publicar(raro, _PLAZO, _AHORA) == _PLAZO
