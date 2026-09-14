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
    MOTIVO_TABLA_DEL_CONJUNTO,
    _abre_anejo_del_conjunto,
    _resolver_ambiguedad_urgencia_mutua,
    _ultimo_lote_mencionado,
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


def test_resolver_urgencia_mutua_con_punto_en_vez_de_dos_puntos():
    # Texto real de `6.22/28510.0125`/`0126` (ANEJO_1 p.15 y sus dos
    # Contratos), sesión 2026-09-14, tercera parte.
    texto = (
        "Lote 1. NORTE y, en caso de urgencia que no pueda ser atendida por el\n"
        "adjudicatario del lote 2, SUR."
    )
    assert _resolver_ambiguedad_urgencia_mutua(texto, ["1", "2"]) == "1"
    # Un importe por lote ("Lote 1.- 3.600.000,00 € Lote 2.- ...") son dos
    # cabeceras, no se resuelve.
    assert _resolver_ambiguedad_urgencia_mutua("Lote 1.- 3.600.000,00 € Lote 2.- 3.600.000,00 €", ["1", "2"]) is None


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


# --- Sesión 2026-09-14, tercera parte: el anejo de criterios técnicos del
# conjunto de los lotes, y lo que hay entre una tabla y la anterior. Frases
# reales de los documentos citados.


def test_frase_del_anejo_de_criterios_de_una_licitacion_por_lotes():
    # `6.23/28510.0051_ANEJO_1` p.55.
    assert _abre_anejo_del_conjunto(
        "1 OBJETO\nEl presente documento tiene como objeto detallar los materiales a suministrar en el\n"
        "expediente “SUMINISTRO DE APARATOS ESPECÍFICOS DE VÍA DE ANCHO MIXTO O MÉTRICO PARA LA RED\n"
        "FERROVIARIA DE INTERÉS GENERAL. 2 LOTES”, así como los requisitos técnicos que estos materiales"
    )
    # `6.25/28510.0019` p.35 y `6.25/28510.0214` p.30: lo que se detalla cambia.
    assert _abre_anejo_del_conjunto(
        "tiene como objeto detallar los materiales de la especialidad de instalaciones a suministrar en el "
        "expediente “SUMINISTRO DE INSTALACIONES DE SEGURIDAD MECANICAS EN LA RED FERROVIARIA DE INTERÉS "
        "GENERAL. 9 LOTES”"
    )
    assert _abre_anejo_del_conjunto(
        "detallar los elementos a suministrar en el expediente “SUMINISTRO DE TRAVIESAS MONOBLOQUE DE "
        "HORMIGÓN PARA TRAMOS DE PRUEBAS. 8 LOTES”"
    )
    # `6.22/28510.0126`: la enumeración del propio anejo no es una cabecera.
    assert _abre_anejo_del_conjunto(
        "detallar los materiales a suministrar en el expediente “SUMINISTRO DE APARATOS GENERICOS DE VÍA "
        "PARA LA RED FERROVIARIA DE INTERES GENERAL.2 LOTES”, así como los requisitos técnicos...\n"
        "En la tabla adjunta se concreta el listado inicial de materiales a suministrar en el objeto del "
        "presente expediente, tanto en el lote 1 como en el lote 2, con las características técnicas"
    )


def test_frase_del_anejo_de_criterios_sin_lotes_o_seguida_de_una_cabecera_de_lote():
    # Licitación de un solo lote (`6.21/28510.0025`): la misma frase, sin
    # "N LOTES" -- sus tablas siguen siendo del único lote.
    assert not _abre_anejo_del_conjunto(
        "detallar los materiales a suministrar en el expediente “SUMINISTRO DE CARRIL NUEVO PARA LAS "
        "NECESIDADES DE LA RED FERROVIARIA DE INTERES GENERAL”, así como"
    )
    # Una cabecera de lote después de la frase abre una sección de lote.
    assert not _abre_anejo_del_conjunto(
        "detallar los materiales a suministrar en el expediente “X. 2 LOTES”, así como...\n"
        "Lote 1: ANCHO MIXTO"
    )


def test_cabecera_de_lote_con_ordinal():
    # `4.25/28510.0207`/`0208` (Contratos y ANEJO): "• Lote nº1:
    # Arrendamiento de vagones de bogies." y "• Lote nº 2: Arrendamiento...".
    from app.extraccion.lote_tabla import _asociar_por_texto

    assert _asociar_por_texto("• Lote nº1: Arrendamiento de vagones de bogies.", {"1", "2"}).identificador_lote == "1"
    assert _asociar_por_texto("• Lote nº 2: Arrendamiento de vagones de ejes.", {"1", "2"}).identificador_lote == "2"
    assert _asociar_por_texto("LOTE Nº1: TRAVIESAS DE MADERAS EUROPEA", {"1"}).identificador_lote == "1"
    assert _ultimo_lote_mencionado("- Lote nº1: Arrendamiento de vagones de bogies") == "1"


def test_ultimo_lote_mencionado_antes_de_una_tabla():
    # Contrato del LOTE 1 de `6.22/28510.0122` (p.127): negrita simulada
    # ("LLote") y la referencia de urgencia al otro lote, que no cuenta.
    assert _ultimo_lote_mencionado(
        "LLote 2: CRUZAMIENTOS Y CONTRACARRILES y, en caso de urgencia que no pueda ser\n"
        "atendida por el adjudicatario del lote 1, semicambios, agujas y contraagujas."
    ) == "2"
    # `6.21/28510.0109_ANEJO_1` p.18: "Lote 1." con punto, no con dos puntos.
    assert _ultimo_lote_mencionado(
        "se han conformado a partir de los listados... Lote 1. Semicambios, agujas y contraagujas de gran "
        "longitud y, en casos de urgencia que no puedan ser atendidos por el adjudicatario del lote 2, "
        "Semicambios, agujas"
    ) == "1"
    assert _ultimo_lote_mencionado("CUADRO DE PRECIOS UNITARIOS") is None


def test_asociar_lote_tabla_anejo_de_criterios_real_es_del_conjunto():
    # p.3 del fixture = p.55 real de `6.23/28510.0051_ANEJO_1`.
    with pdfplumber.open(fx.ANEJO_LOTES_Y_CRITERIOS_0051) as pdf:
        pagina = pdf.pages[2]
        tablas = _tablas_ordenadas(pagina)
        resultado = asociar_lote_tabla(pagina, 0.0, tablas[0].bbox, identificadores_validos={"1", "2"})
    assert resultado.del_conjunto_de_lotes is True
    assert resultado.identificador_lote is None
    assert resultado.elegible_para_herencia is False
    assert resultado.motivo_ambiguo == MOTIVO_TABLA_DEL_CONJUNTO
