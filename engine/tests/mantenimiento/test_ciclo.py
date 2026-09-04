"""Bloque 1 (CLAUDE.md sección 23): el ciclo de mantenimiento decide, encola
y drena — con manejadores falsos, sin scraping real ni modelo real, igual
que el resto de tests de esta cascada."""
from datetime import datetime, timezone

from app.mantenimiento.ciclo import ejecutar_ciclo_mantenimiento
from app.mantenimiento.frescura import VERSION_LOGICA_EXTRACCION, huella_documentos
from app.models import Documento, EstadoExpediente, EstadoTrabajo, Expediente, TrabajoCola
from app.queue import encolar_trabajo


def _crear_expediente(db, **kwargs) -> Expediente:
    base = dict(codigo_expediente=f"6.24/28510.{kwargs.pop('sufijo', '0001')}")
    base.update(kwargs)
    exp = Expediente(**base)
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


def _crear_documento(db, expediente_id: int, hash_: str) -> Documento:
    doc = Documento(
        expediente_id=expediente_id, tipo_documento="anejo", hash=hash_,
        nombre_archivo=f"{hash_}.pdf", ruta_almacenamiento=f"x/{hash_}.pdf",
    )
    db.add(doc)
    db.commit()
    return doc


def _trabajo_ciclo(db, payload=None) -> TrabajoCola:
    return encolar_trabajo(db, tipo="mantenimiento_ciclo", payload=payload)


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

    manejadores = {"descargar_expediente": fake_descargar, "extraer_expediente": fake_extraer}
    trabajo = _trabajo_ciclo(db_session)

    resumen = ejecutar_ciclo_mantenimiento(db_session, storage=None, model_provider=None, manejadores=manejadores, trabajo=trabajo)

    assert resumen["expedientes_evaluados"] == 1
    assert resumen["descargas_lanzadas"] == 1
    # La extracción se encadena desde la propia descarga (fake_descargar),
    # no desde el bucle de decisión (el expediente no tenía documentos
    # cuando se evaluó) -- pero el drenaje la recoge y ejecuta igual.
    assert llamadas_extraer == [exp.id]
    assert resumen["trabajos_drenados"] == 2


def test_expediente_al_dia_no_lanza_nada(db_session):
    exp = _crear_expediente(db_session)
    _crear_documento(db_session, exp.id, "h1")
    docs = db_session.query(Documento).filter(Documento.expediente_id == exp.id).all()
    exp.extraido_en = datetime.now(timezone.utc)
    exp.version_logica_extraccion = VERSION_LOGICA_EXTRACCION
    exp.huella_documentos = huella_documentos(docs)
    db_session.commit()

    manejadores = {"descargar_expediente": lambda db, t: {}, "extraer_expediente": lambda db, t: {}}
    trabajo = _trabajo_ciclo(db_session)

    resumen = ejecutar_ciclo_mantenimiento(db_session, storage=None, model_provider=None, manejadores=manejadores, trabajo=trabajo)

    assert resumen["saltados_descarga"] == 1
    assert resumen["saltados_extraccion"] == 1
    assert resumen["descargas_lanzadas"] == 0
    assert resumen["extracciones_lanzadas"] == 0
    assert resumen["trabajos_drenados"] == 0


def test_forzar_global_reprocesa_aunque_este_al_dia(db_session):
    exp = _crear_expediente(db_session)
    _crear_documento(db_session, exp.id, "h1")
    docs = db_session.query(Documento).filter(Documento.expediente_id == exp.id).all()
    exp.extraido_en = datetime.now(timezone.utc)
    exp.version_logica_extraccion = VERSION_LOGICA_EXTRACCION
    exp.huella_documentos = huella_documentos(docs)
    db_session.commit()

    ejecutados = []
    manejadores = {"extraer_expediente": lambda db, t: ejecutados.append(t.expediente_id) or {}}
    trabajo = _trabajo_ciclo(db_session, payload={"forzar": True})

    resumen = ejecutar_ciclo_mantenimiento(db_session, storage=None, model_provider=None, manejadores=manejadores, trabajo=trabajo)

    assert resumen["extracciones_lanzadas"] == 1
    assert ejecutados == [exp.id]


def test_sin_publicar_se_excluye_del_ciclo(db_session):
    _crear_expediente(db_session, estado=EstadoExpediente.sin_publicar)
    trabajo = _trabajo_ciclo(db_session)

    resumen = ejecutar_ciclo_mantenimiento(db_session, storage=None, model_provider=None, manejadores={}, trabajo=trabajo)

    assert resumen["expedientes_evaluados"] == 0


def test_drenaje_no_recoge_otro_ciclo_pendiente(db_session):
    """Un segundo trabajo `mantenimiento_ciclo` que quedara pendiente en la
    cola (p.ej. encolado a mano mientras este corría) no debe ejecutarse
    desde dentro del drenaje de este -- evita recursión y solapamiento."""
    trabajo = _trabajo_ciclo(db_session)
    otro_ciclo = _trabajo_ciclo(db_session)

    resumen = ejecutar_ciclo_mantenimiento(db_session, storage=None, model_provider=None, manejadores={}, trabajo=trabajo)

    assert resumen["trabajos_drenados"] == 0
    db_session.refresh(otro_ciclo)
    assert otro_ciclo.estado == EstadoTrabajo.pendiente
