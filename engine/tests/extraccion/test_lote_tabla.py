"""Sesión de verificación del Excel de 6.599 líneas (2026-09-08): Parte A
(desambiguar la cláusula de "urgencia mutua entre lotes") y la señal
`elegible_para_herencia` que usa la Parte B (`app.extraccion.pipeline_anejo`).
Verificado, antes de escribir ningún test, contra el documento real completo
de `6.22/28510.0156` (repuestos de vía, 2 lotes) -- el fixture de este
módulo son 5 páginas reales de ese documento, no texto inventado a mano:
página 15 (cabecera ambigua de "Lote 1"), 16 y 25 (continuación, sin ningún
rastro de "LOTE"), 26 (cabecera ambigua de "Lote 2", el cuadro de precios se
repite íntegro desde P-001), 27 (continuación de Lote 2)."""
import pdfplumber

from app.extraccion.lote_tabla import (
    _resolver_ambiguedad_urgencia_mutua,
    asociar_lote_tabla,
)
from app.extraccion.tabla import extraer_tablas_pagina
from tests import fixtures as fx


def _tablas_ordenadas(pagina):
    return sorted(extraer_tablas_pagina(pagina), key=lambda t: t.bbox[1])


def test_resolver_urgencia_mutua_lote_1():
    # Texto real de la p.15: el propio lote 1 cita al 2 como repuesto de
    # urgencia -- nunca al revés en esta frase.
    texto = (
        "Lote 1: SEMICAMBIOS, AGUJAS Y CONTRAAGUJAS y, en caso de urgencia que no pueda ser\n"
        "atendida por el adjudicatario del lote 2, cruzamientos y contracarriles."
    )
    assert _resolver_ambiguedad_urgencia_mutua(texto, ["1", "2"]) == "1"


def test_resolver_urgencia_mutua_lote_2():
    # Texto real de la p.26 (espejo de la anterior).
    texto = (
        "Lote 2: CRUZAMIENTOS Y CONTRACARRILES y, en caso de urgencia que no pueda ser\n"
        "atendida por el adjudicatario del lote 1, semicambios, agujas y contraagujas."
    )
    assert _resolver_ambiguedad_urgencia_mutua(texto, ["1", "2"]) == "2"


def test_resolver_urgencia_mutua_no_adivina_con_dos_cabeceras_fuertes():
    # Guard de seguridad (caso real 6.25/28510.0027, balasto): si las DOS
    # menciones son cabeceras fuertes de verdad (dos tablas reales
    # comparten página), no se elige ninguna -- sigue ambiguo.
    texto = "LOTE 1: PRIMERA TABLA\nLOTE 2: SEGUNDA TABLA"
    assert _resolver_ambiguedad_urgencia_mutua(texto, ["1", "2"]) is None


def test_resolver_urgencia_mutua_no_adivina_sin_cabecera_fuerte():
    # Las dos menciones son referencias débiles ("del lote"), ninguna abre
    # una sección de verdad -- no hay nada de lo que fiarse, sigue ambiguo.
    texto = "Ver las condiciones del lote 1 y del lote 2 en el pliego general."
    assert _resolver_ambiguedad_urgencia_mutua(texto, ["1", "2"]) is None


def test_resolver_urgencia_mutua_no_aplica_con_mas_de_dos_identificadores():
    assert _resolver_ambiguedad_urgencia_mutua("LOTE 1: x del lote 2 y del lote 3", ["1", "2", "3"]) is None


def test_asociar_lote_tabla_documento_real_resuelve_las_dos_cabeceras_ambiguas():
    with pdfplumber.open(fx.ANEJO_HERENCIA_LOTE_0156) as pdf:
        # Página 1 del fixture = p.15 real: "Lote 1: ... del lote 2 ...".
        tablas_p1 = _tablas_ordenadas(pdf.pages[0])
        r1 = asociar_lote_tabla(pdf.pages[0], 0.0, tablas_p1[0].bbox, identificadores_validos={"1", "2"})
        assert r1.identificador_lote == "1"
        assert r1.motivo_ambiguo is None
        assert r1.elegible_para_herencia is False

        # Página 4 del fixture = p.26 real: "Lote 2: ... del lote 1 ...".
        tablas_p4 = _tablas_ordenadas(pdf.pages[3])
        r4 = asociar_lote_tabla(pdf.pages[3], 0.0, tablas_p4[0].bbox, identificadores_validos={"1", "2"})
        assert r4.identificador_lote == "2"
        assert r4.motivo_ambiguo is None
        assert r4.elegible_para_herencia is False


def test_asociar_lote_tabla_documento_real_paginas_de_continuacion_son_elegibles():
    with pdfplumber.open(fx.ANEJO_HERENCIA_LOTE_0156) as pdf:
        # Páginas 2, 3 y 5 del fixture = p.16, p.25 y p.27 reales: ninguna
        # trae ni rastro de la palabra "LOTE".
        for indice_pagina in (1, 2, 4):
            pagina = pdf.pages[indice_pagina]
            tablas = _tablas_ordenadas(pagina)
            resultado = asociar_lote_tabla(pagina, 0.0, tablas[0].bbox, identificadores_validos={"1", "2"})
            assert resultado.identificador_lote is None
            assert resultado.elegible_para_herencia is True
