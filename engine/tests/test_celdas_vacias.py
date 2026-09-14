"""`app.celdas_vacias`: el mismo criterio de tres motivos que la web
(no aplica / no consta / pendiente), decidido en el motor para el Excel y la
API (sesión 2026-09-14, continuación)."""
from decimal import Decimal

from app.catalogo import MOTIVO_VALOR_DE_OTRO_LOTE
from app.celdas_vacias import NO_APLICA, NO_CONSTA, PENDIENTE, celdas_vacias, es_partida_alzada
from app.models import LineaCatalogo


def _linea(**campos) -> LineaCatalogo:
    datos = dict(
        matricula="697500900", codigo_material="GUANTE", descripcion="GUANTE", cantidad=Decimal("30"),
        precio_unitario=Decimal("24"), baja_lote=Decimal("0.54"), precio_adjudicado=Decimal("11.04"),
        unidad_medida="UN", motivo_revision=None,
    )
    datos.update(campos)
    return LineaCatalogo(**datos)


def _motivos(linea: LineaCatalogo, lote="1") -> dict:
    return {c.campo: (c.motivo, c.detalle) for c in celdas_vacias(linea, lote)}


def test_linea_completa_no_tiene_celdas_vacias():
    assert celdas_vacias(_linea(), "1") == []


def test_cantidad_de_otro_lote_es_pendiente_y_la_que_falta_no_consta():
    motivo = f"{MOTIVO_VALOR_DE_OTRO_LOTE}, con cantidades distintos: probablemente cuadros de lotes distintos"
    assert _motivos(_linea(cantidad=None, motivo_revision=motivo))["cantidad"][0] == PENDIENTE
    assert _motivos(_linea(cantidad=None))["cantidad"] == (NO_CONSTA, None)


def test_precio_de_otro_lote_deja_el_precio_adjudicado_pendiente_del_precio():
    motivo = f"{MOTIVO_VALOR_DE_OTRO_LOTE}, con precios unitarios distintos: probablemente ..."
    motivos = _motivos(_linea(precio_unitario=None, precio_adjudicado=None, motivo_revision=motivo))
    assert motivos["precio_unitario"][0] == PENDIENTE
    assert motivos["precio_adjudicado"] == (PENDIENTE, "falta el precio unitario")
    assert "cantidad" not in motivos


def test_precio_adjudicado_sin_baja_es_pendiente_de_la_baja():
    motivos = _motivos(_linea(baja_lote=None, precio_adjudicado=None))
    assert motivos["precio_adjudicado"] == (PENDIENTE, "falta la baja del lote")
    assert motivos["baja_lote"] == (NO_CONSTA, None)


def test_partida_alzada_no_aplica_a_matricula_codigo_y_unidad():
    motivos = _motivos(_linea(
        descripcion="  Partida alzada a justificar para imprevistos", matricula=None, codigo_material=None,
        unidad_medida=None,
    ))
    for campo in ("matricula", "codigo_material", "unidad_medida"):
        assert motivos[campo] == (NO_APLICA, "partida alzada")


def test_sin_lote_no_consta():
    assert _motivos(_linea(), lote=None)["lote"] == (NO_CONSTA, None)


def test_es_partida_alzada_igual_que_la_web():
    assert es_partida_alzada("Partida Alzada para imprevistos")
    assert not es_partida_alzada("Tornillo de partida alzada")
    assert not es_partida_alzada(None)
