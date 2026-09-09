from app.extraccion.firma_cabecera import calcular_firma_cabecera
from app.extraccion.mapeo_cabecera import (
    evaluar_coherencia_mapeo,
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


def test_evaluar_coherencia_mapeo_detecta_mapeo_incoherente_sobre_cabecera_sin_senal():
    # Caso real, Bloque 2 (auditoría 6.20/28510.0042/0046/0047, 51 grupos
    # duplicados y 207 líneas sin descripción): tabla sin cabecera propia de
    # `ANEJO_abd69efbdd39b552.pdf` p.27 -- 5 columnas reales (matrícula,
    # designación, plano, norma técnica, precio). El modelo, guiado solo por
    # unas pocas filas de ejemplo, mapeó descripcion a una columna vacía en
    # todas las filas reales de la tabla.
    filas = [
        ["610850108", "AC-9000 / SCI-A-54-DI-190", "311-31", "03.360.101.4", "1.620,46 €"],
        ["601080026", "CUPON MIXTO 54/42'5 KGS.L:8 M. HILO IZQUIERDO", "", "", "1.665,72 €"],
        ["601080025", "CUPON MIXTO 54/42'5 KGS. L:8 M.HILO DERECHO", "", "", "1.676,15 €"],
        ["612860600", "JUEGO DE PLACAS PARA SUJECION BLOQUE CENTRAL", "", "", "1.692,08 €"],
        ["601080022", "CUPON MIXTO 54/45 12 M.(6+ 6) lADO DERECHO", "", "03.360.101.4", "1.697,76 €"],
    ]
    mapeo_incoherente = {
        "codigo_precio": None, "matricula": 0, "descripcion": None,
        "unidad_medida": None, "cantidad": 3, "precio_unitario": 4,
    }
    motivo = evaluar_coherencia_mapeo(mapeo_incoherente, filas)
    assert motivo is not None
    assert "descripcion" in motivo

    # El mapeo correcto (descripcion=1) sobre las mismas filas pasa la
    # comprobación.
    mapeo_correcto = {
        "codigo_precio": None, "matricula": 0, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 4,
    }
    assert evaluar_coherencia_mapeo(mapeo_correcto, filas) is None


def test_evaluar_coherencia_mapeo_sin_filas_no_opina():
    assert evaluar_coherencia_mapeo({"descripcion": 1, "precio_unitario": 2}, []) is None


def test_evaluar_coherencia_mapeo_detecta_desplazamiento_aunque_descripcion_pase_el_umbral_de_vacio():
    # Caso real, misma tabla (`ANEJO_abd69efbdd39b552.pdf` p.27): el mismo
    # desplazamiento de una columna que el test de arriba (matrícula->
    # codigo_precio, designación->matrícula, PLANO->descripcion) esta vez con
    # más filas de la tabla real -- la columna "Plano" está rellena en más de
    # la mitad de ellas (referencias de plano tipo "P16.0739.04"), así que
    # `descripcion` SÍ pasa la comprobación de vacío. Solo la segunda
    # comprobación (forma de `matricula`) detecta que el mapeo sigue mal:
    # la columna que el mapeo cree que es `matricula` trae designaciones de
    # texto libre, nunca 9 dígitos.
    filas = [
        ["610850108", "AC-9000 / SCI-A-54-DI-190", "311-31", "03.360.101.4", "1.620,46 €"],
        ["601080026", "CUPON MIXTO 54/42'5 KGS.L:8 M. HILO IZQUIERDO", "", "", "1.665,72 €"],
        ["612860604", "JUEGO PLACAS NERVADAS PN-60 SUJ. BLOQUE C 042", "Pl6, 2244.00", "", "1.717,34 €"],
        ["601080620", "CUPON MIXTO 45/60, 10407, 3'20+7'207, HILO D", "ESQUEMAS DE VIA, 2.2.1", "", "1.741,24 €"],
        ["617560810", "J.A.E. IVG 30(REFORZADA) L= 10,80 CARRIL 60", "P16.4039.00", "", "1.761,45 €"],
        ["617060451", "CONTRAAGUJA DCH.-14037(+100) ADH-F-60-500", "P16.1702.00 SIMETRICO", "", "1.822,49 €"],
        ["612250182", "CAC-15465(+200)/ SCI-C-54-II-250", "P16.0739.04", "03.360.101.4", "1.854,06 €"],
    ]
    mapeo_desplazado = {
        "codigo_precio": 0, "matricula": 1, "descripcion": 2,
        "unidad_medida": None, "cantidad": 3, "precio_unitario": 4,
    }
    # La comprobación de vacío por sí sola no bastaría: 5/7 filas traen algo
    # en la columna "Plano" que el mapeo cree que es descripcion.
    con_valor_col2 = sum(1 for f in filas if f[2].strip())
    assert con_valor_col2 / len(filas) >= 0.5

    motivo = evaluar_coherencia_mapeo(mapeo_desplazado, filas)
    assert motivo is not None
    assert "matricula" in motivo
