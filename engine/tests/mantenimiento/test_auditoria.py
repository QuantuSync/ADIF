"""BLOQUE 1, sesión de auditoría automática (2026-09-08): comprobaciones de
solo lectura sobre el catálogo -- cada test monta el estado mínimo que
dispara (o no) un hallazgo concreto, sin red ni modelo, igual que el resto
de esta cascada."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.extraccion.firma_cabecera import calcular_firma_cabecera
from app.mantenimiento.auditoria import TIPO_TRABAJO, ejecutar_auditoria
from app.models import (
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


def test_lineas_duplicadas_exactas_dentro_del_mismo_lote(db_session):
    exp = _expediente(db_session)
    lote = _lote(db_session, exp.id)
    _linea(
        db_session, exp.id, lote.id, clave_linea="P-1", codigo_precio="P-1",
        matricula="123456789", descripcion="TUERCA", cantidad=Decimal("1"), precio_unitario=Decimal("5"),
    )
    _linea(
        db_session, exp.id, lote.id, clave_linea="P-2", codigo_precio="P-2",
        matricula="123456789", descripcion="TUERCA", cantidad=Decimal("1"), precio_unitario=Decimal("5"),
    )

    resultado = ejecutar_auditoria(db_session, _trabajo(db_session))

    categorias = {h["categoria"] for h in resultado["hallazgos"]}
    assert "lineas_duplicadas_exactas" in categorias
    hallazgo = next(h for h in resultado["hallazgos"] if h["categoria"] == "lineas_duplicadas_exactas")
    assert hallazgo["gravedad"] == "error"
    assert exp.codigo_expediente in hallazgo["expedientes"]


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
