from app.extraccion.firma_cabecera import calcular_firma_cabecera
from app.extraccion.mapeo_cabecera import (
    heredar_mapeo_de_pagina_anterior,
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


def test_mapeo_determinista_no_reconoce_codificacion_del_precio():
    # Guarda de regresión (sesión de expedientes sin publicar): se probó
    # añadir "codificacion del precio" a los alias de `codigo_precio` para
    # resolver en determinista las 3 firmas reales que hoy caen al modelo
    # (docs/analisis-corpus.md, "Cabeceras de cuadro de precios"). Revertido
    # porque rompía un caso real (`ANEJO_PRECIOS_BALASTO_MULTI_LOTE`, lote 3):
    # en esa tabla el índice de columna de la cabecera y el de la fila de
    # datos no coinciden (una columna fantasma desplazada de forma distinta
    # entre cabecera y filas), y el mapeo determinista -que solo mira
    # posición de cabecera- extraía `precio_unitario=None` en vez del valor
    # real. El modelo sí lo resuelve bien porque ve filas de ejemplo, no solo
    # la cabecera. Esta cabecera debe seguir cayendo al modelo.
    cabecera = ["Codificación del precio", "Descripción", "Precio Unitario de Referencia"]
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


def test_mapear_cabecera_vacia_nunca_se_cachea_ni_se_reutiliza(db_session):
    # Verificación del Excel exportado (2026-09-08): dos tablas reales
    # distintas sin ninguna cabecera detectada (`extraer_tablas_pagina`
    # devuelve `[]`) comparten la misma firma degenerada (hash de la cadena
    # vacía) -- reutilizar el mapeo de la primera para la segunda mezcló sus
    # columnas (matrícula/descripción intercambiadas), produciendo líneas de
    # catálogo sin descripción, sin matrícula y sin código de expediente
    # cruzado (`6.24/28510.0184` y `6.24/28510.0209` reales). Cada tabla sin
    # cabecera debe pedir su propio mapeo, siempre.
    cabecera_vacia = [None, None, None]
    filas_1 = [["664410231", "", "LUNA2 Power Supply Unit", "418,00 €"]]
    filas_2 = [["Fuente de alimentación FA-602", "618050302", "325,50 €"]]

    modelo_1 = ProveedorModeloFalso({
        "codigo_precio": None, "matricula": 0, "descripcion": 2,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 3,
    })
    resultado1 = mapear_cabecera(cabecera_vacia, filas_1, db_session, modelo_1)
    assert resultado1.origen == "modelo"
    assert modelo_1.llamadas == 1

    firma = calcular_firma_cabecera(cabecera_vacia)
    assert obtener_mapeo_cacheado(db_session, firma) is None

    # Segunda tabla, misma firma degenerada, columnas realmente distintas:
    # debe volver a llamar al modelo, nunca reutilizar el mapeo de la primera.
    modelo_2 = ProveedorModeloFalso({
        "codigo_precio": None, "matricula": 1, "descripcion": 0,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 2,
    })
    resultado2 = mapear_cabecera(cabecera_vacia, filas_2, db_session, modelo_2)
    assert resultado2.origen == "modelo"
    assert resultado2.llamada_modelo is True
    assert modelo_2.llamadas == 1
    assert resultado2.mapeo != resultado1.mapeo
    assert obtener_mapeo_cacheado(db_session, firma) is None


# Bloque 5, cambios del cliente tras revisar el catálogo (sesión 2026-09-09):
# `heredar_mapeo_de_pagina_anterior`, verificado en vivo contra
# `6.20/28510.0047_ANEJO_abd69efbdd39b552.pdf` (61 páginas, cabecera solo en
# la primera): sin esto, 37 de 1.302 líneas reales del documento eran las
# únicas que se extraían.
_MAPEO_EJEMPLO = {
    "codigo_precio": None, "matricula": 0, "descripcion": 1,
    "unidad_medida": None, "cantidad": 6, "precio_unitario": 4,
}


def test_hereda_mapeo_cuando_la_cabecera_no_trae_ninguna_senal():
    cabecera_vacia = [None, None, None, None, None, None, None]

    resultado = heredar_mapeo_de_pagina_anterior(cabecera_vacia, _MAPEO_EJEMPLO, 7)

    assert resultado is not None
    assert resultado.mapeo == _MAPEO_EJEMPLO
    assert resultado.origen == "heredado_pagina_anterior"
    assert resultado.llamada_modelo is False


def test_no_hereda_si_no_hay_mapeo_anterior_todavia():
    cabecera_vacia = [None, None, None]
    assert heredar_mapeo_de_pagina_anterior(cabecera_vacia, None, None) is None


def test_no_hereda_si_la_cabecera_si_trae_señal_propia():
    # Una tabla con cabecera propia siempre pide su propio mapeo (cache,
    # determinista o modelo) -- nunca hereda solo porque haya un mapeo
    # anterior disponible.
    cabecera_real = ["Matricula", "Descripción", None, None, "Precio", None, "Cantidad"]
    assert heredar_mapeo_de_pagina_anterior(cabecera_real, _MAPEO_EJEMPLO, 7) is None


def test_no_hereda_si_el_numero_de_columnas_no_coincide():
    # Señal barata de que es una tabla de forma distinta, no la misma
    # continuando -- nunca se hereda a ciegas solo por venir sin cabecera.
    cabecera_vacia_mas_corta = [None, None, None]
    assert heredar_mapeo_de_pagina_anterior(cabecera_vacia_mas_corta, _MAPEO_EJEMPLO, 7) is None


def test_mapeo_heredado_no_se_guarda_en_cache(db_session):
    # El mapeo heredado nunca pasa por `guardar_mapeo_cacheado` -- verificado
    # aparte de la firma degenerada ya cubierta arriba (misma firma para
    # cualquier cabecera vacía, nunca se cachea bajo ella).
    cabecera_vacia = [None, None, None, None, None, None, None]
    resultado = heredar_mapeo_de_pagina_anterior(cabecera_vacia, _MAPEO_EJEMPLO, 7)
    firma = calcular_firma_cabecera(cabecera_vacia)
    assert obtener_mapeo_cacheado(db_session, firma) is None
    assert resultado.firma == firma
