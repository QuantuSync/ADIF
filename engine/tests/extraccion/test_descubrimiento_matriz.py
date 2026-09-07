"""Descubrimiento inverso matriz -> pedidos (sesión de descubrimiento
inverso): cubre app.extraccion.descubrimiento_matriz contra un doble de
`app.scraping.pcsp.descubrir_candidatos_acuerdo_marco` (nunca Playwright real
en un test) -- la búsqueda y lectura de fichas en sí ya se verificó en vivo
contra la Plataforma real durante la sesión, no hace falta reproducirlo
aquí."""
from __future__ import annotations

from app.extraccion.descubrimiento_matriz import (
    MOTIVO_SIN_ADJUDICATARIO,
    descubrir_pedidos_de_matriz,
    matrices_conocidas,
)
from app.models import CandidatoAcuerdoMarco, EstadoTrabajo, Expediente, Lote, TrabajoCola
from app.extraccion.orquestador import LOTE_UNICO


def _crear_expediente(db, codigo_expediente, **campos) -> Expediente:
    expediente = Expediente(codigo_expediente=codigo_expediente, **campos)
    db.add(expediente)
    db.commit()
    db.refresh(expediente)
    return expediente


def _crear_lote(db, expediente_id, identificador_lote=LOTE_UNICO, **campos) -> Lote:
    lote = Lote(expediente_id=expediente_id, identificador_lote=identificador_lote, **campos)
    db.add(lote)
    db.commit()
    db.refresh(lote)
    return lote


def _parchear_busqueda(monkeypatch, respuestas: dict):
    """`respuestas`: {adjudicatario: (candidatos, nuevas_verificaciones)}.
    Registra cada llamada (adjudicatario, ya_verificados_copia) en `llamadas`
    para que los tests puedan comprobar qué se pidió de verdad."""
    llamadas = []

    async def falso(adjudicatario, ya_verificados, organo="ADIF"):
        llamadas.append((adjudicatario, set(ya_verificados), organo))
        return respuestas.get(adjudicatario, ([], {}))

    import app.extraccion.descubrimiento_matriz as modulo
    monkeypatch.setattr(modulo, "descubrir_candidatos_acuerdo_marco", falso)
    return llamadas


def test_sin_adjudicatario_se_senala_y_no_busca(db_session, monkeypatch):
    llamadas = _parchear_busqueda(monkeypatch, {})
    matriz = _crear_expediente(db_session, "6.23/28510.0018")
    _crear_lote(db_session, matriz.id)  # sin adjudicatario

    resumen = descubrir_pedidos_de_matriz(db_session, matriz)

    assert resumen.omitido is True
    assert resumen.motivo_omitido == MOTIVO_SIN_ADJUDICATARIO
    assert llamadas == []
    db_session.refresh(matriz)
    assert matriz.aviso_descubrimiento_pedidos == MOTIVO_SIN_ADJUDICATARIO


def test_busca_por_cada_adjudicatario_distinto_de_la_matriz(db_session, monkeypatch):
    # Ajuste 1 del encargo: un acuerdo marco puede repartir sus lotes entre
    # varios adjudicatarios -- se busca una vez por cada uno, no solo el del
    # primer lote.
    llamadas = _parchear_busqueda(monkeypatch, {
        "ARCELORMITTAL ESPAÑA SA": (["6.24/28510.0040"], {"6.24/28510.0040": "6.23/28510.0018"}),
        "OTRO PROVEEDOR SA": (["3.24/00000.0001"], {"3.24/00000.0001": "otro/expediente"}),
    })
    matriz = _crear_expediente(db_session, "6.23/28510.0018")
    _crear_lote(db_session, matriz.id, identificador_lote="1", adjudicatario="ARCELORMITTAL ESPAÑA SA")
    _crear_lote(db_session, matriz.id, identificador_lote="2", adjudicatario="OTRO PROVEEDOR SA")

    resumen = descubrir_pedidos_de_matriz(db_session, matriz)

    adjudicatarios_llamados = {a for a, _, _ in llamadas}
    assert adjudicatarios_llamados == {"ARCELORMITTAL ESPAÑA SA", "OTRO PROVEEDOR SA"}
    assert resumen.pedidos_nuevos == 1  # solo el candidato cuya matriz declarada coincide
    pedido = db_session.query(Expediente).filter_by(codigo_expediente="6.24/28510.0040").one()
    assert pedido.matriz_expediente_id == matriz.id
    assert db_session.query(Expediente).filter_by(codigo_expediente="3.24/00000.0001").one_or_none() is None


def test_registra_pedido_nuevo_y_encola_su_descarga(db_session, monkeypatch):
    _parchear_busqueda(monkeypatch, {
        "ARCELORMITTAL ESPAÑA SA": (["6.24/28510.0040"], {"6.24/28510.0040": "6.23/28510.0018"}),
    })
    matriz = _crear_expediente(db_session, "6.23/28510.0018")
    _crear_lote(db_session, matriz.id, adjudicatario="ARCELORMITTAL ESPAÑA SA")

    resumen = descubrir_pedidos_de_matriz(db_session, matriz)

    assert resumen.pedidos_nuevos == 1
    pedido = db_session.query(Expediente).filter_by(codigo_expediente="6.24/28510.0040").one()
    assert pedido.codigo_matriz == "6.23/28510.0018"
    trabajo = db_session.query(TrabajoCola).filter_by(expediente_id=pedido.id).one()
    assert trabajo.tipo == "descargar_expediente"
    assert trabajo.estado == EstadoTrabajo.pendiente


def test_candidato_de_otra_matriz_no_se_registra(db_session, monkeypatch):
    # Mismo adjudicatario, acuerdo marco DISTINTO (verificado real en la
    # sesión: ArcelorMittal tiene más de un acuerdo marco de carril con ADIF
    # a lo largo de los años) -- no basta con que el candidato aparezca en la
    # búsqueda, su propia ficha tiene que declarar ESTA matriz.
    _parchear_busqueda(monkeypatch, {
        "ARCELORMITTAL ESPAÑA SA": (["3.26/27510.0061"], {"3.26/27510.0061": "3.25/27510.0123"}),
    })
    matriz = _crear_expediente(db_session, "6.23/28510.0018")
    _crear_lote(db_session, matriz.id, adjudicatario="ARCELORMITTAL ESPAÑA SA")

    resumen = descubrir_pedidos_de_matriz(db_session, matriz)

    assert resumen.pedidos_nuevos == 0
    assert db_session.query(Expediente).filter_by(codigo_expediente="3.26/27510.0061").one_or_none() is None


def test_usa_cache_sin_reverificar_un_candidato_ya_conocido(db_session, monkeypatch):
    db_session.add(CandidatoAcuerdoMarco(
        codigo_expediente_candidato="6.24/28510.0040", codigo_matriz_declarado="6.23/28510.0018",
    ))
    db_session.commit()
    llamadas = _parchear_busqueda(monkeypatch, {
        # La búsqueda sigue devolviendo el candidato (sigue matcheando el
        # filtro), pero no debería pedirse su verificación de nuevo.
        "ARCELORMITTAL ESPAÑA SA": (["6.24/28510.0040"], {}),
    })
    matriz = _crear_expediente(db_session, "6.23/28510.0018")
    _crear_lote(db_session, matriz.id, adjudicatario="ARCELORMITTAL ESPAÑA SA")

    resumen = descubrir_pedidos_de_matriz(db_session, matriz)

    assert "6.24/28510.0040" in llamadas[0][1]  # ya_verificados incluía el candidato cacheado
    assert resumen.candidatos_verificados_ahora == 0
    assert resumen.pedidos_nuevos == 1
    assert db_session.query(CandidatoAcuerdoMarco).count() == 1  # no se duplicó la fila de caché


def test_pedido_ya_enlazado_no_se_duplica(db_session, monkeypatch):
    _parchear_busqueda(monkeypatch, {
        "ARCELORMITTAL ESPAÑA SA": (["6.24/28510.0040"], {"6.24/28510.0040": "6.23/28510.0018"}),
    })
    matriz = _crear_expediente(db_session, "6.23/28510.0018")
    _crear_lote(db_session, matriz.id, adjudicatario="ARCELORMITTAL ESPAÑA SA")
    _crear_expediente(db_session, "6.24/28510.0040", codigo_matriz="6.23/28510.0018", matriz_expediente_id=matriz.id)

    resumen = descubrir_pedidos_de_matriz(db_session, matriz)

    assert resumen.pedidos_nuevos == 0
    assert resumen.pedidos_ya_conocidos == 1
    assert db_session.query(Expediente).filter_by(codigo_expediente="6.24/28510.0040").count() == 1
    assert db_session.query(TrabajoCola).count() == 0


def test_matrices_conocidas_solo_devuelve_las_que_tienen_algun_pedido(db_session):
    matriz = _crear_expediente(db_session, "6.23/28510.0018")
    _crear_expediente(db_session, "6.24/28510.0040", matriz_expediente_id=matriz.id)
    _crear_expediente(db_session, "6.24/28510.9999")  # expediente normal, no es matriz de nadie

    resultado = matrices_conocidas(db_session)

    assert [e.codigo_expediente for e in resultado] == ["6.23/28510.0018"]
