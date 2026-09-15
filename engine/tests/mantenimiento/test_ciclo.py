"""Bloque 1 (CONTEXTO.md sección 23): el ciclo de mantenimiento decide, encola
y drena — con manejadores falsos, sin scraping real ni modelo real, igual
que el resto de tests de esta cascada."""
from datetime import datetime, timedelta, timezone

from app.mantenimiento.auditoria import TIPO_TRABAJO as TIPO_TRABAJO_AUDITORIA
from app.mantenimiento.auditoria import ejecutar_auditoria
from app.mantenimiento.ciclo import ejecutar_ciclo_mantenimiento
from app.mantenimiento.frescura import VERSION_LOGICA_BUSQUEDA, VERSION_LOGICA_EXTRACCION, huella_documentos
from app.models import Documento, DocumentoExpediente, EstadoExpediente, EstadoTrabajo, Expediente, TrabajoCola
from app.queue import encolar_trabajo

# BLOQUE 1, sesión de auditoría automática (2026-09-08): la auditoría se
# encola sola al final de CADA ciclo (`app.mantenimiento.ciclo`), así que
# todo manejador de estos tests la incluye -- con la función real (de solo
# lectura, sin red ni modelo, igual de barata que el resto de estos tests)
# para que el conteo de `trabajos_drenados` y el propio `resumen["auditoria"]`
# reflejen el comportamiento real, no un manejador desconocido fallando en
# silencio.
_AUDITORIA = {TIPO_TRABAJO_AUDITORIA: ejecutar_auditoria}


def _crear_expediente(db, **kwargs) -> Expediente:
    base = dict(codigo_expediente=f"6.24/28510.{kwargs.pop('sufijo', '0001')}")
    base.update(kwargs)
    exp = Expediente(**base)
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


def _crear_documento(db, expediente_id: int, hash_: str) -> Documento:
    doc = Documento(tipo_documento="anejo", hash=hash_, ruta_almacenamiento=f"x/{hash_}.pdf")
    db.add(doc)
    db.commit()
    db.add(DocumentoExpediente(documento_id=doc.id, expediente_id=expediente_id, nombre_archivo=f"{hash_}.pdf"))
    db.commit()
    return doc


def _trabajo_ciclo(db, payload=None) -> TrabajoCola:
    # Bloque 2 (app.sindicacion.descubrimiento): desactivado por defecto en
    # estos tests de bloque 1, que no deben tocar la red ni depender de un
    # ZIP -- ver tests/sindicacion/test_descubrimiento.py y
    # tests/mantenimiento/test_ciclo_descubrimiento.py para eso.
    payload_final = {"sindicacion_desactivada": True, **(payload or {})}
    return encolar_trabajo(db, tipo="mantenimiento_ciclo", payload=payload_final)


def test_expediente_sin_documentos_encola_y_drena_descarga_y_extraccion_encadenada(db_session):
    """Simula lo que hace `app.scraping.job` de verdad: la descarga deja un
    documento nuevo y encadena su propia extracción -- el drenaje del ciclo
    debe recogerla igual, sin que el bucle de decisión la duplique."""
    exp = _crear_expediente(db_session)

    def fake_descargar(db, trabajo):
        _crear_documento(db, trabajo.expediente_id, "hash-nuevo")
        encolar_trabajo(db, tipo="extraer_expediente", expediente_id=trabajo.expediente_id)
        return {"ok": True}

    llamadas_extraer = []

    def fake_extraer(db, trabajo):
        llamadas_extraer.append(trabajo.expediente_id)
        e = db.get(Expediente, trabajo.expediente_id)
        e.estado = EstadoExpediente.completado
        return {"ok": True}

    manejadores = {"descargar_expediente": fake_descargar, "extraer_expediente": fake_extraer, **_AUDITORIA}
    trabajo = _trabajo_ciclo(db_session)

    resumen = ejecutar_ciclo_mantenimiento(db_session, storage=None, model_provider=None, manejadores=manejadores, trabajo=trabajo)

    assert resumen["expedientes_evaluados"] == 1
    assert resumen["descargas_lanzadas"] == 1
    # La extracción se encadena desde la propia descarga (fake_descargar),
    # no desde el bucle de decisión (el expediente no tenía documentos
    # cuando se evaluó) -- pero el drenaje la recoge y ejecuta igual.
    assert llamadas_extraer == [exp.id]
    # descarga + extracción + auditoría automática de fin de ciclo.
    assert resumen["trabajos_drenados"] == 3
    assert resumen["auditoria"] is not None
    assert resumen["auditoria"]["total_expedientes"] == 1


def test_expediente_al_dia_no_lanza_nada(db_session):
    exp = _crear_expediente(db_session)
    _crear_documento(db_session, exp.id, "h1")
    docs = (
        db_session.query(Documento)
        .join(DocumentoExpediente, DocumentoExpediente.documento_id == Documento.id)
        .filter(DocumentoExpediente.expediente_id == exp.id)
        .all()
    )
    exp.extraido_en = datetime.now(timezone.utc)
    exp.version_logica_extraccion = VERSION_LOGICA_EXTRACCION
    exp.huella_documentos = huella_documentos(docs)
    db_session.commit()

    manejadores = {"descargar_expediente": lambda db, t: {}, "extraer_expediente": lambda db, t: {}, **_AUDITORIA}
    trabajo = _trabajo_ciclo(db_session)

    resumen = ejecutar_ciclo_mantenimiento(db_session, storage=None, model_provider=None, manejadores=manejadores, trabajo=trabajo)

    assert resumen["saltados_descarga"] == 1
    assert resumen["saltados_extraccion"] == 1
    assert resumen["descargas_lanzadas"] == 0
    assert resumen["extracciones_lanzadas"] == 0
    # Nada que descargar/extraer, pero la auditoría automática de fin de
    # ciclo sí corre siempre.
    assert resumen["trabajos_drenados"] == 1


def test_forzar_global_reprocesa_aunque_este_al_dia(db_session):
    exp = _crear_expediente(db_session)
    _crear_documento(db_session, exp.id, "h1")
    docs = (
        db_session.query(Documento)
        .join(DocumentoExpediente, DocumentoExpediente.documento_id == Documento.id)
        .filter(DocumentoExpediente.expediente_id == exp.id)
        .all()
    )
    # Margen claro respecto a `trabajo.created_at` (más abajo): SQLite, el
    # motor de estos tests, solo guarda `CURRENT_TIMESTAMP` con resolución
    # de segundo -- sin este margen, un `extraido_en` con microsegundos
    # capturado unos milisegundos antes puede leerse de vuelta como
    # POSTERIOR al `created_at` truncado del trabajo, disparando por
    # accidente la comprobación de resumibilidad del Bloque 2. PostgreSQL
    # (producción) no trunca así, pero el margen no depende de esa
    # diferencia de motor.
    exp.extraido_en = datetime.now(timezone.utc) - timedelta(seconds=5)
    exp.version_logica_extraccion = VERSION_LOGICA_EXTRACCION
    exp.huella_documentos = huella_documentos(docs)
    db_session.commit()

    ejecutados = []
    manejadores = {"extraer_expediente": lambda db, t: ejecutados.append(t.expediente_id) or {}, **_AUDITORIA}
    trabajo = _trabajo_ciclo(db_session, payload={"forzar": True})

    resumen = ejecutar_ciclo_mantenimiento(db_session, storage=None, model_provider=None, manejadores=manejadores, trabajo=trabajo)

    assert resumen["extracciones_lanzadas"] == 1
    assert ejecutados == [exp.id]


def _descargas_por_expediente(db) -> list[int]:
    return [
        t.expediente_id
        for t in db.query(TrabajoCola).filter(TrabajoCola.tipo == "descargar_expediente").order_by(TrabajoCola.id)
    ]


def test_sin_publicar_confirmado_dentro_de_plazo_no_se_rebusca(db_session):
    _crear_expediente(
        db_session, estado=EstadoExpediente.sin_publicar,
        sin_publicar_en=datetime.now(timezone.utc) - timedelta(days=3),
        sin_publicar_version_busqueda=VERSION_LOGICA_BUSQUEDA,
    )
    trabajo = _trabajo_ciclo(db_session)

    resumen = ejecutar_ciclo_mantenimiento(
        db_session, storage=None, model_provider=None, manejadores=dict(_AUDITORIA), trabajo=trabajo,
    )

    # Fuera del bucle normal de descarga/extracción, y sin búsqueda nueva.
    assert resumen["expedientes_evaluados"] == 0
    assert resumen["sin_publicar_reintentados"] == 0
    assert resumen["sin_publicar_en_plazo"] == 1
    assert _descargas_por_expediente(db_session) == []


def test_sin_publicar_se_rebusca_si_no_esta_confirmado_o_vencio_el_plazo(db_session):
    """Sesión 2026-09-15: `sin_publicar` ya no es definitivo -- los negativos
    de antes del arreglo de límite de tasa (sin versión) se vuelven a buscar
    en seguida, y los confirmados, pasado el plazo."""
    sin_confirmar = _crear_expediente(
        db_session, sufijo="0001", estado=EstadoExpediente.sin_publicar,
        sin_publicar_en=datetime.now(timezone.utc) - timedelta(days=1),
    )
    vencido = _crear_expediente(
        db_session, sufijo="0002", estado=EstadoExpediente.sin_publicar,
        sin_publicar_en=datetime.now(timezone.utc) - timedelta(days=30),
        sin_publicar_version_busqueda=VERSION_LOGICA_BUSQUEDA,
    )
    buscados = []

    def fake_descargar(db, t):
        buscados.append(t.expediente_id)
        return {}

    trabajo = _trabajo_ciclo(db_session)
    resumen = ejecutar_ciclo_mantenimiento(
        db_session, storage=None, model_provider=None,
        manejadores={"descargar_expediente": fake_descargar, **_AUDITORIA}, trabajo=trabajo,
    )

    assert resumen["sin_publicar_reintentados"] == 2
    # El no confirmado va primero aunque sea más reciente.
    assert buscados == [sin_confirmar.id, vencido.id]


def test_sin_publicar_respeta_el_tope_por_ciclo(db_session, monkeypatch):
    monkeypatch.setattr("app.mantenimiento.ciclo.settings.sin_publicar_reintentos_por_ciclo", 2)
    viejos = [
        _crear_expediente(
            db_session, sufijo=f"000{i}", estado=EstadoExpediente.sin_publicar,
            sin_publicar_en=datetime.now(timezone.utc) - timedelta(days=40 - i),
            sin_publicar_version_busqueda=VERSION_LOGICA_BUSQUEDA,
        )
        for i in range(3)
    ]
    trabajo = _trabajo_ciclo(db_session)

    resumen = ejecutar_ciclo_mantenimiento(
        db_session, storage=None, model_provider=None,
        manejadores={"descargar_expediente": lambda db, t: {}, **_AUDITORIA}, trabajo=trabajo,
    )

    assert resumen["sin_publicar_reintentados"] == 2
    assert resumen["sin_publicar_aplazados"] == 1
    # Los dos más antiguos; el tercero, al ciclo siguiente.
    assert _descargas_por_expediente(db_session) == [viejos[0].id, viejos[1].id]


def test_reintento_de_ciclo_huerfano_no_reextrae_lo_ya_hecho_en_este_ciclo(db_session):
    """Resumibilidad (sesión 2026-09-11): un `mantenimiento_ciclo` reclamado
    como huérfano y reintentado (mismo `TrabajoCola.created_at`, `intentos`
    incrementado) no debe volver a lanzar la extracción de un expediente que
    un intento ANTERIOR de este mismo ciclo ya completó -- aunque el payload
    siga trayendo `forzar: true` (`forzar_global`, el mismo en cada
    reintento). Simula el escenario real: el trabajo de ciclo ya existía
    (creado antes) cuando el expediente terminó su extracción."""
    exp = _crear_expediente(db_session)
    _crear_documento(db_session, exp.id, "h1")

    trabajo = _trabajo_ciclo(db_session, payload={"forzar": True})
    # El expediente se extrajo DESPUÉS de que este ciclo se creara -- como lo
    # habría dejado un primer intento de este mismo ciclo, antes de que el
    # worker se reiniciara a mitad de camino.
    exp.extraido_en = trabajo.created_at + timedelta(seconds=5)
    exp.version_logica_extraccion = VERSION_LOGICA_EXTRACCION
    docs = (
        db_session.query(Documento)
        .join(DocumentoExpediente, DocumentoExpediente.documento_id == Documento.id)
        .filter(DocumentoExpediente.expediente_id == exp.id)
        .all()
    )
    exp.huella_documentos = huella_documentos(docs)
    db_session.commit()

    ejecutados = []
    manejadores = {"extraer_expediente": lambda db, t: ejecutados.append(t.expediente_id) or {}, **_AUDITORIA}

    resumen = ejecutar_ciclo_mantenimiento(
        db_session, storage=None, model_provider=None, manejadores=manejadores, trabajo=trabajo
    )

    assert resumen["extracciones_lanzadas"] == 0
    assert resumen["saltados_extraccion"] == 1
    assert ejecutados == []


def test_ciclo_renueva_bloqueado_en_al_drenar_trabajos(db_session):
    """Latido de resumibilidad: cada trabajo drenado dentro del ciclo debe
    refrescar `bloqueado_en` del propio trabajo `mantenimiento_ciclo`, para
    que `reclamar_trabajos_huerfanos` no lo marque huérfano mientras sigue
    vivo y avanzando."""
    exp = _crear_expediente(db_session)

    def fake_descargar(db, trabajo):
        _crear_documento(db, trabajo.expediente_id, "hash-nuevo")
        encolar_trabajo(db, tipo="extraer_expediente", expediente_id=trabajo.expediente_id)
        return {"ok": True}

    manejadores = {
        "descargar_expediente": fake_descargar,
        "extraer_expediente": lambda db, t: {"ok": True},
        **_AUDITORIA,
    }
    trabajo = _trabajo_ciclo(db_session)
    bloqueado_en_inicial = datetime.now(timezone.utc) - timedelta(minutes=10)
    trabajo.bloqueado_en = bloqueado_en_inicial
    db_session.commit()

    ejecutar_ciclo_mantenimiento(db_session, storage=None, model_provider=None, manejadores=manejadores, trabajo=trabajo)

    db_session.refresh(trabajo)
    # SQLite (motor de estos tests) devuelve el valor guardado sin
    # información de zona horaria -- se compara en naive por los dos lados,
    # el punto del test es el orden relativo, no el `tzinfo`.
    assert trabajo.bloqueado_en.replace(tzinfo=None) > bloqueado_en_inicial.replace(tzinfo=None)


def test_drenaje_no_recoge_otro_ciclo_pendiente(db_session):
    """Un segundo trabajo `mantenimiento_ciclo` que quedara pendiente en la
    cola (p.ej. encolado a mano mientras este corría) no debe ejecutarse
    desde dentro del drenaje de este -- evita recursión y solapamiento."""
    trabajo = _trabajo_ciclo(db_session)
    otro_ciclo = _trabajo_ciclo(db_session)

    resumen = ejecutar_ciclo_mantenimiento(db_session, storage=None, model_provider=None, manejadores=_AUDITORIA, trabajo=trabajo)

    # El segundo `mantenimiento_ciclo` pendiente nunca se recoge (excluido
    # del drenaje por tipo); la auditoría automática de fin de ciclo sí.
    assert resumen["trabajos_drenados"] == 1
    db_session.refresh(otro_ciclo)
    assert otro_ciclo.estado == EstadoTrabajo.pendiente
