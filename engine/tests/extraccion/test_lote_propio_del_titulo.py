"""Bloque 3, sesión 2026-09-19 (decisión del cliente): el título del propio
expediente diciendo cuál de los lotes de la licitación es.

`6.22/28510.0011`-`0014` (balasto, 6 lotes) comparten los mismos siete
documentos con sus hermanos y los dos únicos Contratos publicados son los de
los lotes 5 y 6, así que ninguna de las dos vías fuertes los alcanza. Sin
esta regla, el reparto por lotes del cuadro les carga los SEIS cuadros del
ANEJO y cada uno lleva el material de toda la licitación.
"""
import pytest

from app.extraccion.orquestador import (
    _aplicar_lote_propio_del_titulo,
    _lote_declarado_en_el_titulo,
)
from app.models import Expediente, LineaCatalogo, Lote


@pytest.mark.parametrize(
    "titulo, esperado",
    [
        ("Lote 1: Jefatura de Barcelona", "1"),
        ("Lote 4. Corazones de punta fija y contracarriles", "4"),
        ("LOTE 6. PUNTO DE CARGA SANCHIDRIAN", "6"),
        ("Lote nº 2: arrendamiento de vagones zona norte", "2"),
        ("lote 2: cruzamientos y contracarriles", "2"),
        ("Lote 1 Equipos anticaídas", "1"),
        ("Lote 13 - Placas de caucho", "13"),
        # No abre el título: cualquier pliego multi-lote nombra lotes en su
        # prosa y eso no dice de cuál es el expediente.
        ("Suministro de balasto. 6 LOTES", None),
        ("Suministro de elementos de vía. Lote 5: Placas de caucho", None),
        ("Acuerdo marco de suministro de carril", None),
        ("", None),
        (None, None),
    ],
)
def test_solo_cuenta_el_lote_que_abre_el_titulo(titulo, esperado):
    assert _lote_declarado_en_el_titulo(Expediente(nombre_proyecto=titulo)) == esperado


def _expediente_con_lotes(db_session, codigo, titulo, identificadores, **por_lote):
    expediente = Expediente(codigo_expediente=codigo, nombre_proyecto=titulo)
    db_session.add(expediente)
    db_session.commit()
    for identificador in identificadores:
        lote = Lote(expediente_id=expediente.id, identificador_lote=identificador, **por_lote.get(identificador, {}))
        db_session.add(lote)
        db_session.commit()
        db_session.add(LineaCatalogo(
            lote_id=lote.id, expediente_id=expediente.id,
            clave_linea=f"P-{identificador}", orden_aparicion=int(identificador),
            descripcion=f"material del lote {identificador}",
        ))
    db_session.commit()
    return expediente


def test_0011_se_queda_solo_con_el_cuadro_de_su_lote(db_session):
    expediente = _expediente_con_lotes(
        db_session, "6.22/28510.0011", "Lote 1: Jefatura de Barcelona", ["1", "2", "3", "4", "5", "6"]
    )
    assert _aplicar_lote_propio_del_titulo(db_session, expediente, "1") == "1"
    db_session.refresh(expediente)
    assert [l.identificador_lote for l in expediente.lotes] == ["1"]
    # Las líneas de los lotes hermanos se van con su lote: no se quedan
    # huérfanas colgando de este expediente.
    assert db_session.query(LineaCatalogo).filter_by(expediente_id=expediente.id).count() == 1


def test_un_expediente_de_un_solo_lote_no_se_toca(db_session):
    """La regla existe para el expediente que carga con VARIOS cuadros. Con
    uno solo no hay nada que quitar, y activar `lote_propio` ahí sería otro
    cambio con otro alcance -- `6.21/28510.0109`, cuyo único lote es el
    sentinela "1" y cuyo título dice, por casualidad, "Lote 1."."""
    expediente = _expediente_con_lotes(
        db_session, "6.21/28510.0109", "Lote 1. Semicambios, agujas y contraagujas", ["1"]
    )
    assert _aplicar_lote_propio_del_titulo(db_session, expediente, "1") is None
    assert [l.identificador_lote for l in expediente.lotes] == ["1"]


def test_si_el_lote_del_titulo_no_esta_entre_sus_lotes_no_se_inventa_ninguno(db_session):
    """`6.21/28510.0135` dice "Lote 6" y sus lotes guardados son el 1, el 3 y
    el 7: se queda exactamente como está."""
    expediente = _expediente_con_lotes(
        db_session, "6.21/28510.0135", "Lote 6. Placas asiento PAE", ["1", "3", "7"]
    )
    assert _aplicar_lote_propio_del_titulo(db_session, expediente, "6") is None
    assert sorted(l.identificador_lote for l in expediente.lotes) == ["1", "3", "7"]


def test_un_lote_con_dato_propio_no_lo_borra_el_titulo(db_session):
    """Contra un documento el título no manda: un lote con baja, importe o
    código de expediente de lote lo declaró un documento, no el reparto del
    cuadro."""
    from decimal import Decimal

    expediente = _expediente_con_lotes(
        db_session, "6.22/28510.0011", "Lote 1: Jefatura de Barcelona", ["1", "2"],
        **{"2": {"baja_lote": Decimal("0.05")}},
    )
    assert _aplicar_lote_propio_del_titulo(db_session, expediente, "1") is None
    assert sorted(l.identificador_lote for l in expediente.lotes) == ["1", "2"]
