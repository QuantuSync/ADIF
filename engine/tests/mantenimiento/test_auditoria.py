"""BLOQUE 1, sesión de auditoría automática (2026-09-08): comprobaciones de
solo lectura sobre el catálogo -- cada test monta el estado mínimo que
dispara (o no) un hallazgo concreto, sin red ni modelo, igual que el resto
de esta cascada."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.extraccion.firma_cabecera import calcular_firma_cabecera
from app.mantenimiento.auditoria import (
    MENSAJE_DUPLICADAS_CODIGOS_DISTINTOS,
    TIPO_TRABAJO,
    ejecutar_auditoria,
)
from app.models import (
    Documento,
    DocumentoExpediente,
    EstadoRevisionLinea,
    EstadoTrabajo,
    Expediente,
    Lote,
    LineaCatalogo,
    MapeoCabeceraCache,
    TrabajoCola,
)
from app.queue import encolar_trabajo

_contador_clave = iter(range(1_000_000))
_contador_hash = iter(range(1_000_000))


def _expediente(db, codigo="6.24/28510.0001", **kwargs) -> Expediente:
    exp = Expediente(codigo_expediente=codigo, **kwargs)
    db.add(exp)
    db.commit()
    return exp


def _lote(db, expediente_id, identificador="1", **kwargs) -> Lote:
    lote = Lote(expediente_id=expediente_id, identificador_lote=identificador, **kwargs)
    db.add(lote)
    db.commit()
    return lote


def _linea(db, expediente_id, lote_id=None, **kwargs) -> LineaCatalogo:
    base = dict(
        expediente_id=expediente_id,
        lote_id=lote_id,
        clave_linea=kwargs.pop("clave_linea", f"P-{next(_contador_clave)}"),
        orden_aparicion=kwargs.pop("orden_aparicion", 0),
        descripcion=kwargs.pop("descripcion", "MATERIAL X"),
    )
    base.update(kwargs)
    linea = LineaCatalogo(**base)
    db.add(linea)
    db.commit()
    return linea


def _vincular_documento(db, expediente_id, documento=None) -> Documento:
    if documento is None:
        h = f"hash-{next(_contador_hash)}"
        documento = Documento(tipo_documento="anuncio_pcsp", hash=h, ruta_almacenamiento=f"x/{h}.pdf")
        db.add(documento)
        db.commit()
    db.add(DocumentoExpediente(documento_id=documento.id, expediente_id=expediente_id, nombre_archivo="x.pdf"))
    db.commit()
    return documento


def _trabajo(db) -> TrabajoCola:
    return encolar_trabajo(db, tipo=TIPO_TRABAJO)


def test_sin_ningun_defecto_no_da_hallazgos(db_session):
    exp = _expediente(db_session)
    lote = _lote(db_session, exp.id)
    _linea(db_session, exp.id, lote.id, clave_linea="P-1", codigo_precio="P-1", precio_unitario=Decimal("10"))
    _linea(db_session, exp.id, lote.id, clave_linea="P-2", codigo_precio="P-2", precio_unitario=Decimal("12"))

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    assert resultado["hallazgos"] == []
    assert resultado["total_lineas"] == 2


# --- Duplicadas exactas: el código de precio decide la gravedad -------------
# Decisión del cliente, sesión 2026-09-18. El `codigo_precio` es la clave de
# la línea dentro del documento (CONTEXTO.md sección 2), así que dos filas por
# lo demás idénticas significan cosas distintas según lo que traigan ahí.


def _duplicado(db, exp, lote, codigo_a, codigo_b):
    for i, codigo in enumerate((codigo_a, codigo_b)):
        _linea(
            db, exp.id, lote.id, clave_linea=f"clave-{i}-{next(_contador_clave)}", codigo_precio=codigo,
            matricula="123456789", descripcion="TUERCA", cantidad=Decimal("1"), precio_unitario=Decimal("5"),
        )


def test_duplicadas_con_el_mismo_codigo_de_precio_son_error(db_session):
    """La misma línea del documento contada dos veces: no hay lectura posible."""
    exp = _expediente(db_session)
    lote = _lote(db_session, exp.id)
    _duplicado(db_session, exp, lote, "P-1", "P-1")

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    hallazgo = next(h for h in resultado["hallazgos"] if h["categoria"] == "lineas_duplicadas_exactas")
    assert hallazgo["gravedad"] == "error"
    assert exp.codigo_expediente in hallazgo["expedientes"]


def test_duplicadas_sin_codigo_de_precio_son_error(db_session):
    exp = _expediente(db_session)
    lote = _lote(db_session, exp.id)
    _duplicado(db_session, exp, lote, None, None)

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    hallazgo = next(h for h in resultado["hallazgos"] if h["categoria"] == "lineas_duplicadas_exactas")
    assert hallazgo["gravedad"] == "error"


def test_duplicadas_con_una_sola_sin_codigo_siguen_siendo_error(db_session):
    """Basta una fila sin código para no poder afirmar que el documento las
    lista como dos entradas propias."""
    exp = _expediente(db_session)
    lote = _lote(db_session, exp.id)
    _duplicado(db_session, exp, lote, "P-1", None)

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    hallazgo = next(h for h in resultado["hallazgos"] if h["categoria"] == "lineas_duplicadas_exactas")
    assert hallazgo["gravedad"] == "error"


def test_la_fila_que_el_propio_cuadro_repite_es_aviso_y_no_error(db_session):
    """Sesión 2026-09-21 (tercera parte): la repetición conservada porque con
    ella el lote cuadra lleva su marca (`app.extraccion.filas_repetidas`)."""
    from app.catalogo import _MOTIVO_FILA_REPETIDA_EN_EL_CUADRO

    exp = _expediente(db_session)
    lote = _lote(db_session, exp.id)
    for i, motivo in enumerate((None, _MOTIVO_FILA_REPETIDA_EN_EL_CUADRO)):
        _linea(
            db_session, exp.id, lote.id, clave_linea=f"clave-r-{i}-{next(_contador_clave)}", codigo_precio=None,
            matricula=None, descripcion="GUANTE JUBA", cantidad=Decimal("100"), precio_unitario=Decimal("1.5"),
            motivo_revision=motivo,
        )

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    categorias = {h["categoria"]: h["gravedad"] for h in resultado["hallazgos"]}
    assert "lineas_duplicadas_exactas" not in categorias
    assert categorias["lineas_repetidas_por_el_propio_cuadro"] == "aviso"


def test_duplicadas_con_codigos_de_precio_distintos_son_aviso(db_session):
    """Los 11 grupos reales del corpus (`0051`/`0060`, `4.25/28510.0132`):
    el propio documento repite el material con dos claves propias."""
    exp = _expediente(db_session)
    lote = _lote(db_session, exp.id)
    _duplicado(db_session, exp, lote, "P-1", "P-2")

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    categorias = {h["categoria"] for h in resultado["hallazgos"]}
    assert "lineas_duplicadas_exactas" not in categorias, "ya no es un error de extracción"
    hallazgo = next(
        h for h in resultado["hallazgos"] if h["categoria"] == "lineas_duplicadas_codigo_precio_distinto"
    )
    assert hallazgo["gravedad"] == "aviso"
    assert MENSAJE_DUPLICADAS_CODIGOS_DISTINTOS in hallazgo["mensaje"]
    assert exp.codigo_expediente in hallazgo["expedientes"]
    assert resultado["total_errores"] == 0


def test_los_dos_tipos_de_duplicado_a_la_vez_se_separan(db_session):
    exp_error = _expediente(db_session, codigo="6.24/28510.0001")
    lote_error = _lote(db_session, exp_error.id)
    _duplicado(db_session, exp_error, lote_error, "P-9", "P-9")

    exp_aviso = _expediente(db_session, codigo="6.24/28510.0002")
    lote_aviso = _lote(db_session, exp_aviso.id)
    _duplicado(db_session, exp_aviso, lote_aviso, "P-1", "P-2")

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    error = next(h for h in resultado["hallazgos"] if h["categoria"] == "lineas_duplicadas_exactas")
    aviso = next(
        h for h in resultado["hallazgos"] if h["categoria"] == "lineas_duplicadas_codigo_precio_distinto"
    )
    assert error["expedientes"] == [exp_error.codigo_expediente]
    assert aviso["expedientes"] == [exp_aviso.codigo_expediente]
    assert error["detalle"]["lineas"] == 2 and aviso["detalle"]["lineas"] == 2


def test_precio_cero_es_error(db_session):
    exp = _expediente(db_session)
    lote = _lote(db_session, exp.id)
    _linea(db_session, exp.id, lote.id, clave_linea="P-1", codigo_precio="P-1", precio_unitario=Decimal("0"))

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    hallazgo = next(h for h in resultado["hallazgos"] if h["categoria"] == "precio_cero_o_negativo")
    assert hallazgo["gravedad"] == "error"
    assert hallazgo["total_afectados"] == 1


def test_precio_desproporcionado_frente_a_la_mediana_del_expediente(db_session):
    exp = _expediente(db_session)
    lote = _lote(db_session, exp.id)
    for i in range(4):
        _linea(db_session, exp.id, lote.id, clave_linea=f"P-{i}", codigo_precio=f"P-{i}", precio_unitario=Decimal("10"))
    _linea(db_session, exp.id, lote.id, clave_linea="P-atipica", codigo_precio="P-atipica", precio_unitario=Decimal("5000"))

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    hallazgo = next(h for h in resultado["hallazgos"] if h["categoria"] == "precio_desproporcionado")
    assert hallazgo["gravedad"] == "aviso"


def test_la_partida_alzada_no_cuenta_como_precio_desproporcionado(db_session):
    """Bloque 6, sesión 2026-09-18 (sexta parte). CONTEXTO.md sección 2: la
    partida alzada es una línea legítima, no un error -- una reserva
    presupuestaria vale por definición órdenes de magnitud más que cualquier
    pieza del mismo cuadro. Eran 331 de las 2.005 líneas que este aviso
    señalaba."""
    exp = _expediente(db_session)
    lote = _lote(db_session, exp.id)
    for i in range(4):
        _linea(db_session, exp.id, lote.id, clave_linea=f"P-{i}", codigo_precio=f"P-{i}",
               precio_unitario=Decimal("10"), unidad_medida="ud")
    _linea(db_session, exp.id, lote.id, clave_linea="P-pa", codigo_precio="P-pa",
           descripcion="Partida alzada a justificar para imprevistos",
           precio_unitario=Decimal("50000"), unidad_medida="ud")

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    assert not [h for h in resultado["hallazgos"] if h["categoria"] == "precio_desproporcionado"]


def test_el_precio_se_compara_con_la_mediana_de_su_misma_unidad_de_medida(db_session):
    """CONTEXTO.md sección 7 (aviso del cliente): un precio unitario no
    significa nada sin su unidad. Un precio por tonelada-kilómetro comparado
    con la mediana de un cuadro de desvíos completos da 1/7000 y no dice nada
    -- salvo que haya suficientes líneas de esa misma unidad con las que
    compararlo, y entonces sí."""
    exp = _expediente(db_session)
    lote = _lote(db_session, exp.id)
    for i in range(4):
        _linea(db_session, exp.id, lote.id, clave_linea=f"D-{i}", codigo_precio=f"D-{i}",
               precio_unitario=Decimal("11000"), unidad_medida="ud")
    # Una sola línea en t·km: no hay mediana de su unidad con la que juzgarla.
    _linea(db_session, exp.id, lote.id, clave_linea="T-1", codigo_precio="T-1",
           precio_unitario=Decimal("1.60"), unidad_medida="t·km")

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))
    assert not [h for h in resultado["hallazgos"] if h["categoria"] == "precio_desproporcionado"]

    # Con tres compañeras de su misma unidad, una que se sale sí se señala.
    for i in range(3):
        _linea(db_session, exp.id, lote.id, clave_linea=f"T-{i}-b", codigo_precio=f"T-{i}-b",
               precio_unitario=Decimal("1.60"), unidad_medida="t·km")
    _linea(db_session, exp.id, lote.id, clave_linea="T-rara", codigo_precio="T-rara",
           precio_unitario=Decimal("900"), unidad_medida="t·km")

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))
    hallazgo = next(h for h in resultado["hallazgos"] if h["categoria"] == "precio_desproporcionado")
    assert hallazgo["total_afectados"] == 1


def test_cantidad_con_forma_de_anio(db_session):
    exp = _expediente(db_session)
    lote = _lote(db_session, exp.id)
    _linea(db_session, exp.id, lote.id, clave_linea="P-1", codigo_precio="P-1", cantidad=Decimal("2024"))

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    hallazgo = next(h for h in resultado["hallazgos"] if h["categoria"] == "cantidad_forma_anio")
    assert hallazgo["gravedad"] == "aviso"


def test_baja_negativa_o_100_por_cien_es_error(db_session):
    exp = _expediente(db_session)
    _lote(db_session, exp.id, identificador="1", baja_lote=Decimal("-0.1"))
    _lote(db_session, exp.id, identificador="2", baja_lote=Decimal("1.5"))

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    hallazgo = next(h for h in resultado["hallazgos"] if h["categoria"] == "baja_implausible")
    assert hallazgo["total_afectados"] == 1  # un solo expediente, dos lotes


def test_baja_cero_no_da_ningun_hallazgo(db_session):
    """CONTEXTO.md sección 16 (sesión 2026-09-06, bloque 3): una baja de
    lote a 0% es real y verificada ("baja económica del 0,00 %...", con
    fragmento de origen) -- nunca debe marcarse por sí sola."""
    exp = _expediente(db_session)
    _lote(db_session, exp.id, baja_lote=Decimal("0"))

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    categorias = {h["categoria"] for h in resultado["hallazgos"]}
    assert "baja_implausible" not in categorias
    assert "baja_muy_alta" not in categorias


def test_firma_cabecera_vacia_es_error(db_session):
    db_session.add(MapeoCabeceraCache(firma="x" * 64, cabecera=[None, "", None], mapeo={}, origen="modelo"))
    db_session.commit()

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    hallazgo = next(h for h in resultado["hallazgos"] if h["categoria"] == "firma_cabecera_vacia")
    assert hallazgo["total_afectados"] == 1


def test_firma_cabecera_corrupta_es_error(db_session):
    cabecera = ["CÓDIGO", "DESCRIPCIÓN", "PRECIO"]
    firma_real = calcular_firma_cabecera(cabecera)
    db_session.add(MapeoCabeceraCache(firma="no-coincide-con-la-cabecera", cabecera=cabecera, mapeo={}, origen="modelo"))
    db_session.commit()

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    hallazgo = next(h for h in resultado["hallazgos"] if h["categoria"] == "firma_cabecera_no_reproducible")
    assert hallazgo["total_afectados"] == 1
    assert firma_real != "no-coincide-con-la-cabecera"


def test_firma_cabecera_valida_no_da_hallazgo(db_session):
    cabecera = ["CÓDIGO", "DESCRIPCIÓN", "PRECIO"]
    db_session.add(
        MapeoCabeceraCache(firma=calcular_firma_cabecera(cabecera), cabecera=cabecera, mapeo={}, origen="modelo")
    )
    db_session.commit()

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    categorias = {h["categoria"] for h in resultado["hallazgos"]}
    assert "firma_cabecera_vacia" not in categorias
    assert "firma_cabecera_no_reproducible" not in categorias


def test_lineas_cambian_sin_cambiar_documentos_compara_con_la_ejecucion_anterior(db_session):
    exp = _expediente(db_session, huella_documentos="hash-estable")
    lote = _lote(db_session, exp.id)
    _linea(db_session, exp.id, lote.id, clave_linea="P-1", codigo_precio="P-1", precio_unitario=Decimal("10"))

    hace_una_hora = datetime.now(timezone.utc) - timedelta(hours=1)
    primera = ejecutar_auditoria(db_session, _trabajo(db_session))
    trabajo1 = TrabajoCola(
        tipo=TIPO_TRABAJO, resultado=primera, estado=EstadoTrabajo.completado, created_at=hace_una_hora
    )
    db_session.add(trabajo1)
    db_session.commit()

    # Misma huella de documentos, pero una línea más -- exactamente el
    # síntoma que ya vigila `app.mantenimiento.frescura.
    # detectar_crecimiento_sin_cambios` expediente a expediente; aquí se
    # comprueba a nivel de corpus, entre dos ejecuciones de la auditoría.
    _linea(db_session, exp.id, lote.id, clave_linea="P-2", codigo_precio="P-2", precio_unitario=Decimal("11"))

    segundo_trabajo = TrabajoCola(tipo=TIPO_TRABAJO, created_at=datetime.now(timezone.utc))
    db_session.add(segundo_trabajo)
    db_session.commit()
    resultado = ejecutar_auditoria(db_session, segundo_trabajo)

    hallazgo = next(h for h in resultado["hallazgos"] if h["categoria"] == "lineas_cambian_sin_cambiar_documentos")
    assert exp.codigo_expediente in hallazgo["expedientes"]
    assert resultado["comparado_con_ejecucion_anterior"] == trabajo1.id


def test_bajada_de_lineas_explicada_por_poda_no_es_error(db_session):
    """Bloque 4, sesión 2026-09-11: hallazgo real del reproceso completo de
    la sesión anterior -- 15 expedientes marcados "error" que en realidad
    eran `podar_lineas_obsoletas_de_documento` limpiando residuo genuino.
    Una bajada de recuento con `lineas_podadas` que la explica EXACTAMENTE
    (2 líneas menos, 2 podadas) no debe aparecer como
    `lineas_cambian_sin_cambiar_documentos`, solo como aviso informativo."""
    exp = _expediente(db_session, huella_documentos="hash-estable")
    lote = _lote(db_session, exp.id)
    for i in range(5):
        _linea(db_session, exp.id, lote.id, clave_linea=f"P-{i}", codigo_precio=f"P-{i}", precio_unitario=Decimal("10"))

    hace_una_hora = datetime.now(timezone.utc) - timedelta(hours=1)
    primera = ejecutar_auditoria(db_session, _trabajo(db_session))
    trabajo1 = TrabajoCola(
        tipo=TIPO_TRABAJO, resultado=primera, estado=EstadoTrabajo.completado, created_at=hace_una_hora
    )
    db_session.add(trabajo1)
    db_session.commit()

    # La poda (Bloque 4, sesión del maestro de materiales) borra 2 líneas
    # obsoletas de un reproceso real, entre las dos auditorías -- registrado
    # en el resultado de su propio trabajo `extraer_expediente`.
    lineas = db_session.query(LineaCatalogo).order_by(LineaCatalogo.id).all()
    db_session.delete(lineas[0])
    db_session.delete(lineas[1])
    db_session.commit()
    trabajo_extraccion = TrabajoCola(
        tipo="extraer_expediente",
        expediente_id=exp.id,
        estado=EstadoTrabajo.completado,
        resultado={"lineas_podadas": 2},
        created_at=hace_una_hora + timedelta(minutes=10),
    )
    db_session.add(trabajo_extraccion)
    db_session.commit()

    segundo_trabajo = TrabajoCola(tipo=TIPO_TRABAJO, created_at=datetime.now(timezone.utc))
    db_session.add(segundo_trabajo)
    db_session.commit()
    resultado = ejecutar_auditoria(db_session, segundo_trabajo)

    categorias = {h["categoria"] for h in resultado["hallazgos"]}
    assert "lineas_cambian_sin_cambiar_documentos" not in categorias
    hallazgo = next(h for h in resultado["hallazgos"] if h["categoria"] == "lineas_bajan_explicado_por_poda")
    assert hallazgo["gravedad"] == "aviso"
    assert exp.codigo_expediente in hallazgo["expedientes"]


def test_bajada_de_lineas_no_explicada_por_poda_sigue_siendo_error(db_session):
    """Misma bajada de recuento, pero sin ninguna poda que la explique (o
    que la explique solo a medias): sigue siendo el error de siempre, no se
    descarta a ciegas."""
    exp = _expediente(db_session, huella_documentos="hash-estable")
    lote = _lote(db_session, exp.id)
    for i in range(5):
        _linea(db_session, exp.id, lote.id, clave_linea=f"P-{i}", codigo_precio=f"P-{i}", precio_unitario=Decimal("10"))

    hace_una_hora = datetime.now(timezone.utc) - timedelta(hours=1)
    primera = ejecutar_auditoria(db_session, _trabajo(db_session))
    trabajo1 = TrabajoCola(
        tipo=TIPO_TRABAJO, resultado=primera, estado=EstadoTrabajo.completado, created_at=hace_una_hora
    )
    db_session.add(trabajo1)
    db_session.commit()

    lineas = db_session.query(LineaCatalogo).order_by(LineaCatalogo.id).all()
    db_session.delete(lineas[0])
    db_session.delete(lineas[1])
    db_session.commit()
    # Ninguna poda registrada esta vez (o una extracción sin `lineas_podadas`
    # real): la bajada queda sin explicar.
    trabajo_extraccion = TrabajoCola(
        tipo="extraer_expediente",
        expediente_id=exp.id,
        estado=EstadoTrabajo.completado,
        resultado={"lineas_podadas": 0},
        created_at=hace_una_hora + timedelta(minutes=10),
    )
    db_session.add(trabajo_extraccion)
    db_session.commit()

    segundo_trabajo = TrabajoCola(tipo=TIPO_TRABAJO, created_at=datetime.now(timezone.utc))
    db_session.add(segundo_trabajo)
    db_session.commit()
    resultado = ejecutar_auditoria(db_session, segundo_trabajo)

    hallazgo = next(h for h in resultado["hallazgos"] if h["categoria"] == "lineas_cambian_sin_cambiar_documentos")
    assert hallazgo["gravedad"] == "error"
    assert exp.codigo_expediente in hallazgo["expedientes"]


def test_bajada_explicada_por_el_filtro_de_extraccion_es_aviso_no_error(db_session):
    """Bloque 4, sesión 2026-09-18 (caso real `6.23/28510.0105`). La sesión
    anterior enseñó a la cascada a tratar las filas de resumen de presupuesto
    ("Suma", "IVA (21%)") como pie de tabla en vez de como material, y ese
    expediente perdió su única fila de ese tipo: 36 líneas -> 35. La quitó el
    FILTRO DE EXTRACCIÓN, no el podador, y la reextracción podó 32 y creó 31
    (quitar una fila corre el `orden_aparicion` de las siguientes, y con él
    su clave). `lineas_podadas` (32) no cuadra con la bajada (1), así que
    salía como `error` un cambio perfectamente explicado; el balance
    `podadas - creadas` sí cuadra."""
    exp = _expediente(db_session, huella_documentos="hash-estable")
    lote = _lote(db_session, exp.id)
    for i in range(5):
        _linea(db_session, exp.id, lote.id, clave_linea=f"P-{i}", codigo_precio=f"P-{i}",
               precio_unitario=Decimal("10"))

    hace_una_hora = datetime.now(timezone.utc) - timedelta(hours=1)
    primera = ejecutar_auditoria(db_session, _trabajo(db_session))
    trabajo1 = TrabajoCola(
        tipo=TIPO_TRABAJO, resultado=primera, estado=EstadoTrabajo.completado, created_at=hace_una_hora
    )
    db_session.add(trabajo1)
    db_session.commit()

    # La reextracción borra las 5 viejas y escribe 4 nuevas: neto -1.
    for linea in db_session.query(LineaCatalogo).all():
        db_session.delete(linea)
    db_session.commit()
    for i in range(4):
        _linea(db_session, exp.id, lote.id, clave_linea=f"Q-{i}", codigo_precio=f"Q-{i}",
               precio_unitario=Decimal("10"))
    db_session.add(TrabajoCola(
        tipo="extraer_expediente",
        expediente_id=exp.id,
        estado=EstadoTrabajo.completado,
        resultado={"lineas_podadas": 5, "lineas_creadas": 4},
        created_at=hace_una_hora + timedelta(minutes=10),
    ))
    db_session.commit()

    segundo_trabajo = TrabajoCola(tipo=TIPO_TRABAJO, created_at=datetime.now(timezone.utc))
    db_session.add(segundo_trabajo)
    db_session.commit()
    resultado = ejecutar_auditoria(db_session, segundo_trabajo)

    categorias = {h["categoria"] for h in resultado["hallazgos"]}
    assert "lineas_cambian_sin_cambiar_documentos" not in categorias
    hallazgo = next(
        h for h in resultado["hallazgos"] if h["categoria"] == "lineas_bajan_explicado_por_reextraccion"
    )
    assert hallazgo["gravedad"] == "aviso"
    assert exp.codigo_expediente in hallazgo["expedientes"]


def test_una_subida_sigue_siendo_error_aunque_la_reextraccion_creara_lineas(db_session):
    """La atribución nueva no puede convertirse en una puerta de atrás: una
    SUBIDA de recuento sin que cambien los documentos es el síntoma que
    motivó esta comprobación, y el balance de la reextracción nunca la
    excusa."""
    exp = _expediente(db_session, huella_documentos="hash-estable")
    lote = _lote(db_session, exp.id)
    for i in range(3):
        _linea(db_session, exp.id, lote.id, clave_linea=f"P-{i}", codigo_precio=f"P-{i}",
               precio_unitario=Decimal("10"))

    hace_una_hora = datetime.now(timezone.utc) - timedelta(hours=1)
    primera = ejecutar_auditoria(db_session, _trabajo(db_session))
    db_session.add(TrabajoCola(
        tipo=TIPO_TRABAJO, resultado=primera, estado=EstadoTrabajo.completado, created_at=hace_una_hora
    ))
    db_session.commit()

    for i in range(2):
        _linea(db_session, exp.id, lote.id, clave_linea=f"Q-{i}", codigo_precio=f"Q-{i}",
               precio_unitario=Decimal("10"))
    db_session.add(TrabajoCola(
        tipo="extraer_expediente",
        expediente_id=exp.id,
        estado=EstadoTrabajo.completado,
        resultado={"lineas_podadas": 0, "lineas_creadas": 2},
        created_at=hace_una_hora + timedelta(minutes=10),
    ))
    db_session.commit()

    segundo_trabajo = TrabajoCola(tipo=TIPO_TRABAJO, created_at=datetime.now(timezone.utc))
    db_session.add(segundo_trabajo)
    db_session.commit()
    resultado = ejecutar_auditoria(db_session, segundo_trabajo)

    hallazgo = next(
        h for h in resultado["hallazgos"] if h["categoria"] == "lineas_cambian_sin_cambiar_documentos"
    )
    assert hallazgo["gravedad"] == "error"
    assert exp.codigo_expediente in hallazgo["expedientes"]


def test_columna_vacia_crece_mucho_respecto_a_la_ejecucion_anterior(db_session):
    exp = _expediente(db_session)
    lote = _lote(db_session, exp.id)
    for i in range(10):
        _linea(
            db_session, exp.id, lote.id, clave_linea=f"P-{i}", codigo_precio=f"P-{i}",
            precio_unitario=Decimal("10"), unidad_medida="UD.",
        )

    hace_una_hora = datetime.now(timezone.utc) - timedelta(hours=1)
    primera = ejecutar_auditoria(db_session, _trabajo(db_session))
    trabajo1 = TrabajoCola(
        tipo=TIPO_TRABAJO, resultado=primera, estado=EstadoTrabajo.completado, created_at=hace_una_hora
    )
    db_session.add(trabajo1)
    db_session.commit()
    assert primera["vacios_por_columna"]["unidad_medida"] == 0.0

    # La mitad de las líneas pierde la unidad de medida entre ejecuciones.
    for linea in db_session.query(LineaCatalogo).all()[:5]:
        linea.unidad_medida = None
    db_session.commit()

    segundo_trabajo = TrabajoCola(tipo=TIPO_TRABAJO, created_at=datetime.now(timezone.utc))
    db_session.add(segundo_trabajo)
    db_session.commit()
    resultado = ejecutar_auditoria(db_session, segundo_trabajo)

    hallazgo = next(h for h in resultado["hallazgos"] if h["categoria"] == "columna_vacia_crecio")
    assert hallazgo["detalle"]["columna"] == "unidad_medida"


def test_lineas_descartadas_no_cuentan_para_ningun_hallazgo(db_session):
    exp = _expediente(db_session)
    lote = _lote(db_session, exp.id)
    _linea(
        db_session, exp.id, lote.id, clave_linea="P-1", codigo_precio="P-1",
        precio_unitario=Decimal("0"), estado_revision=EstadoRevisionLinea.descartado,
    )

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    assert resultado["total_lineas"] == 0
    assert resultado["hallazgos"] == []


def test_importe_licitacion_compartido_entre_expedientes_distintos(db_session):
    """Encargo del cliente, medición del alcance "Nº Lote: NNN" (2026-09-08):
    dos expedientes que comparten el mismo documento de origen (un Anuncio
    de adjudicación multi-lote) y el mismo importe de licitación son
    sospechosos -- caso real, `6.20/28510.0041` y su familia."""
    exp1 = _expediente(db_session, codigo="6.20/28510.0041")
    exp2 = _expediente(db_session, codigo="6.20/28510.0042")
    documento = _vincular_documento(db_session, exp1.id)
    _vincular_documento(db_session, exp2.id, documento=documento)
    _lote(db_session, exp1.id, importe_licitacion=Decimal("22000000"), importe_adjudicacion=Decimal("500000"))
    _lote(db_session, exp2.id, importe_licitacion=Decimal("22000000"), importe_adjudicacion=Decimal("812000"))

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    hallazgo = next(
        h for h in resultado["hallazgos"] if h["categoria"] == "importe_licitacion_compartido_entre_expedientes"
    )
    assert hallazgo["gravedad"] == "aviso"
    assert set(hallazgo["expedientes"]) == {"6.20/28510.0041", "6.20/28510.0042"}


def test_el_mismo_lote_en_el_principal_y_en_su_expediente_no_da_hallazgo(db_session):
    # Sesión 2026-09-15: `6.22/28510.0033` (principal) y `0058` (su LOTE 2)
    # guardan el mismo lote, con el importe que declara su Contrato.
    principal = _expediente(db_session, codigo="6.22/28510.0033")
    lote_2 = _expediente(db_session, codigo="6.22/28510.0058")
    documento = _vincular_documento(db_session, principal.id)
    _vincular_documento(db_session, lote_2.id, documento=documento)
    for expediente in (principal, lote_2):
        _lote(db_session, expediente.id, identificador="2", importe_licitacion=Decimal("2400000"),
              codigo_expediente_lote="6.22/28510.0058")

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    categorias = {h["categoria"] for h in resultado["hallazgos"]}
    assert "importe_licitacion_compartido_entre_expedientes" not in categorias


def test_lotes_distintos_con_el_mismo_importe_del_mismo_documento_si_dan_hallazgo(db_session):
    principal = _expediente(db_session, codigo="6.22/28510.0033")
    lote_2 = _expediente(db_session, codigo="6.22/28510.0058")
    documento = _vincular_documento(db_session, principal.id)
    _vincular_documento(db_session, lote_2.id, documento=documento)
    _lote(db_session, principal.id, identificador="1", importe_licitacion=Decimal("2400000"),
          codigo_expediente_lote="6.22/28510.0057")
    _lote(db_session, lote_2.id, identificador="2", importe_licitacion=Decimal("2400000"),
          codigo_expediente_lote="6.22/28510.0058")

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    categorias = {h["categoria"] for h in resultado["hallazgos"]}
    assert "importe_licitacion_compartido_entre_expedientes" in categorias


def test_importe_licitacion_distinto_entre_expedientes_no_da_hallazgo(db_session):
    exp1 = _expediente(db_session, codigo="6.20/28510.0041")
    exp2 = _expediente(db_session, codigo="6.20/28510.0042")
    documento = _vincular_documento(db_session, exp1.id)
    _vincular_documento(db_session, exp2.id, documento=documento)
    _lote(db_session, exp1.id, importe_licitacion=Decimal("500000"), importe_adjudicacion=Decimal("500000"))
    _lote(db_session, exp2.id, importe_licitacion=Decimal("812000"), importe_adjudicacion=Decimal("812000"))

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    categorias = {h["categoria"] for h in resultado["hallazgos"]}
    assert "importe_licitacion_compartido_entre_expedientes" not in categorias


def test_importe_licitacion_compartido_sin_documento_comun_no_da_hallazgo(db_session):
    # Mismo importe por coincidencia real, pero documentos de origen
    # distintos -- no es la firma del defecto (dos licitaciones
    # independientes pueden compartir presupuesto por casualidad).
    exp1 = _expediente(db_session, codigo="6.20/28510.0041")
    exp2 = _expediente(db_session, codigo="6.20/28510.0042")
    _vincular_documento(db_session, exp1.id)
    _vincular_documento(db_session, exp2.id)
    _lote(db_session, exp1.id, importe_licitacion=Decimal("500000"))
    _lote(db_session, exp2.id, importe_licitacion=Decimal("500000"))

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    categorias = {h["categoria"] for h in resultado["hallazgos"]}
    assert "importe_licitacion_compartido_entre_expedientes" not in categorias


def test_importe_licitacion_repetido_en_lotes_del_mismo_expediente(db_session):
    exp = _expediente(db_session)
    _lote(db_session, exp.id, identificador="1", importe_licitacion=Decimal("100000"))
    _lote(db_session, exp.id, identificador="2", importe_licitacion=Decimal("100000"))

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    hallazgo = next(
        h for h in resultado["hallazgos"] if h["categoria"] == "importe_licitacion_repetido_en_el_mismo_expediente"
    )
    assert hallazgo["gravedad"] == "aviso"
    assert exp.codigo_expediente in hallazgo["expedientes"]
