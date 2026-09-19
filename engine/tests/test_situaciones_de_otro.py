"""Bloque 5, sesión 2026-09-19 (tercera parte) -- los 26 de la situación
"Otro", desglosados por su causa real.

Condición del cliente: una situación nueva solo si hay al menos 3 expedientes
del mismo tipo. Los 26 dan tres grupos que la cumplen (14 de cobertura parcial
de lotes, 5 cuyo acuerdo marco tampoco publica precios, 4 cuyos documentos son
de sus hermanos) y dos que no (2 y 1), que se quedan en "Otro" con su motivo
técnico a la vista, que es para lo que "Otro" existe.

El orden de las ramas se prueba aquí porque un motivo real puede traer los
tres textos a la vez: el de un pedido cuya matriz tampoco tiene cuadro
arrastra íntegro el motivo de la matriz (caso real `6.19/28510.0210`).
"""
from app.conciliacion import (
    BAJA_SOLO_EN_DOCUMENTO_DE_HERMANO,
    COBERTURA_PARCIAL_DE_LOTES,
    MATRIZ_TAMPOCO_PUBLICA,
    OTRO,
    SITUACIONES,
    _situacion,
)
from app.models import EstadoExpediente, Expediente

# Motivos técnicos literales, copiados de la base de datos real.
MOTIVO_COBERTURA = (
    "cobertura parcial: 1 de 5 lotes declarados tienen baja/importe (con datos: 5); "
    "ANEJO_1.pdf: página 16: banda vacía: posible continuación de tabla partida entre páginas"
)
MOTIVO_HERMANO = (
    "2 baja(s) declarada(s) en documento(s) compartido(s) con expediente(s) hermano(s) (cada "
    "documento declara explícitamente su propio 'Contrato nº', ninguno coincide con el de este "
    "expediente) -- ninguna se usa, para no atribuir la baja de otro lote; cobertura parcial: 0 de "
    "3 lotes identificados por número"
)
MOTIVO_MATRIZ = (
    "la matriz 6.19/28510.0179 tampoco tiene cuadro de precios ni baja: " + MOTIVO_HERMANO
)
MOTIVO_LOTES_AGRUPADOS = (
    "el Anuncio de adjudicación agrupa varios lotes en un solo documento (Nº Lote: 001/002/003/004) "
    "y no se pudo identificar con confianza a cuál pertenece este expediente"
)


def _expediente(motivo: str, codigo_matriz: str | None = None) -> Expediente:
    from datetime import datetime, timezone

    ahora = datetime(2026, 9, 19, tzinfo=timezone.utc)
    return Expediente(
        codigo_expediente="6.19/28510.0210",
        codigo_matriz=codigo_matriz,
        estado=EstadoExpediente.pendiente_revision,
        error=motivo,
        descargado_en=ahora,
        extraido_en=ahora,
    )


def _sit(motivo: str, codigo_matriz: str | None = None) -> str:
    return _situacion(_expediente(motivo, codigo_matriz), 0, 5, 0, None)[0]


def test_cobertura_parcial_de_lotes_tiene_su_propia_situacion():
    assert _sit(MOTIVO_COBERTURA) == COBERTURA_PARCIAL_DE_LOTES


def test_documentos_de_hermanos_tiene_su_propia_situacion():
    assert _sit(MOTIVO_HERMANO) == BAJA_SOLO_EN_DOCUMENTO_DE_HERMANO


def test_la_matriz_gana_al_hermano_porque_su_motivo_lo_contiene():
    """`6.19/28510.0210` real: su motivo trae los tres textos. La causa que de
    verdad lo explica es que su acuerdo marco tampoco publica precios -- si
    ganara la rama del hermano, el pedido se clasificaría por la causa de su
    matriz y el cliente no sabría a qué documento preguntar."""
    assert MOTIVO_HERMANO in MOTIVO_MATRIZ  # la premisa del orden, explícita
    assert _sit(MOTIVO_MATRIZ, "6.19/28510.0179") == MATRIZ_TAMPOCO_PUBLICA


def test_el_motivo_de_la_matriz_nombra_el_acuerdo_marco():
    _, motivo = _situacion(_expediente(MOTIVO_MATRIZ, "6.19/28510.0179"), 0, 5, 0, None)
    assert "6.19/28510.0179" in motivo


def test_un_grupo_de_menos_de_tres_se_queda_en_otro():
    """Los lotes agrupados en un solo anuncio son 2 expedientes
    (`3.20/28510.0071` y `6.15/28510.0080`): no llegan al mínimo de 3 que puso
    el cliente, así que siguen en "Otro" con su motivo a la vista."""
    situacion, motivo = _situacion(_expediente(MOTIVO_LOTES_AGRUPADOS), 0, 7, 0, None)
    assert situacion == OTRO
    assert "Nº Lote: 001/002/003/004" in motivo


def test_las_tres_situaciones_nuevas_estan_en_la_lista_valida():
    for situacion in (MATRIZ_TAMPOCO_PUBLICA, BAJA_SOLO_EN_DOCUMENTO_DE_HERMANO, COBERTURA_PARCIAL_DE_LOTES):
        assert situacion in SITUACIONES


def test_ninguna_situacion_nueva_usa_jerga_interna():
    """Mismo criterio que `app.celdas_vacias`: los textos son para alguien de
    almacenes."""
    prohibidas = ("huérfana", "huerfana", "cascada", "mapeo", "cola", "lote_id", "motivo_revision")
    for motivo_tecnico in (MOTIVO_COBERTURA, MOTIVO_HERMANO, MOTIVO_MATRIZ):
        _, motivo = _situacion(_expediente(motivo_tecnico, "6.19/28510.0179"), 0, 5, 0, None)
        for palabra in prohibidas:
            assert palabra not in motivo.lower()


def test_un_expediente_que_aporta_lineas_no_se_reclasifica():
    """Las ramas nuevas van al final: nada de lo anterior cambia."""
    from app.conciliacion import APORTA_LINEAS

    assert _situacion(_expediente(MOTIVO_COBERTURA), 12, 5, 0, None)[0] == APORTA_LINEAS
