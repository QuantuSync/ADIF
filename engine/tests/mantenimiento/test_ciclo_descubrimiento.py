"""Integración bloque 1 + bloque 2 (CONTEXTO.md sección 24): un expediente
descubierto por sindicación en un ciclo entra en el mismo bucle de decisión
de frescura de ESE mismo ciclo, sin esperar al siguiente."""
from app.mantenimiento.ciclo import ejecutar_ciclo_mantenimiento
from app.models import Expediente
from app.queue import encolar_trabajo
from tests.sindicacion.fixtures import construir_zip, entrada_xml


def test_expediente_descubierto_se_procesa_en_el_mismo_ciclo(tmp_path, db_session, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "sindicacion_departamentos_adif", "28510")

    zip_path = construir_zip(
        tmp_path / "prueba.zip",
        [entrada_xml("6.24/28510.0088", "ADIF - Presidencia", "PUB", "2024-08-05T15:07:29+02:00", "1", "1")],
    )

    descargas = []
    manejadores = {"descargar_expediente": lambda db, t: descargas.append(t.expediente_id) or {}}
    trabajo = encolar_trabajo(
        db_session, tipo="mantenimiento_ciclo",
        payload={"sindicacion_desactivada": False, "sindicacion_periodo": "202408", "sindicacion_ruta_zip": str(zip_path)},
    )

    resumen = ejecutar_ciclo_mantenimiento(db_session, storage=None, model_provider=None, manejadores=manejadores, trabajo=trabajo)

    assert resumen["nuevos_descubiertos"] == 1
    expediente = db_session.query(Expediente).filter_by(codigo_expediente="6.24/28510.0088").one()
    assert descargas == [expediente.id]
    assert resumen["descargas_lanzadas"] == 1


def test_fallo_de_descubrimiento_no_impide_el_resto_del_ciclo(tmp_path, db_session):
    """Un periodo sin ZIP real (fichero inexistente) no debe tirar el resto
    del ciclo -- el descubrimiento falla, se registra el error, y el bucle
    de frescura de siempre sigue evaluando lo que ya había."""
    exp = Expediente(codigo_expediente="6.24/28510.0001")
    db_session.add(exp)
    db_session.commit()

    trabajo = encolar_trabajo(
        db_session, tipo="mantenimiento_ciclo",
        payload={
            "sindicacion_desactivada": False, "sindicacion_periodo": "999999",
            "sindicacion_ruta_zip": str(tmp_path / "no-existe.zip"),
        },
    )

    resumen = ejecutar_ciclo_mantenimiento(db_session, storage=None, model_provider=None, manejadores={}, trabajo=trabajo)

    assert "error" in resumen["descubrimiento"]
    assert resumen["expedientes_evaluados"] == 1


# --- Sesión 2026-09-16: segunda vía de descubrimiento, por búsqueda directa ---


def _doble_busqueda(monkeypatch, codigos):
    from app.scraping import descubrimiento_busqueda

    async def falso(fragmentos):
        return {f: list(codigos) for f in fragmentos}

    monkeypatch.setattr(descubrimiento_busqueda, "buscar_codigos_de_fragmentos", falso)


def test_expediente_descubierto_por_busqueda_se_descarga_en_el_mismo_ciclo(db_session, monkeypatch):
    """Mismo trato que el descubrimiento por sindicación: lo que aparece en
    la búsqueda entra en el bucle de frescura de ESE mismo ciclo."""
    from app import config
    monkeypatch.setattr(config.settings, "busqueda_descubrimiento_activo", True)
    _doble_busqueda(monkeypatch, ["6.26/28510.0016"])

    descargas = []
    manejadores = {"descargar_expediente": lambda db, t: descargas.append(t.expediente_id) or {}}
    trabajo = encolar_trabajo(
        db_session, tipo="mantenimiento_ciclo",
        payload={"sindicacion_desactivada": True, "busqueda_fragmentos": ["6.26/28510"]},
    )

    resumen = ejecutar_ciclo_mantenimiento(
        db_session, storage=None, model_provider=None, manejadores=manejadores, trabajo=trabajo
    )

    assert resumen["descubrimiento_busqueda"]["expedientes_nuevos"] == 1
    assert resumen["nuevos_descubiertos"] == 1
    expediente = db_session.query(Expediente).filter_by(codigo_expediente="6.26/28510.0016").one()
    assert descargas == [expediente.id]
    assert resumen["descargas_lanzadas"] == 1


def test_un_sin_publicar_reabierto_por_la_busqueda_vuelve_a_descargarse(db_session, monkeypatch):
    """El bucle de frescura excluye los `sin_publicar`; reabrirlo a
    `pendiente` es lo único que hace falta para que lo recoja -- por eso el
    descubrimiento no encola la descarga él mismo (sería la misma petición
    por duplicado)."""
    from app import config
    from app.models import EstadoExpediente

    monkeypatch.setattr(config.settings, "busqueda_descubrimiento_activo", True)
    exp = Expediente(codigo_expediente="6.26/28510.0004", estado=EstadoExpediente.sin_publicar)
    db_session.add(exp)
    db_session.commit()
    _doble_busqueda(monkeypatch, ["6.26/28510.0004"])

    descargas = []
    manejadores = {"descargar_expediente": lambda db, t: descargas.append(t.expediente_id) or {}}
    trabajo = encolar_trabajo(
        db_session, tipo="mantenimiento_ciclo",
        payload={"sindicacion_desactivada": True, "busqueda_fragmentos": ["6.26/28510"]},
    )

    resumen = ejecutar_ciclo_mantenimiento(
        db_session, storage=None, model_provider=None, manejadores=manejadores, trabajo=trabajo
    )

    assert resumen["descubrimiento_busqueda"]["sin_publicar_reabiertos"] == 1
    assert descargas == [exp.id]
    assert resumen["descargas_lanzadas"] == 1


def test_fallo_de_la_busqueda_no_impide_el_resto_del_ciclo(db_session, monkeypatch):
    from app import config
    from app.scraping import descubrimiento_busqueda

    monkeypatch.setattr(config.settings, "busqueda_descubrimiento_activo", True)

    async def revienta(fragmentos):
        raise RuntimeError("la Plataforma devolvió una página de bloqueo")

    monkeypatch.setattr(descubrimiento_busqueda, "buscar_codigos_de_fragmentos", revienta)

    db_session.add(Expediente(codigo_expediente="6.24/28510.0001"))
    db_session.commit()
    trabajo = encolar_trabajo(
        db_session, tipo="mantenimiento_ciclo",
        payload={"sindicacion_desactivada": True, "busqueda_fragmentos": ["6.26/28510"]},
    )

    resumen = ejecutar_ciclo_mantenimiento(
        db_session, storage=None, model_provider=None, manejadores={}, trabajo=trabajo
    )

    assert "error" in resumen["descubrimiento_busqueda"]
    assert resumen["expedientes_evaluados"] == 1


# --- Bloque 4, sesión 2026-09-18: con la bandera puesta, CERO peticiones ----


def _busqueda_que_no_debe_llamarse(monkeypatch):
    """Doble que revienta si alguien la llama: `buscar_codigos_de_fragmentos`
    es la única puerta por la que el ciclo llega a la Plataforma para buscar
    (abre el formulario, busca y pagina, todo por `esperar_turno_async`). Si
    no se la llama, no ha habido ninguna petición."""
    from app.scraping import descubrimiento_busqueda

    llamadas = []

    async def jamas(fragmentos):
        llamadas.append(fragmentos)
        raise AssertionError(f"se pidió a la Plataforma con la búsqueda desactivada: {fragmentos!r}")

    monkeypatch.setattr(descubrimiento_busqueda, "buscar_codigos_de_fragmentos", jamas)
    return llamadas


def test_con_busqueda_desactivada_el_ciclo_no_pide_nada_a_la_plataforma(db_session, monkeypatch):
    from app import config

    # Activa en configuración: lo único que la frena es la bandera del payload.
    monkeypatch.setattr(config.settings, "busqueda_descubrimiento_activo", True)
    llamadas = _busqueda_que_no_debe_llamarse(monkeypatch)

    exp = Expediente(codigo_expediente="6.26/28510.0016")
    db_session.add(exp)
    db_session.commit()

    trabajo = encolar_trabajo(
        db_session, tipo="mantenimiento_ciclo",
        payload={"sindicacion_desactivada": True, "busqueda_desactivada": True},
    )

    resumen = ejecutar_ciclo_mantenimiento(
        db_session, storage=None, model_provider=None, manejadores={}, trabajo=trabajo
    )

    assert llamadas == [], "la búsqueda se lanzó pese a estar desactivada"
    assert resumen["descubrimiento_busqueda"] is None
    # Y el resto del ciclo sí corre con normalidad.
    assert resumen["expedientes_evaluados"] == 1


def test_sin_la_bandera_la_busqueda_si_se_lanza(db_session, monkeypatch):
    """La otra mitad de la comprobación: sin bandera, el doble sí se llama --
    si no, el test de arriba pasaría por un motivo equivocado."""
    from app import config

    monkeypatch.setattr(config.settings, "busqueda_descubrimiento_activo", True)
    _doble_busqueda(monkeypatch, [])

    trabajo = encolar_trabajo(
        db_session, tipo="mantenimiento_ciclo",
        payload={"sindicacion_desactivada": True, "busqueda_fragmentos": ["6.26/28510"]},
    )

    resumen = ejecutar_ciclo_mantenimiento(
        db_session, storage=None, model_provider=None, manejadores={}, trabajo=trabajo
    )

    assert resumen["descubrimiento_busqueda"] is not None
    assert resumen["descubrimiento_busqueda"]["error"] is None
