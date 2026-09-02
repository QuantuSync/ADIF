from app.extraccion.firma_cabecera import calcular_firma_cabecera
from app.extraccion.mapeo_cabecera import (
    intentar_mapeo_determinista,
    mapear_cabecera,
    obtener_mapeo_cacheado,
)
from tests.extraccion.dobles import ProveedorModeloFalso


def test_mapeo_determinista_cabecera_completa():
    cabecera = [
        "Código de Precio",
        "Nº Matrícula",
        "Descripción",
        "Unidad de Medida",
        "Cantidades Estimadas de Referencia",
        "Precio Unitario de Referencia",
    ]
    mapeo = intentar_mapeo_determinista(cabecera)
    assert mapeo == {
        "codigo_precio": 0,
        "matricula": 1,
        "descripcion": 2,
        "unidad_medida": 3,
        "cantidad": 4,
        "precio_unitario": 5,
    }


def test_mapeo_determinista_columna_codigo_precio_no_se_confunde_con_precio():
    # "CÓDIGO DE PRECIO" contiene tanto el alias de codigo_precio ("codigo")
    # como el de precio_unitario ("precio"); precio_unitario debe resolverse
    # por su propia columna, no reclamar esta.
    cabecera = ["Código de Precio", "Descripción", "Precio Unitario de Referencia"]
    mapeo = intentar_mapeo_determinista(cabecera)
    assert mapeo["codigo_precio"] == 0
    assert mapeo["precio_unitario"] == 2


def test_mapeo_determinista_columna_fantasma_no_se_mapea():
    cabecera = ["Código de Precio", None, "Descripción", "", "Precio Unitario"]
    mapeo = intentar_mapeo_determinista(cabecera)
    assert mapeo["codigo_precio"] == 0
    assert mapeo["descripcion"] == 2
    assert mapeo["precio_unitario"] == 4
    assert 1 not in mapeo.values()
    assert 3 not in mapeo.values()


def test_mapeo_determinista_sin_descripcion_falla():
    cabecera = ["Código de Precio", "Precio Unitario"]
    assert intentar_mapeo_determinista(cabecera) is None


def test_mapeo_determinista_sin_identificador_falla():
    cabecera = ["Descripción", "Precio Unitario"]
    assert intentar_mapeo_determinista(cabecera) is None


def test_mapear_cabecera_desconocida_llama_al_modelo_una_vez_y_cachea(db_session):
    # Cabecera sintética que el mapeo determinista no puede resolver
    # (nombres de columna que no están en ningún alias conocido).
    cabecera = ["Ref.", "Detalle del artículo", "Coste unitario"]
    filas_ejemplo = [["P-001", "Artículo de prueba", "12,50"]]
    respuesta_modelo = {
        "codigo_precio": 0,
        "matricula": None,
        "descripcion": 1,
        "unidad_medida": None,
        "cantidad": None,
        "precio_unitario": 2,
    }
    modelo = ProveedorModeloFalso(respuesta_modelo)

    resultado1 = mapear_cabecera(cabecera, filas_ejemplo, db_session, modelo)
    assert resultado1.origen == "modelo"
    assert resultado1.llamada_modelo is True
    assert resultado1.mapeo == respuesta_modelo
    assert modelo.llamadas == 1

    # Nunca se le pasan las filas de datos completas, solo 2-3 de ejemplo.
    assert str(filas_ejemplo[0]) in modelo.prompts[0]

    firma = calcular_firma_cabecera(cabecera)
    assert obtener_mapeo_cacheado(db_session, firma) is not None

    # Segunda vez, misma firma: no se vuelve a llamar al modelo.
    resultado2 = mapear_cabecera(cabecera, filas_ejemplo, db_session, modelo)
    assert resultado2.origen == "cache"
    assert resultado2.llamada_modelo is False
    assert resultado2.mapeo == respuesta_modelo
    assert modelo.llamadas == 1  # sigue en 1, no ha subido


def test_mapear_cabecera_dos_firmas_distintas_dos_llamadas(db_session):
    modelo = ProveedorModeloFalso({
        "codigo_precio": 0, "matricula": None, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 2,
    })
    mapear_cabecera(["Ref.", "Detalle", "Coste"], [["P-1", "x", "1,00"]], db_session, modelo)
    mapear_cabecera(["Cod.", "Concepto", "Importe"], [["P-2", "y", "2,00"]], db_session, modelo)
    assert modelo.llamadas == 2


def test_mapear_cabecera_sin_model_provider_y_sin_determinismo_falla(db_session):
    import pytest

    with pytest.raises(RuntimeError):
        mapear_cabecera(["Ref.", "Detalle", "Coste"], [], db_session, None)
