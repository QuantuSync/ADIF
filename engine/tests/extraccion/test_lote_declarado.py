"""Bloque 6, sesión 2026-09-18 (continuación): el lote que un pedido derivado
declara en su propio "Objeto del Contrato" publicado. Los títulos de estos
tests son reales, copiados de la Plataforma."""
import pytest

from app.extraccion.lote_declarado import (
    extraer_expediente_principal_declarado,
    extraer_lote_declarado,
)


@pytest.mark.parametrize(
    "titulo, esperado",
    [
        # Los cinco pedidos de equipos de protección individual del encargo.
        (
            "Pedido nº 1 acuerdo marco 4.24/04110.0187 para el suministro de equipos de protección "
            "individual 2024-2025 (8 lotes). expediente principal 4.23/04110.0256 lote 4: guantes de "
            "protección contra riesgos mecánicos",
            "4",
        ),
        (
            "Pedido nº 1 acuerdo marco 4.24/04110.0189 para el suministro de equipos de protección "
            "individual 2024-2025 (8 lotes). exp.4.23/04110.0256. lote 6: crema o leche de protección "
            "solar (dosificadores, recargas y botes).",
            "6",
        ),
        (
            "Pedido nº 2 acuerdo marco 2.24/04110.0036 para el suministro de equipos de protección "
            "individual: Lote 2. Chaqueta impermeable y chaqueta softshell de alta visibilidad contra "
            "el frío extremo (hasta -50°c)",
            "2",
        ),
        (
            "Pedido nº 2 acuerdo marco para el suministro de equipos de protección individual. Lote 1 "
            "chaqueta impermeable y chaqueta softshell de alta visibilidad contra el frío (hasta -5°c)",
            "1",
        ),
        (
            "Pedido nº 2 acuerdo marco para el suministro de equipos de protección individual. Lote 3: "
            "Chalecos de alta visibilidad",
            "3",
        ),
        # El caso que el arreglo desbloquea de verdad: su matriz sí publica el
        # cuadro de precios de cada lote.
        (
            "Suministro de balasto para las necesidades de obras y mantenimiento en la red ferroviaria "
            "de interés general (zona norte). Lote 2: Base en Sanchidrián.",
            "2",
        ),
        ("LOTE Nº 7 - Traviesas de hormigón", "7"),
        ("Suministro de carril, lote 04", "4"),
    ],
)
def test_lote_declarado_en_titulos_reales(titulo, esperado):
    assert extraer_lote_declarado(titulo) == esperado


def test_el_numero_de_lotes_de_la_licitacion_no_es_un_lote():
    """"(8 LOTES)" dice cuántos lotes tiene la licitación, no cuál es el suyo:
    el número va delante de la palabra, no detrás."""
    titulo = "Acuerdo Marco para el suministro de equipos de protección individual 2024-2025 (8 lotes)."
    assert extraer_lote_declarado(titulo) is None


def test_dos_lotes_distintos_no_declaran_ninguno():
    """Un pedido que cita dos lotes los menciona, no declara el suyo. Antes de
    adivinar, a revisión."""
    assert extraer_lote_declarado("Suministro conjunto del lote 2 y del lote 3") is None


def test_el_mismo_lote_repetido_sigue_siendo_una_declaracion():
    assert extraer_lote_declarado("Lote 2: balasto. Ver condiciones del lote 2 en el pliego.") == "2"


def test_sin_lote_ni_titulo():
    assert extraer_lote_declarado("Suministro de balasto, base en Sanchidrián") is None
    assert extraer_lote_declarado(None) is None
    assert extraer_lote_declarado("") is None


def test_no_confunde_un_codigo_de_expediente_pegado_con_un_lote():
    assert extraer_lote_declarado("acuerdo marco 4.24/04110.0187 lote 4") == "4"


def test_expediente_principal_declarado():
    assert extraer_expediente_principal_declarado(
        "Pedido nº 1 ... expediente principal 4.23/04110.0256 lote 4: guantes"
    ) == "4.23/04110.0256"
    assert extraer_expediente_principal_declarado(
        "Pedido nº 1 ... (8 lotes). exp.4.23/04110.0256. lote 6: crema solar"
    ) == "4.23/04110.0256"
    assert extraer_expediente_principal_declarado(
        "Pedido nº 2 acuerdo marco para el suministro de equipos. Lote 1 chaqueta"
    ) is None
