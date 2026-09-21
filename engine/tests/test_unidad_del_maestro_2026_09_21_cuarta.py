"""Sesión 2026-09-21 (cuarta parte), bloque 1: la unidad del maestro de materiales dentro del
proceso automático.

Hasta ahora era un paso manual (`completar-unidades`) que no se volvía a lanzar
tras cargar el maestro: las líneas nuevas se quedaban sin la unidad que el
maestro sí trae. Ahora la aplica el guardado de cada documento, sobre la fila
terminada. La unidad del documento manda siempre, y la fila del Excel dice
cuándo la unidad viene del maestro.
"""
from app.catalogo import construir_linea_catalogo, guardar_lineas_catalogo
from app.exportacion import TEXTO_UNIDAD_DEL_MAESTRO, _texto_celdas_vacias
from app.extraccion.maestro_materiales import completar_unidades_desde_maestro
from app.models import Expediente, LineaCatalogo, Lote, MaestroMaterial

_MAPEO = {
    "codigo_precio": 0,
    "matricula": 1,
    "descripcion": 2,
    "unidad_medida": 3,
    "cantidad": 4,
    "precio_unitario": 5,
}


def _lote(db_session, codigo="6.22/28510.9001"):
    expediente = Expediente(codigo_expediente=codigo)
    db_session.add(expediente)
    db_session.commit()
    lote = Lote(expediente_id=expediente.id, identificador_lote="1")
    db_session.add(lote)
    db_session.commit()
    return lote


def _maestro(db_session, matricula, unidad="UN"):
    db_session.add(MaestroMaterial(matricula=matricula, descripcion="X", unidad_medida=unidad))
    db_session.commit()


def _guardar(db_session, lote, filas):
    lineas = [
        construir_linea_catalogo(
            fila, _MAPEO, pagina=3, documento_origen_id=None, expediente_id=lote.expediente_id,
            baja_lote=None, orden_aparicion=orden,
        )
        for orden, fila in enumerate(filas)
    ]
    guardar_lineas_catalogo(db_session, lote.id, lineas)
    db_session.commit()
    return db_session.query(LineaCatalogo).filter_by(lote_id=lote.id).one()


def test_la_fila_sin_unidad_la_toma_del_maestro_al_guardarse(db_session):
    _maestro(db_session, "612860020", "P")
    lote = _lote(db_session)

    linea = _guardar(db_session, lote, [["P-1", "612860020", "PLACA NERVADA PN-60", "", "4", "69,82"]])

    assert linea.unidad_medida == "P"
    assert linea.unidad_medida_completada_desde_maestro is True


def test_la_unidad_del_documento_manda_sobre_la_del_maestro(db_session):
    _maestro(db_session, "603000210", "UN")
    lote = _lote(db_session)

    linea = _guardar(db_session, lote, [["P-1", "603000210", "TORNILLO", "Kg", "4", "1,00"]])

    assert linea.unidad_medida == "kg"
    assert not linea.unidad_medida_completada_desde_maestro
    assert linea.unidad_medida_discrepancia_maestro == "UN"


def test_si_el_documento_trae_la_unidad_despues_la_marca_del_maestro_se_quita(db_session):
    _maestro(db_session, "603000210", "UN")
    lote = _lote(db_session)
    linea = _guardar(db_session, lote, [["P-1", "603000210", "TORNILLO", "", "4", "1,00"]])
    assert linea.unidad_medida_completada_desde_maestro is True

    linea = _guardar(db_session, lote, [["P-1", "603000210", "TORNILLO", "m", "4", "1,00"]])

    assert linea.unidad_medida == "m"
    assert not linea.unidad_medida_completada_desde_maestro


def test_la_unidad_del_maestro_se_retira_si_la_matricula_deja_de_figurar(db_session):
    _maestro(db_session, "603000210", "UN")
    lote = _lote(db_session)
    linea = _guardar(db_session, lote, [["P-1", "603000210", "TORNILLO", "", "4", "1,00"]])
    db_session.query(MaestroMaterial).filter_by(matricula="603000210").delete()
    _maestro(db_session, "111111111")

    completar_unidades_desde_maestro(db_session)

    db_session.refresh(linea)
    assert linea.unidad_medida is None
    assert not linea.unidad_medida_completada_desde_maestro


def test_la_partida_alzada_no_recibe_unidad_del_maestro(db_session):
    _maestro(db_session, "603000210", "UN")
    lote = _lote(db_session)

    linea = _guardar(db_session, lote, [["P-1", "603000210", "PARTIDA ALZADA", "PA", "1", "500,00"]])

    assert linea.unidad_medida is None
    assert not linea.unidad_medida_completada_desde_maestro


def test_sin_maestro_cargado_no_toca_nada(db_session):
    lote = _lote(db_session)

    linea = _guardar(db_session, lote, [["P-1", "603000210", "TORNILLO", "", "4", "1,00"]])

    assert linea.unidad_medida is None
    assert not linea.unidad_medida_completada_desde_maestro


def test_la_fila_del_excel_dice_que_la_unidad_viene_del_maestro(db_session):
    _maestro(db_session, "612860020", "P")
    lote = _lote(db_session)
    linea = _guardar(db_session, lote, [["P-1", "612860020", "PLACA NERVADA PN-60", "", "4", "69,82"]])

    texto = _texto_celdas_vacias(linea, "1")

    assert TEXTO_UNIDAD_DEL_MAESTRO in texto
    assert "Unidad de medida: no consta" not in texto


def test_la_fila_con_unidad_del_documento_no_lleva_la_nota(db_session):
    _maestro(db_session, "603000210", "UN")
    lote = _lote(db_session)
    linea = _guardar(db_session, lote, [["P-1", "603000210", "TORNILLO", "ud", "4", "1,00"]])

    assert TEXTO_UNIDAD_DEL_MAESTRO not in (_texto_celdas_vacias(linea, "1") or "")


# --------------------------------------------------------------------------
# Bloque 2 — la nota de la cantidad mínima por pedido en `6.19/28510.0177`
# p.22: su tabla empieza en una fila con dos matrículas en la misma celda,
# que se tomaba por cabecera y cerraba el cuadro de la nota.
# --------------------------------------------------------------------------


def test_una_celda_con_varias_matriculas_es_una_fila_de_datos():
    from app.extraccion.pipeline_anejo import _es_celda_de_matriculas

    assert _es_celda_de_matriculas("64315045O 64810014Z")
    assert _es_celda_de_matriculas("643150450")
    assert _es_celda_de_matriculas("643150 450")
    assert not _es_celda_de_matriculas("Nº MATRICULA")
    assert not _es_celda_de_matriculas("10 10")
    assert not _es_celda_de_matriculas(None)
