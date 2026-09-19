"""`app.celdas_vacias`: el mismo criterio de tres motivos que la web
(no aplica / no consta / pendiente), decidido en el motor para el Excel y la
API (sesión 2026-09-14, continuación)."""
from decimal import Decimal

from app.catalogo import MOTIVO_VALOR_DE_OTRO_LOTE
from app.celdas_vacias import NO_APLICA, NO_CONSTA, PENDIENTE, celdas_vacias, es_partida_alzada
from app.models import LineaCatalogo


def _linea(**campos) -> LineaCatalogo:
    datos = dict(
        codigo_precio="P-001",
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


# --- Columnas del expediente (sesión 2026-09-18, bloque 2) -------------------
# Hasta esta sesión, una celda vacía en "Código interno", "Código matriz",
# "Título expediente" o "Estado del contrato (SAP)" no tenía motivo en ninguna
# parte del entregable.


def _expediente(**campos):
    from app.models import Expediente

    datos = dict(
        codigo_expediente="6.26/28510.0016", codigo_interno="24036", codigo_matriz="6.25/28510.0016",
        nombre_proyecto="Suministro de carril", estado_contrato_sap="En ejecución", codigos_cruzados=True,
    )
    datos.update(campos)
    return Expediente(**datos)


def test_sin_expediente_no_aparece_ningun_motivo_de_columna_de_expediente():
    """La web llama con dos argumentos y no debe cambiar de comportamiento."""
    assert celdas_vacias(_linea(), "1") == []


def test_expediente_completo_no_anade_ningun_motivo():
    assert celdas_vacias(_linea(), "1", _expediente()) == []


def test_codigo_interno_vacio_sin_cruce_dice_que_no_esta_en_el_listado():
    motivos = {
        c.campo: (c.motivo, c.detalle)
        for c in celdas_vacias(_linea(), "1", _expediente(codigo_interno=None, codigos_cruzados=False))
    }
    assert motivos["codigo_interno"][0] == NO_CONSTA
    assert "no aparece en el listado de códigos de ADIF" in motivos["codigo_interno"][1]


def test_codigo_interno_vacio_con_cruce_dice_que_el_listado_no_lo_trae():
    motivos = {
        c.campo: (c.motivo, c.detalle)
        for c in celdas_vacias(_linea(), "1", _expediente(codigo_interno=None, codigos_cruzados=True))
    }
    assert "no trae número interno" in motivos["codigo_interno"][1]


def test_codigo_matriz_titulo_y_estado_sap_vacios_tienen_motivo():
    motivos = {
        c.campo: (c.motivo, c.detalle)
        for c in celdas_vacias(
            _linea(), "1",
            _expediente(codigo_matriz=None, nombre_proyecto=None, estado_contrato_sap=None),
        )
    }
    assert motivos["codigo_matriz"][0] == NO_CONSTA
    assert "acuerdo marco" in motivos["codigo_matriz"][1]
    assert motivos["titulo_expediente"][0] == NO_CONSTA
    assert motivos["estado_contrato_sap"][0] == NO_CONSTA
    assert "SAP" in motivos["estado_contrato_sap"][1]


def test_los_motivos_del_expediente_no_usan_jerga_interna():
    """El texto lo lee alguien de almacenes: nada de nombres de campo ni de
    vocabulario del sistema (encargo del cliente, sesión 2026-09-18)."""
    textos = " ".join(
        c.detalle or ""
        for c in celdas_vacias(
            _linea(), "1",
            _expediente(codigo_interno=None, codigo_matriz=None, nombre_proyecto=None,
                        estado_contrato_sap=None, codigos_cruzados=False),
        )
    ).lower()
    for jerga in ("cruce", "cruzad", "codigos_cruzados", "índice", "payload", "null", "none", "campo"):
        assert jerga not in textos, f"jerga interna en el texto al cliente: {jerga!r}"


# --- Bloque 2, sesión 2026-09-18: la tercera causa de "Código interno" vacío


def test_codigo_interno_vacio_por_fila_ajena_tiene_su_propio_motivo():
    """El expediente SÍ encuentra fila en el listado de ADIF, pero es la de
    otro expediente de su familia: su número interno es el de ese otro, y
    heredarlo llevaría a almacenes al expediente equivocado."""
    motivos = {
        c.campo: (c.motivo, c.detalle)
        for c in celdas_vacias(
            _linea(), "1",
            _expediente(codigo_interno=None, codigos_cruzados=True, cruce_fila_propia=False),
        )
    }
    assert motivos["codigo_interno"] == (
        NO_CONSTA, "este expediente no figura por sí mismo en el listado de códigos de ADIF"
    )


def test_las_otras_dos_causas_de_codigo_interno_vacio_no_cambian():
    sin_cruce = {
        c.campo: c.detalle
        for c in celdas_vacias(_linea(), "1", _expediente(codigo_interno=None, codigos_cruzados=False))
    }
    assert sin_cruce["codigo_interno"] == "este expediente no aparece en el listado de códigos de ADIF"
    cruza_sin_numero = {
        c.campo: c.detalle
        for c in celdas_vacias(
            _linea(), "1",
            _expediente(codigo_interno=None, codigos_cruzados=True, cruce_fila_propia=True),
        )
    }
    assert cruza_sin_numero["codigo_interno"] == (
        "el listado de códigos de ADIF no trae número interno para este expediente"
    )


def test_el_motivo_de_la_fila_ajena_tampoco_usa_jerga_interna():
    textos = " ".join(
        c.detalle or ""
        for c in celdas_vacias(
            _linea(), "1",
            _expediente(codigo_interno=None, codigos_cruzados=True, cruce_fila_propia=False),
        )
    ).lower()
    for jerga in ("cruce", "cruzad", "codigos_cruzados", "índice", "payload", "null", "none", "campo"):
        assert jerga not in textos, f"jerga interna en el texto al cliente: {jerga!r}"


# --- Bloque 7, sesión 2026-09-18 (continuación): segunda familia de precio ---


def test_precio_indexado_por_pedido_no_es_un_dato_que_falte():
    """`6.26/28510.0014` y los demás pedidos de los acuerdos marco de carril
    (CONTEXTO.md sección 16). No tienen una baja única **por diseño del
    contrato**: decir "no consta" manda al cliente a buscar en la Plataforma
    un número que nunca se publicó."""
    from app.models import ModeloPrecio

    motivos = {
        c.campo: (c.motivo, c.detalle)
        for c in celdas_vacias(
            _linea(baja_lote=None, precio_adjudicado=None), "1",
            modelo_precio=ModeloPrecio.indexado_por_pedido,
        )
    }
    assert motivos["baja_lote"][0] == NO_APLICA
    assert motivos["precio_adjudicado"][0] == NO_APLICA
    assert "fuera de la Plataforma" in motivos["baja_lote"][1]


def test_sin_modelo_indexado_la_baja_vacia_sigue_siendo_no_consta():
    motivos = {
        c.campo: (c.motivo, c.detalle)
        for c in celdas_vacias(_linea(baja_lote=None, precio_adjudicado=None), "1")
    }
    assert motivos["baja_lote"][0] == NO_CONSTA
    assert motivos["precio_adjudicado"] == (PENDIENTE, "falta la baja del lote")
