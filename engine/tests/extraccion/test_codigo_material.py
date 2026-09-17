from app.extraccion.codigo_material import (
    derivar_codigo_material,
    derivar_codigo_material_con_modelo,
    obtener_codigo_material_cacheado,
)
from tests.extraccion.dobles import ProveedorModeloFalso


def test_deriva_del_sustantivo_principal():
    assert derivar_codigo_material("BRIDA PARA JUNTA ORDINARIA. 42,5 KG/M") == "BRIDA"
    assert derivar_codigo_material("GUANTE CONTRA RIESGO ELECTRICO.") == "GUANTE"


def test_sin_vocabulario_conocido_no_inventa():
    assert derivar_codigo_material("CONTADOR DE EJES") is None


def test_descripcion_vacia_no_revienta():
    assert derivar_codigo_material("") is None


def test_vocabulario_ampliado_bloque_5():
    # Sustantivos reales del corpus (bloque 5, sesión 2026-09-07), ausentes
    # del vocabulario original de 11 términos.
    assert derivar_codigo_material("CONTRACARRIL DE ACERO PARA...") == "CONTRACARRIL"
    assert derivar_codigo_material("TIRANTE DE UNION PARA...") == "TIRANTE"
    assert derivar_codigo_material("CORAZÓN DE CRUZAMIENTO...") == "CORAZÓN"


def test_partida_alzada_sigue_sin_codigo_material():
    # CONTEXTO.md sección 2: una partida alzada es por definición una línea
    # SIN código de material -- "PARTIDA" nunca debe entrar al vocabulario.
    assert derivar_codigo_material("PARTIDA ALZADA A JUSTIFICAR PARA IMPREVISTOS") is None


def test_salta_unidad_de_medida_suelta_delante_del_material():
    # Corpus real: la unidad de medida a veces encabeza la descripción en
    # vez del material ("T de balasto...", "m de poste...", "ud SEÑAL...").
    assert derivar_codigo_material("T de balasto transportado a la Base de Mantenimiento") == "BALASTO"
    assert derivar_codigo_material("ud SEÑAL DE DOBLE ASPA + GALON P11A") is None  # SEÑAL no está en vocabulario


def test_normaliza_acentos_y_plural_a_forma_canonica():
    # "BULÓN"/"BULON" y singular/plural conviven en el corpus real -- deben
    # compartir el mismo código canónico (con acento, en singular).
    assert derivar_codigo_material("BULON M20 PARA...") == "BULÓN"
    assert derivar_codigo_material("CERROJOS DE SEGURIDAD PARA...") == "CERROJO"
    assert derivar_codigo_material("FUSIBLES DE PROTECCION PARA...") == "FUSIBLE"


def test_sigla_de_aparato_de_via_nombra_la_pieza():
    # Sesión 2026-09-17: la nomenclatura de aparatos de vía de ADIF, verificada
    # contra el propio corpus (la misma pieza con sigla y con palabra en el
    # mismo cuadro, misma serie de matrículas y norma).
    assert derivar_codigo_material("DSF-A-45-112/129- 1:10,5-CR-D") == "DESVÍO"
    assert derivar_codigo_material("AC-16300(+100) / SCI-B1- 54-ID-500") == "AGUJA"
    assert derivar_codigo_material("AR -11250(+100)/ SCI-A- 54-DD- 320") == "AGUJA"
    assert derivar_codigo_material("CAC-12000/ SCI-A-RN45'- 213-3 TER") == "CONTRAAGUJA"
    assert derivar_codigo_material("CAR SCI-B1-54-ID-186 HORMIGÓN") == "CONTRAAGUJA"
    assert derivar_codigo_material("CC Vía Desviada CZI-AG-B1- 54-1:10,5-R") == "CONTRACARRIL"
    assert derivar_codigo_material("CC 33 (L:6000 MM) DCHO para B1-54- 0,09/0'075") == "CONTRACARRIL"
    assert derivar_codigo_material("CZI-AG-P-60-0,11-R (S/PROL)") == "CRUZAMIENTO"
    assert derivar_codigo_material("SCI(DMRD)-B1-54-DD-320") == "SEMICAMBIO"
    assert derivar_codigo_material("SCV-C-60-DD-318 HORM") == "SEMICAMBIO"
    assert derivar_codigo_material("ESH-P1-60-318-0,11-CC- D-TC-3808") == "ESCAPE"
    assert derivar_codigo_material("T.S.U.-B1-54-0'11- 1'435/1'668 M-6A-") == "TRAVESÍA"
    assert derivar_codigo_material("ADH-P(AV4)-60-500 CURVA") == "APARATO"
    assert derivar_codigo_material("J.A.E. EXTER.P/DS-C-54-318-0,09-CR-D") == "JUNTA"
    assert derivar_codigo_material("TRAV.HORM.664054SEH-V- 60-1500-0,042-D-CR") == "TRAVIESA"
    assert derivar_codigo_material("PL.NERV.C/RESBAL.IVAB.PNC5 4-42-B-R.P/1R.D:26") == "PLACA"


def test_desvio_por_geometria_salvo_que_diga_la_pieza():
    # `6.23/28510.0051` p.117: "Semicambio ..." cae detrás del código del
    # desvío; sin esa palabra, la línea es el desvío entero.
    assert derivar_codigo_material("DMRDH-G-60-500-0,071-CR- TC-D") == "DESVÍO"
    assert derivar_codigo_material("DIRD-B1-54-320/194- 0.11-CR-D") == "DESVÍO"
    assert derivar_codigo_material("DMIDH-G-60-500-0,071-CR- I-TC Semicambio dcha (doble) SIN") == "SEMICAMBIO"


def test_sigla_sin_forma_de_codigo_no_casa():
    # Una palabra corta en mayúsculas seguida de texto corriente no es una
    # sigla de aparato de vía.
    assert derivar_codigo_material("ES DE APLICACION LA NORMA") is None
    assert derivar_codigo_material("Es-ta descripcion") is None
    assert derivar_codigo_material("SCHNEIDER Modicon X80 BMXRMS004GPF") is None
    assert derivar_codigo_material("CI-A-54-D-190") is None


def test_ordinal_delante_de_la_pieza():
    assert derivar_codigo_material("SEGUNDA PLACA DE TALON, DCHA. MOD.45.17-D.D") == "PLACA"
    assert derivar_codigo_material("TERCERA PLACA DETALON, IZQDA. MOD.45.18-D.G") == "PLACA"


def test_con_modelo_usa_vocabulario_primero_sin_tocar_bd(db_session):
    modelo = ProveedorModeloFalso({"codigo_material": "NO_DEBERIA_LLAMARSE"})
    assert derivar_codigo_material_con_modelo("BRIDA PARA JUNTA...", db_session, modelo) == "BRIDA"
    assert modelo.llamadas == 0


def test_con_modelo_llama_una_vez_por_termino_nuevo_y_cachea(db_session):
    modelo = ProveedorModeloFalso({"codigo_material": "CONTADOR"})

    resultado1 = derivar_codigo_material_con_modelo("CONTADOR DE EJES MODELO X", db_session, modelo)
    assert resultado1 == "CONTADOR"
    assert modelo.llamadas == 1

    cacheado = obtener_codigo_material_cacheado(db_session, "CONTADOR")
    assert cacheado is not None
    assert cacheado.codigo_material == "CONTADOR"
    assert cacheado.origen == "modelo"

    # Segunda línea con el mismo término candidato: no se vuelve a llamar.
    resultado2 = derivar_codigo_material_con_modelo("CONTADOR DE EJES MODELO Y", db_session, modelo)
    assert resultado2 == "CONTADOR"
    assert modelo.llamadas == 1


def test_con_modelo_confirma_ausencia_de_material_y_lo_cachea(db_session):
    # El modelo puede confirmar "esto no es un sustantivo de material"
    # (una marca comercial) -- también se cachea como null,
    # para no volver a preguntarlo.
    modelo = ProveedorModeloFalso({"codigo_material": None})

    resultado1 = derivar_codigo_material_con_modelo("SCHNEIDER Modicon X80 BMXRMS004GPF", db_session, modelo)
    assert resultado1 is None
    assert modelo.llamadas == 1

    cacheado = obtener_codigo_material_cacheado(db_session, "SCHNEIDER")
    assert cacheado is not None
    assert cacheado.codigo_material is None

    resultado2 = derivar_codigo_material_con_modelo("SCHNEIDER Premium TSXDEY16FK", db_session, modelo)
    assert resultado2 is None
    assert modelo.llamadas == 1


def test_con_modelo_sin_model_provider_no_llama_ni_cachea(db_session):
    resultado = derivar_codigo_material_con_modelo("CONTADOR DE EJES", db_session, None)
    assert resultado is None
    assert obtener_codigo_material_cacheado(db_session, "CONTADOR") is None


def test_respuesta_cacheada_solo_vale_si_la_descripcion_nombra_la_pieza(db_session):
    # Sesión 2026-09-17: "X" -> BALASTO (cacheado para una línea de balasto)
    # acababa en equipos Ethernet y postes con la misma primera palabra.
    modelo = ProveedorModeloFalso({"codigo_material": "RODILLO"})
    assert derivar_codigo_material_con_modelo("Paquete de 1 Rodillo sobre resbaladera", db_session, modelo) == "RODILLO"
    assert derivar_codigo_material_con_modelo("PAQUETE DE CABLES VARIOS", db_session, modelo) is None
    assert modelo.llamadas == 1


def test_respuesta_cacheada_que_es_la_propia_palabra_abreviada(db_session):
    modelo = ProveedorModeloFalso({"codigo_material": "CONJUNTO"})
    assert derivar_codigo_material_con_modelo("CONJ. FIJAC. SKL-12 C/PLACA NERV", db_session, modelo) == "CONJUNTO"
