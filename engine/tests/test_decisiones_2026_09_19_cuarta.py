"""Sesión 2026-09-19 (cuarta parte) -- las dos decisiones que el cliente
manda aplicar.

3. El espacio mapeado al signo `!` en `4.26/28510.0005`, con la condición de
   que todos los `!` de esa fuente sean espacios (demostrado: 137.832 `!` y 0
   espacios en los ocho subconjuntos de Calibri de ese documento) y sin tocar
   los ocho `!` de la p.49, que son la letra "j" de una fuente sin tabla
   `ToUnicode`.
4. El precio adjudicado no se calcula antes de conocer la baja de su lote.
"""
from decimal import Decimal

import pytest

from app.catalogo import (
    _recomponer_espacios_del_signo_admiracion,
    recalcular_precio_adjudicado,
)
from app.models import EstadoExpediente, Expediente, LineaCatalogo, Lote


# ---------------------------------------------------------------------------
# 3 -- el espacio mapeado a "!"
# ---------------------------------------------------------------------------

def test_recompone_los_cinco_conceptos_de_4_26_28510_0005():
    casos = {
        "Precio!Mensual!de!Mantenimiento!": "Precio Mensual de Mantenimiento",
        "Hora!Técnico!jornada!laboral!": "Hora Técnico jornada laboral",
        "Hora!Técnico!jornada!nocturna!": "Hora Técnico jornada nocturna",
        "Hora!Técnico!jornada!festiva!": "Hora Técnico jornada festiva",
        "Gestión!de!reparación!": "Gestión de reparación",
    }
    for bruto, esperado in casos.items():
        assert _recomponer_espacios_del_signo_admiracion(bruto) == esperado


def test_una_celda_con_un_espacio_de_verdad_no_se_toca():
    """Si la celda ya trae un separador real, el `!` podría ser una
    exclamación legítima y no se decide nada. Medido: en las 39.651 líneas del
    corpus no hay ni una descripción con `!` y espacio a la vez."""
    texto = "ATENCIÓN! revisar antes de instalar"
    assert _recomponer_espacios_del_signo_admiracion(texto) == texto


def test_un_solo_signo_no_basta():
    texto = "TORNILLO!"
    assert _recomponer_espacios_del_signo_admiracion(texto) == texto


def test_los_glifos_sin_tabla_de_caracteres_no_se_tocan():
    """Los ocho `!` de la p.49 del contrato son la letra "j" ("juicio",
    "mejor", "baja", "adjudicación") en una fuente sin `ToUnicode`, y su texto
    sale como `(cid:NN)`. Ese mundo es el de `app.extraccion.glifos_cid`."""
    texto = "(cid:5)(cid:26)!(cid:29)(cid:4)(cid:20)(cid:4)(cid:16)"
    assert _recomponer_espacios_del_signo_admiracion(texto) == texto


def test_una_descripcion_normal_no_cambia():
    texto = "BRIDA DE UNIÓN PARA CARRIL 54E1"
    assert _recomponer_espacios_del_signo_admiracion(texto) == texto


# ---------------------------------------------------------------------------
# 4 -- el precio adjudicado, después de la baja de su lote
# ---------------------------------------------------------------------------

def _expediente_con_linea(db_session, baja, precio, adjudicado):
    expediente = Expediente(
        codigo_expediente="6.24/28510.0008", estado=EstadoExpediente.pendiente_revision
    )
    db_session.add(expediente)
    db_session.flush()
    lote = Lote(expediente_id=expediente.id, identificador_lote="1", baja_lote=baja)
    db_session.add(lote)
    db_session.flush()
    linea = LineaCatalogo(
        expediente_id=expediente.id, lote_id=lote.id, clave_linea="P-001",
        orden_aparicion=1, codigo_precio="P-001", descripcion="GUANTE CONTRA RIESGO ELECTRICO",
        precio_unitario=precio, precio_adjudicado=adjudicado, baja_lote=baja,
    )
    db_session.add(linea)
    db_session.commit()
    return expediente, linea


def test_rellena_el_adjudicado_que_faltaba(db_session):
    """El caso real de `6.24/28510.0008`: su baja del 54 % llega por la
    herencia de su acuerdo marco, después de que sus líneas ya estén
    guardadas, así que tenían precio y no adjudicado."""
    expediente, linea = _expediente_con_linea(
        db_session, Decimal("0.540000"), Decimal("24.0000"), None
    )
    assert recalcular_precio_adjudicado(db_session, expediente.id) == 1
    db_session.commit()
    assert linea.precio_adjudicado == Decimal("11.0400")


def test_no_cuenta_como_cambio_lo_que_ya_estaba_bien(db_session):
    """Sin esto, cada pasada marcaría como cambiada cada línea del corpus: el
    valor recién derivado trae más decimales que el guardado."""
    expediente, _ = _expediente_con_linea(
        db_session, Decimal("0.540000"), Decimal("24.0000"), Decimal("11.0400")
    )
    assert recalcular_precio_adjudicado(db_session, expediente.id) == 0


def test_un_lote_sin_baja_deja_la_linea_sin_adjudicado(db_session):
    """El adjudicado se rederiva desde cero en cada pasada (decisión de la
    sesión 2026-09-09): un lote que pierde su baja tiene que dejar sus líneas
    sin adjudicado, no quedarse con el valor viejo."""
    expediente, linea = _expediente_con_linea(
        db_session, None, Decimal("24.0000"), Decimal("11.0400")
    )
    assert recalcular_precio_adjudicado(db_session, expediente.id) == 1
    db_session.commit()
    assert linea.precio_adjudicado is None


def test_una_linea_sin_precio_no_gana_adjudicado(db_session):
    expediente, linea = _expediente_con_linea(
        db_session, Decimal("0.540000"), None, None
    )
    assert recalcular_precio_adjudicado(db_session, expediente.id) == 0
    assert linea.precio_adjudicado is None


def test_una_huerfana_sin_lote_no_se_toca(db_session):
    """Sin lote no hay baja de la que derivar, y las huérfanas no llegan al
    entregable: se dejan como están."""
    expediente = Expediente(
        codigo_expediente="6.21/28510.0112", estado=EstadoExpediente.pendiente_revision
    )
    db_session.add(expediente)
    db_session.flush()
    linea = LineaCatalogo(
        expediente_id=expediente.id, lote_id=None, clave_linea="P-1",
        orden_aparicion=1, descripcion="PIEZA HUÉRFANA",
        precio_unitario=Decimal("10.0000"), precio_adjudicado=Decimal("9.0000"),
        baja_lote=Decimal("0.100000"),
    )
    db_session.add(linea)
    db_session.commit()
    assert recalcular_precio_adjudicado(db_session, expediente.id) == 0
    assert linea.precio_adjudicado == Decimal("9.0000")


def test_la_baja_de_la_linea_se_alinea_con_la_de_su_lote(db_session):
    """"No hay una baja distinta por material dentro de un lote"
    (CONTEXTO.md sección 4)."""
    expediente, linea = _expediente_con_linea(
        db_session, Decimal("0.540000"), Decimal("24.0000"), Decimal("11.0400")
    )
    linea.baja_lote = Decimal("0.100000")
    db_session.commit()
    assert recalcular_precio_adjudicado(db_session, expediente.id) == 1
    db_session.commit()
    assert linea.baja_lote == Decimal("0.540000")
