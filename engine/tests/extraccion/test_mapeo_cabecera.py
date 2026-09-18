from app.extraccion.firma_cabecera import calcular_firma_cabecera
from app.extraccion.mapeo_cabecera import (
    completar_codigo_precio_por_contenido,
    corregir_confusion_matricula_codigo_precio,
    corregir_confusion_precio_cantidad,
    derivar_mapeo_por_contenido,
    evaluar_coherencia_mapeo,
    completar_columna_codigo_material,
    heredar_mapeo_por_geometria,
    intentar_mapeo_determinista,
    mapear_cabecera,
    obtener_mapeo_cacheado,
)
from tests.extraccion.dobles import ProveedorModeloFalso


# --- derivar_mapeo_por_contenido (Bloque 3, sesión 2026-09-11) ---
# Filas reales completas de `ANEJO_abd69efbdd39b552.pdf` p.35 (trío
# 0042/0046/0047, 33 líneas): matrícula, descripción, plano, norma técnica,
# precio -- sin ninguna columna de código de precio. Verificado en vivo que
# el modelo devuelve una permutación de columnas distinta en cada llamada
# sobre esta tabla exacta; estas son las filas reales que lo motivaron.
_FILAS_TRIO_P35 = [
    ["612260110", "SCV-C-60-ID-318", "P16.0785.02", "03.361.130.2", "15.377,63 €"],
    ["612260115", "SCV-C-60-II-318", "P16.0785.24", "03.361.130.2", "15.468,40 €"],
    ["615260093", "SCI-P-60-II-318", "P16.3589.05 SIMETRICO", "03.361.130.2", "15.561,96 €"],
    ["619350615", "CZI-AG-3HD-B1-54-0,11-R", "P16.2316.00 (S)", "03.361.140.1", "15.571,69 €"],
    ["612260101", "SCV-C-6O-DD-318", "P16.0784.24", "03.361.130.2", "15.584,23 €"],
    ["612260105", "SCV-C-60-DI -318", "P16.0784.02", "03.361.130.2", "15.622,21 €"],
    ["615260091", "SCI -P-60-ID-318", "P16.3589.02 SIMETRICO", "03.361.130.2", "15.741,46 €"],
    ["619350645", "CZI-AG-3HI-B1-54-0,11-R", "P16.2316.00", "03.361.140.1", "16.060,87 €"],
    ["612250101", "SCI-C-54-DD-318", "P16.0733.24", "03.361.130.2", "16.310,47 €"],
    ["612250110", "SCI-C-54-ID-318", "P16.0734.02", "03.361.130.2", "16.310,47 €"],
    ["612250115", "SCI-C-54-II-318", "P16.0734.24", "03.361.130.2", "16.310,47 €"],
    ["612250105", "SCI-C-54-DI-318", "P16.0733.02", "03.361.130.2", "16.360,33 €"],
    ["619350812", "SCI(DRMI)-B1-54-DD-320", "P16.4315.00", "03.361.130.2", "16.478,17 €"],
    ["619350814", "SCI(DRMI)-B1-54-DI-320", "P16.4314.00", "03.361.130.2", "16.478,17 €"],
    ["619350642", "SCI(DMRI)-B1-54-II-320", "P16.4312.00", "03.361.130.2", "16.567,94 €"],
    ["619350644", "SCI(DMRI)-B1-54-ID-320", "P16.4311.00", "03.361.130.2", "16.567,94 €"],
    ["612250102", "SCI-C(+10)-54-DD-318", "P16.5144.22", "03.361.130.2", "16.627,80 €"],
    ["612250116", "SCI-C(+10)-54-II-318", "P16.5165.22", "03.361.130.2", "17.272,37 €"],
    ["615260111", "SCI-P-60-AC-CAR-I.D.\nP/DSH-P-60-318-0,11", "", "", "17.315,61 €"],
    ["612260145", "SCVH-C-60-DD-500", "P16.2913.22", "03.361.130.2", "17.674,63 €"],
    ["612260155", "SCVH-C-60-ID-500", "P16.2913.02 SIMETRICO", "03.361.130.2", "17.674,63 €"],
    ["612260150", "SCVH-C-60-II-500", "P16.2913.22 SIMETRICO", "03.361.130.2", "17.847,17 €"],
    ["612260140", "SCVH-C-60-0I-500", "P16.2913.02", "03.361.130.2", "18.038,99 €"],
    ["615250090", "SCI-P-54-DD-318 P/DS-P-\n54-318-0'09-CR-D", "", "", "18.268,00 €"],
    ["615250091", "SCI-P-54-DI 318 P/DS-P-\n54-318-0'09-CR-D", "", "", "18.268,00 €"],
    ["615260094", "SCI-P-60-AR-CAC-D.D.\nP/DSH-P-60-318-0,09", "", "", "18.268,00 €"],
    ["614860200", "CONJ.100 TRAV.M/DCHA. DE\nE640156D A E640255D", "", "", "18.565,57 €"],
    ["612250161", "SCI-C(+10)-54-II-500", "P16.5160.24", "03.360.130.2", "18.733,39 €"],
    ["612260125", "SCV-C-60-DD-500", "P16.0862.24", "03.361.130.2", "18.759,77 €"],
    ["612260130", "SCV-C-60-ID-500", "P16.0863.02", "03.361.130.2", "18.759,77 €"],
    ["612260135", "SCV-C-60-II -500", "P16.0863.24", "03.361.130.2", "18.759,77 €"],
    ["612850231", "PLACA NERVADA PN54-540I\nCON SOPORTE DE AGUJA", "P16.0764.09", "", "19.176,00 €"],
    ["612250160", "SCI-C-54-II-500", "P16.0913.024", "03.361.130.2", "19.227,46 €"],
]


def test_derivar_mapeo_por_contenido_caso_real_trio_0042_0046_0047():
    mapeo = derivar_mapeo_por_contenido(_FILAS_TRIO_P35)
    assert mapeo == {
        "codigo_precio": None, "matricula": 0, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 4,
    }
    # Y el mapeo derivado pasa la validación de coherencia sin ningún aviso.
    assert evaluar_coherencia_mapeo(mapeo, _FILAS_TRIO_P35) is None


def test_derivar_mapeo_por_contenido_caso_real_p27_mismo_documento():
    # Misma tabla sin cabecera, otra página del mismo documento (p.27):
    # también resuelta hoy vía `evaluar_coherencia_mapeo` rechazando al
    # modelo -- con la derivación por contenido, se resuelve sin llamarlo.
    filas = [
        ["610850108", "AC-9000 / SCI-A-54-DI-190", "311-31", "03.360.101.4", "1.620,46 €"],
        ["601080026", "CUPON MIXTO 54/42'5 KGS.L:8 M. HILO IZQUIERDO", "", "", "1.665,72 €"],
        ["601080025", "CUPON MIXTO 54/42'5 KGS. L:8 M.HILO DERECHO", "", "", "1.676,15 €"],
        ["612860600", "JUEGO DE PLACAS PARA SUJECION BLOQUE CENTRAL", "", "", "1.692,08 €"],
        ["601080022", "CUPON MIXTO 54/45 12 M.(6+ 6) lADO DERECHO", "", "03.360.101.4", "1.697,76 €"],
    ]
    mapeo = derivar_mapeo_por_contenido(filas)
    assert mapeo == {
        "codigo_precio": None, "matricula": 0, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 4,
    }


# --- Bloque 7, sesión 2026-09-13: 771 líneas reales en 8 expedientes con
# `codigo_precio` igual a la matrícula, en tablas cuyo precio no lleva `€`
# (`docs/sesion-2026-09-12-defecto-mapeo-calidad-interfaz-rendimiento.md`
# bloque 2). Filas reales completas de `6.22_28510.0058/ANEJO_
# a9e7c95651661aad.pdf` p.15 (tornillería, sin cabecera, sin código de
# precio -- solo matrícula, precio con coma decimal sin símbolo de moneda).
_FILAS_TORNILLERIA_P15 = [
    ["603250020", "TIRAFONDO ESPECIAL E3, 22X235 MM. P/ENCARRIL", "ud", "1.200", "7,40"],
    ["603250025", "TIRAFONDO ESPECIAL E4, 22X170 MM. P/ENCARRIL", "ud", "1.200", "5,03"],
    ["603250027", "TIRAFONDO ESPECIAL, 22X290 MM.UIC-54, BICROMAT", "ud", "1.200", "6,20"],
    ["605300020", "TORNILLO PARA TRAVIESA HORMIGON TIPO RS", "ud", "70.000", "4,22"],
    ["605300021", "TUERCA P/TORNILLO TRAVIESA HORMIGON TIPO RS", "ud", "1.200", "1,37"],
    ["605300030", "TORNILLO PARA TOPE, SUJECION STEDEF, VSB", "ud", "1.200", "2,34"],
    ["605300200", "TORNILLO TIPO 5, DE PLASTIRAIL, 22-115", "ud", "1.200", "2,31"],
    ["605300210", "TIRAFONDO GS PARA BLOQUE POLIVALENTE EXTRAIBL", "ud", "1.200", "2,26"],
    ["605300270", "ARANDELA PLANA 50X24X4, STEDEF, A.V. -60, 1'435", "ud", "1.200", "0,36"],
    ["607300000", "TIRAFONDO DE VIA, TIPO NUMERO 6, GALV. /CROMAT", "ud", "7.000", "1,72"],
    ["607300010", "TORNILLO T-2 PARA SUJECION VM", "ud", "12.000", "2,89"],
]


def test_derivar_mapeo_por_contenido_caso_real_tornilleria_sin_simbolo_euro():
    # Antes del bloque 7, `_clasificar_columna` no reconocía esta columna de
    # precio (sin `€`) y `derivar_mapeo_por_contenido` se rendía sin más
    # (`indices_precio == []`) -- la tabla caía al modelo, que en la
    # sesión anterior devolvió `codigo_precio` apuntando a la propia
    # columna de matrícula en al menos una llamada real.
    mapeo = derivar_mapeo_por_contenido(_FILAS_TORNILLERIA_P15)
    assert mapeo == {
        "codigo_precio": None, "matricula": 0, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 4,
    }
    assert evaluar_coherencia_mapeo(mapeo, _FILAS_TORNILLERIA_P15) is None


def test_derivar_mapeo_por_contenido_detecta_codigo_precio_real():
    filas = [
        ["P-001", "BRIDA DE SUJECION TIPO A", "10", "3,50 €"],
        ["P-002", "PLACA DE ASIENTO TIPO B", "5", "7,20 €"],
        ["P-003", "TORNILLO M22X325 DE ALTA RESISTENCIA", "20", "1,10 €"],
    ]
    mapeo = derivar_mapeo_por_contenido(filas)
    assert mapeo == {
        "codigo_precio": 0, "matricula": None, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 3,
    }


def test_derivar_mapeo_por_contenido_dos_columnas_de_texto_no_se_adivina():
    # Dos columnas con el mismo perfil (texto libre, alta cardinalidad) sin
    # ningún patrón que las distinga -- condición 1 del encargo: no se
    # adivina cuál es la descripción, se devuelve None (la línea sigue el
    # camino de siempre, que puede acabar en revisión).
    filas = [
        ["611150110", "Observación variable uno de la fila", "Designación libre variable uno", "3,50 €"],
        ["611150111", "Observación variable dos de la fila", "Designación libre variable dos", "7,20 €"],
        ["611150098", "Observación variable tres de la fila", "Designación libre variable tres", "1,10 €"],
    ]
    assert derivar_mapeo_por_contenido(filas) is None


def test_derivar_mapeo_por_contenido_sin_identificador_no_se_adivina():
    # Ni matrícula ni código de precio en ninguna columna: no hay nada que
    # ancle la fila, mejor no derivar nada.
    filas = [
        ["Balasto sobre camión en cantera", "1", "0,142 €"],
        ["Transporte de traviesas a obra", "2", "0,255 €"],
    ]
    assert derivar_mapeo_por_contenido(filas) is None


def test_derivar_mapeo_por_contenido_sin_filas_no_opina():
    assert derivar_mapeo_por_contenido([]) is None


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


def test_corregir_confusion_matricula_codigo_precio_caso_real_0042_0046_0047():
    # Caso real, Bloque 3, sesión 2026-09-11: `ANEJO_abd69efbdd39b552.pdf`
    # p.35 (trío 0042/0046/0047), tabla sin cabecera propia y SIN ninguna
    # columna de código de precio real -- 5 columnas (matrícula,
    # designación, plano, norma técnica, precio). El modelo asignó la
    # columna 0 (matrícula real) a `codigo_precio` y dejó `matricula` sin
    # columna.
    filas = [
        ["612260110", "SCV-C-60-ID-318", "P16.0785.02", "03.361.130.2", "15.377,63 €"],
        ["615250090", "SCI-P-54-DD-318 P/DS-P-\n54-318-0'09-CR-D", "", "", "18.268,00 €"],
        ["615250091", "SCI-P-54-DI 318 P/DS-P-\n54-318-0'09-CR-D", "", "", "18.268,00 €"],
        ["615260094", "SCI-P-60-AR-CAC-D.D.\nP/DSH-P-60-318-0,09", "", "", "18.268,00 €"],
    ]
    mapeo_confundido = {
        "codigo_precio": 0, "matricula": None, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 4,
    }
    corregido = corregir_confusion_matricula_codigo_precio(mapeo_confundido, filas)
    assert corregido == {
        "codigo_precio": None, "matricula": 0, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 4,
    }


def test_corregir_confusion_matricula_codigo_precio_no_toca_mapeo_correcto():
    # `codigo_precio` con forma real de código ("P-001"...) nunca se toca,
    # aunque `matricula` esté sin asignar (tabla legítima sin matrícula).
    filas = [["P-001", "BRIDA", "10", "3,50 €"], ["P-002", "PLACA", "5", "7,20 €"]]
    mapeo = {
        "codigo_precio": 0, "matricula": None, "descripcion": 1,
        "unidad_medida": None, "cantidad": 2, "precio_unitario": 3,
    }
    assert corregir_confusion_matricula_codigo_precio(mapeo, filas) == mapeo


def test_corregir_confusion_matricula_codigo_precio_variante_misma_columna_para_los_dos_campos():
    # Segunda variante real, verificada reprocesando el trío 0042/0046/0047
    # contra el stack real (misma tabla, otra llamada al modelo sin
    # cabecera): `matricula` Y `codigo_precio` apuntan a la MISMA columna 0
    # en vez de quedar `matricula` sin asignar -- mismo defecto de fondo
    # (columna 0 es la matrícula real, nunca un código de precio), forma
    # distinta.
    filas = [["612260110", "SCV-C-60-ID-318", "15.377,63 €"]]
    mapeo = {
        "codigo_precio": 0, "matricula": 0, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 2,
    }
    corregido = corregir_confusion_matricula_codigo_precio(mapeo, filas)
    assert corregido == {
        "codigo_precio": None, "matricula": 0, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 2,
    }


def test_corregir_confusion_matricula_codigo_precio_cabecera_desalineada_con_sus_propios_datos():
    # Caso real, bloque 2, sesión 2026-09-12 (continuación):
    # `6.21/28510.0149_ANEJO_bd79fa987e814be3.pdf` p.6 -- cabecera real
    # "Nº MATRÍCULA" en la columna 1, pero la matrícula real cae en la
    # columna 0 (sin nombre) en el 100% de las filas; la columna 1 está
    # vacía siempre. `matricula` SÍ tiene "su propia columna" en la forma
    # del mapeo, pero esa columna no trae ningún dato real.
    filas = [
        ["697100100", None, None, "Arnés anticaída", "..."],
        ["697100105", None, None, "Cuerda de conexión", "..."],
    ]
    mapeo = {
        "codigo_precio": 0, "matricula": 1, "descripcion": 3,
        "unidad_medida": None, "cantidad": None, "precio_unitario": None,
    }
    corregido = corregir_confusion_matricula_codigo_precio(mapeo, filas)
    assert corregido == {
        "codigo_precio": None, "matricula": 0, "descripcion": 3,
        "unidad_medida": None, "cantidad": None, "precio_unitario": None,
    }


def test_corregir_confusion_matricula_codigo_precio_no_toca_si_matricula_en_otra_columna_distinta():
    # `matricula` con su PROPIA columna, distinta de `codigo_precio`: no hay
    # ninguna confusión que resolver, aunque la columna de `codigo_precio`
    # tenga forma numérica de 9 dígitos por otro motivo.
    filas = [["612260110", "612345678", "BRIDA", "3,50 €"]]
    mapeo = {
        "codigo_precio": 0, "matricula": 1, "descripcion": 2,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 3,
    }
    assert corregir_confusion_matricula_codigo_precio(mapeo, filas) == mapeo


def test_corregir_confusion_matricula_codigo_precio_matricula_en_columna_sin_forma_de_matricula():
    # Sesión 2026-09-14, filas reales de `6.21/28510.0016_ANEJO_
    # e40fc4e4546ec90b.pdf` p.13 (cabecera ilegible, fuente sin mapa
    # Unicode): el modelo puso `codigo_precio` en la matrícula real y
    # `matricula` en "REF. ADIF" -- columna llena, pero sin ningún valor con
    # forma de matrícula.
    filas = [
        ["642190360", "RT58", "ALMOHADILLA PARA AISLADORES", "03PAI-\n032-01", "100", "1,53 €"],
        ["642530150", "L5a", "PASADOR PARA MORDAZA DE ATIRANTADO", "01PAT-\n023-01", "200", "0,86 €"],
        ["643130300", "T4", "TORNILLO DE CORREDERA DE\nTRIANGULACIÓN", "01PET-\n003-01", "200", "0,98 €"],
    ]
    mapeo = {
        "codigo_precio": 0, "matricula": 1, "descripcion": 2,
        "unidad_medida": 3, "cantidad": 4, "precio_unitario": 5,
    }
    corregido = corregir_confusion_matricula_codigo_precio(mapeo, filas)
    assert corregido["matricula"] == 0
    assert corregido["codigo_precio"] is None


def test_columna_de_matricula_con_sello_csv_colado_se_reconoce_como_matricula():
    # `6.24/28510.0209_CONTRATO_12d53d58eda5a9e6.pdf` p.95, valores reales de
    # la columna de matrícula: el sello de verificación invertido se cuela en
    # 11 de 18 celdas. Sin contar esas celdas, la columna no llegaba al 50% y
    # nadie la reconocía como matrícula.
    from app.extraccion.firma_estructural import clasificar_columnas

    matriculas = [
        "664510005", "664510010", "664510015", "664510020", "664510025", "664510030\nps",
        "j.adil\n664510035", "av/vs\n664510040", "c/se.b\n664510045", "og.fi\n664510050",
        "da.ed\n664510055", "es//:spt\n664510060", "66 th\nn", "e\n664510070 elb",
        "acif\n664510075", "ireV\n664510080", "664510085", "664510090",
    ]
    filas = [[m, None, f"Material {i}", "1.631,70€", "325,50 €", f"FA-60{i}", "1"] for i, m in enumerate(matriculas)]
    assert clasificar_columnas(filas)[0] == "matricula"
    mapeo = {
        "codigo_precio": 0, "matricula": None, "descripcion": 2,
        "unidad_medida": None, "cantidad": 6, "precio_unitario": 4,
    }
    corregido = corregir_confusion_matricula_codigo_precio(mapeo, filas)
    assert corregido["matricula"] == 0 and corregido["codigo_precio"] is None


def test_completar_matricula_por_contenido_columna_codigo_adif():
    # `6.25/28510.0251_ANEJO_1f2691ba90da3138.pdf` p.23: "CÓDIGO ADIF" es la
    # matrícula, pero ningún alias la reconoce.
    from app.extraccion.mapeo_cabecera import completar_matricula_por_contenido

    filas = [
        ["P-01", "594200000", "PLETINA DE COBRE 10 MM X 5 MM", "UNE 13.605", "NORMAL", None, None, "4,70 €", "M"],
        ["P-02", "594200001", "PLETINA DE COBRE 30 MM X 5 MM", "UNE 13.605", "NORMAL", None, None, "14,00 €", "M"],
        ["P-03", "594200002", "PLETINA DE COBRE 30 MM X 10 MM", "UNE 13.605", "NORMAL", None, None, "28,00 €", "M"],
    ]
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 2, "unidad_medida": 8, "cantidad": None, "precio_unitario": 7}
    assert completar_matricula_por_contenido(mapeo, filas)["matricula"] == 1
    # Ya asignada: no se toca.
    con_matricula = dict(mapeo, matricula=1)
    assert completar_matricula_por_contenido(con_matricula, filas) == con_matricula


def test_completar_matricula_por_contenido_dos_columnas_candidatas_no_adivina():
    from app.extraccion.mapeo_cabecera import completar_matricula_por_contenido

    filas = [["P-01", "594200000", "594200100", "PLETINA", "4,70 €"], ["P-02", "594200001", "594200101", "PLETINA", "5,70 €"]]
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 3, "unidad_medida": None, "cantidad": None, "precio_unitario": 4}
    assert completar_matricula_por_contenido(mapeo, filas)["matricula"] is None


def test_mapeo_determinista_columna_repuesto_es_codigo_material():
    # Sesión 2026-09-14, cabecera real de `6.21/28510.0109_ANEJO_
    # 7bfc92005f43e68e.pdf` p.3 (decisión del cliente: REPUESTO es el
    # "Código del material").
    cabecera = [
        "TIPOLOGÍ\nA\nAPARATO", "CÓDIGO\nDEL\nELEMENT\nO", "REPUESTO", "DESCRIPCIÓN", "PESO en\ntoneladas",
        "PRECIO\nDEL\nELEMENTO", "UNIDAD\nDE\nMEDIDA", None, "IMPACTO DEL FALLO DEL ELEMENTO", None,
    ]
    mapeo = intentar_mapeo_determinista(cabecera)
    assert mapeo["codigo_material"] == 2
    assert mapeo["codigo_precio"] == 1
    assert mapeo["descripcion"] == 3
    assert mapeo["precio_unitario"] == 5


def test_mapeo_determinista_repuesto_dentro_de_otro_nombre_no_es_codigo_material():
    cabecera = ["CÓDIGO DE PRECIO", "DESCRIPCIÓN", "PRECIO DEL REPUESTO"]
    mapeo = intentar_mapeo_determinista(cabecera)
    assert "codigo_material" not in mapeo
    assert mapeo["precio_unitario"] == 2


def test_mapeo_determinista_sin_columna_repuesto_no_trae_codigo_material():
    mapeo = intentar_mapeo_determinista(["CÓDIGO DE PRECIO", "DESCRIPCIÓN", "PRECIO UNITARIO"])
    assert "codigo_material" not in mapeo


# Geometría real de `6.21/28510.0109_ANEJO_7bfc92005f43e68e.pdf`: p.3 (tabla
# con cabecera, 10 columnas -- las dos últimas son artefactos de la celda de
# "IMPACTO") y p.4 (continuación sin cabecera, 8 columnas).
_COLUMNAS_P3 = (
    (38.0, 82.0), (82.0, 125.0), (125.0, 178.0), (178.0, 359.0), (359.0, 408.0),
    (408.0, 458.0), (458.0, 508.0), (508.0, 557.0), (511.0, 554.0), (554.0, 557.0),
)
_COLUMNAS_P4 = (
    (38.0, 82.0), (82.0, 125.0), (125.0, 177.0), (177.0, 359.0), (359.0, 408.0),
    (408.0, 458.0), (458.0, 508.0), (508.0, 557.0),
)
_MAPEO_P3 = {
    "codigo_precio": 1, "matricula": None, "descripcion": 3, "unidad_medida": 6,
    "cantidad": None, "precio_unitario": 5, "codigo_material": 2,
}


def test_heredar_mapeo_por_geometria_caso_real_continuacion():
    assert heredar_mapeo_por_geometria(_MAPEO_P3, _COLUMNAS_P3, _COLUMNAS_P4) == _MAPEO_P3


def test_heredar_mapeo_por_geometria_columnas_desplazadas_no_hereda():
    desplazadas = tuple((x0 + 20, x1 + 20) for x0, x1 in _COLUMNAS_P4)
    assert heredar_mapeo_por_geometria(_MAPEO_P3, _COLUMNAS_P3, desplazadas) is None


def test_heredar_mapeo_por_geometria_reindexa_por_posicion_no_por_indice():
    # Una columna fantasma de más al principio de la continuación: los
    # campos caen un índice más allá, pero en la MISMA posición horizontal.
    con_fantasma = ((20.0, 38.0),) + _COLUMNAS_P4
    heredado = heredar_mapeo_por_geometria(_MAPEO_P3, _COLUMNAS_P3, con_fantasma)
    assert heredado["codigo_precio"] == 2
    assert heredado["descripcion"] == 4
    assert heredado["codigo_material"] == 3


def test_heredar_mapeo_por_geometria_sin_geometria_no_opina():
    assert heredar_mapeo_por_geometria(_MAPEO_P3, (), _COLUMNAS_P4) is None
    assert heredar_mapeo_por_geometria(_MAPEO_P3, _COLUMNAS_P3, ()) is None


def test_corregir_confusion_matricula_codigo_precio_sin_codigo_precio_no_opina():
    mapeo = {
        "codigo_precio": None, "matricula": None, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 2,
    }
    assert corregir_confusion_matricula_codigo_precio(mapeo, [["a", "b", "c"]]) == mapeo


def test_evaluar_coherencia_mapeo_sin_filas_no_opina():
    assert evaluar_coherencia_mapeo({"descripcion": 1, "precio_unitario": 2}, []) is None


# --- corregir_confusion_precio_cantidad / evaluar_coherencia_mapeo sin
# columna de precio (Bloque 2, sesión 2026-09-12, continuación) ---
# Caso real: `6.24/28510.0184_CONTRATO_b15b77d1fff4f23f.pdf` p.97-98,
# equipamiento de telecomunicaciones. La tabla trae Matrícula, Designación,
# Referencia del fabricante, Precio Referencia Adquisición (siempre en
# blanco), Precio Referencia Reparación (siempre en blanco), Cantidad
# Estimada (siempre "1") -- el documento no declara ningún precio para este
# material. Sin más pista que 2-3 filas de ejemplo, el modelo mapeó
# `precio_unitario` a la columna de cantidad, produciendo un "precio" de
# 1,00 € idéntico en cada fila.
_FILAS_EQUIPAMIENTO_SIN_PRECIO = [
    ["664410420", "OpenScapeBranch 550HA DP14", "L30220-D600-B149", "", "", "1"],
    ["664410421", "OpenScape Branch 550HA DP24", "L30220-D600-B150", "", "", "1"],
    ["664410422", "OpenScape Branch 550HA NC", "L30220-D600-B151", "", "", "1"],
    ["664410423", "OpenScape Branch 550HA DP4", "L30220-D600-B152", "", "", "1"],
]


def test_corregir_confusion_precio_cantidad_caso_real_0184():
    mapeo_confundido = {
        "codigo_precio": None, "matricula": 0, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 5,
    }
    corregido = corregir_confusion_precio_cantidad(mapeo_confundido, _FILAS_EQUIPAMIENTO_SIN_PRECIO)
    assert corregido == {
        "codigo_precio": None, "matricula": 0, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": None,
    }


def test_corregir_confusion_precio_cantidad_no_toca_una_columna_de_precio_real():
    filas = [["612260110", "SCV-C-60-ID-318", "15.377,63 €"]]
    mapeo = {
        "codigo_precio": None, "matricula": 0, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 2,
    }
    assert corregir_confusion_precio_cantidad(mapeo, filas) == mapeo


def test_corregir_confusion_precio_cantidad_sin_precio_asignado_no_opina():
    mapeo = {
        "codigo_precio": None, "matricula": 0, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": None,
    }
    assert corregir_confusion_precio_cantidad(mapeo, _FILAS_EQUIPAMIENTO_SIN_PRECIO) == mapeo


def test_evaluar_coherencia_mapeo_acepta_tabla_sin_ninguna_columna_de_precio_real():
    # Tras `corregir_confusion_precio_cantidad`, precio_unitario queda sin
    # columna -- confirmado por contenido (ninguna columna de la tabla tiene
    # forma de precio real), no un fallo de mapeo: la tabla debe seguir
    # coherente (matrícula y descripción sí están bien), no descartarse
    # entera del Excel entregable.
    mapeo = {
        "codigo_precio": None, "matricula": 0, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": None,
    }
    assert evaluar_coherencia_mapeo(mapeo, _FILAS_EQUIPAMIENTO_SIN_PRECIO) is None


def test_evaluar_coherencia_mapeo_sigue_exigiendo_precio_si_alguna_columna_sí_tiene_forma() :
    # Red de seguridad: si de verdad existe una columna con forma de precio
    # en la tabla (`6.20/28510.0042`/`0046`/`0047`, caso ya cubierto arriba)
    # y el mapeo no la encontró, sigue siendo incoherente -- el atajo de
    # "sin ninguna columna de precio" no debe tapar un fallo de mapeo real.
    motivo = evaluar_coherencia_mapeo(
        {"codigo_precio": None, "matricula": 0, "descripcion": 1,
         "unidad_medida": None, "cantidad": None, "precio_unitario": None},
        _FILAS_TRIO_P35,
    )
    assert motivo is not None
    assert "precio_unitario" in motivo


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


def test_columna_tipo_de_traviesa_es_codigo_material_aunque_sea_la_descripcion():
    # Sesión 2026-09-17, cabecera real de `6.24/28510.0177` p.112 (mapeada
    # por el modelo, que nunca devuelve `codigo_material`).
    cabecera = [
        "CÓDIGO DE\nPRECIO", "TIPO DE TRAVIESA*", "MEDIDAS ESTÁNDAR (mm)", "USO DE LA TRAVIESA",
        "UNIDAD\nDE\nMEDIDA", "CANTIDAD\nESTIMADA\nDE\nREFERENCIA", None, "PRECIO DE REFERENCIA DEL ELEMENTO (€)",
    ]
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": 4, "cantidad": 5, "precio_unitario": 7}
    assert completar_columna_codigo_material(cabecera, mapeo)["codigo_material"] == 1


def test_columna_tipo_ocupada_por_otro_campo_no_es_codigo_material():
    cabecera = ["TIPO DE TRAVIESA", "DESCRIPCIÓN", "PRECIO"]
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    assert "codigo_material" not in completar_columna_codigo_material(cabecera, mapeo)


# --- Bloque 8, sesión 2026-09-18 (sexta parte) ----------------------------


def test_completar_codigo_precio_por_contenido_recupera_codificacion_del_precio():
    """`6.21/28510.0152` p.114 (rodillos de aguja): la cabecera llama a la
    columna "CODIFICACIÓN DEL PRECIO" y ni el determinista ni el modelo la
    asignan, así que la fila que `pdfplumber` funde (cuatro artículos en una)
    no se podía separar. La corrección mira los DATOS, no el nombre de la
    columna -- por eso no reabre la regresión del cuadro de balasto que sí
    causaba añadir el alias (ver el test de guarda de más arriba)."""
    mapeo = {
        "codigo_precio": None, "matricula": 1, "descripcion": 2,
        "unidad_medida": 3, "cantidad": 7, "precio_unitario": 8,
    }
    filas = [[
        "P-1\nP-2\nP-3\nP-4", "619900701\n619900702\n619900703\nPA",
        "Rodillo de presión para\nel talón\nRodillo de presión para\nla punta",
        "ud\nud\nud", "238\n68\n5", None, None, "600\n200\n20\n1",
        "366,00 €\n466,00 €\n155,00 €\n34.100,00 €",
    ]]

    assert completar_codigo_precio_por_contenido(mapeo, filas)["codigo_precio"] == 0


def test_completar_codigo_precio_no_toca_un_mapeo_que_ya_tiene_columna():
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1,
             "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    filas = [["P-1", "Rodillo", "366,00 €"]]
    assert completar_codigo_precio_por_contenido(mapeo, filas) == mapeo


def test_completar_codigo_precio_no_adivina_con_una_columna_que_no_lo_es():
    """Una columna libre cuyos valores no son todos código de precio no se
    toca: ni una matrícula, ni una referencia normativa, ni texto."""
    mapeo = {"codigo_precio": None, "matricula": None, "descripcion": 1,
             "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    filas = [["03.360.571.8", "Rodillo", "366,00 €"], ["03.360.571.8", "Placa", "155,00 €"]]
    assert completar_codigo_precio_por_contenido(mapeo, filas)["codigo_precio"] is None
    # Y con DOS columnas libres que las dos tienen forma de código, tampoco
    # se elige: no se adivina.
    mapeo2 = {"codigo_precio": None, "matricula": None, "descripcion": 2,
              "unidad_medida": None, "cantidad": None, "precio_unitario": 3}
    filas2 = [["P-1", "P-2", "Rodillo", "366,00 €"]]
    assert completar_codigo_precio_por_contenido(mapeo2, filas2)["codigo_precio"] is None
