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


def test_codigo_de_aparato_de_via_sin_sustantivo_no_casa_por_reglas():
    # "DSF-A-45-112/129-1:10,5-CR-D" es un código de tipo de desvío, no trae
    # ningún sustantivo -- no debe colarse en el vocabulario determinista.
    assert derivar_codigo_material("DSF-A-45-112/129- 1:10,5-CR-D") is None


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
    # (código de tipo de aparato de vía) -- también se cachea como null,
    # para no volver a preguntarlo.
    modelo = ProveedorModeloFalso({"codigo_material": None})

    resultado1 = derivar_codigo_material_con_modelo("DSF-A-45-112/129- 1:10,5-CR-D", db_session, modelo)
    assert resultado1 is None
    assert modelo.llamadas == 1

    cacheado = obtener_codigo_material_cacheado(db_session, "DSF")
    assert cacheado is not None
    assert cacheado.codigo_material is None

    resultado2 = derivar_codigo_material_con_modelo("DSF-B1-54-100- 1:6-CC-D", db_session, modelo)
    assert resultado2 is None
    assert modelo.llamadas == 1


def test_con_modelo_sin_model_provider_no_llama_ni_cachea(db_session):
    resultado = derivar_codigo_material_con_modelo("CONTADOR DE EJES", db_session, None)
    assert resultado is None
    assert obtener_codigo_material_cacheado(db_session, "CONTADOR") is None
