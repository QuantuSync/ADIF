from decimal import Decimal

from app.catalogo import (
    _combinar_por_clave,
    _normalizar_codigo_precio,
    buscar_posible_duplicado_huerfana,
    campos_vacios_por_valor_de_otro_lote,
    calcular_clave_linea,
    construir_linea_catalogo,
    construir_lineas_desde_tabla,
    guardar_lineas_catalogo,
    podar_lineas_heredadas_obsoletas,
    podar_lineas_obsoletas_de_documento,
)
from app.extraccion.invalidado import INVALIDADO
from app.extraccion.tabla import TablaExtraida
from app.models import Expediente, Lote, LineaCatalogo


def _lote(db_session, identificador="1"):
    expediente = Expediente(codigo_expediente="6.24/28510.9999")
    db_session.add(expediente)
    db_session.commit()
    lote = Lote(expediente_id=expediente.id, identificador_lote=identificador)
    db_session.add(lote)
    db_session.commit()
    return lote


def test_construir_linea_catalogo_deriva_precio_adjudicado():
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": 4, "precio_unitario": 5}
    fila = ["P-001", "697500900", "GUANTE X", "UN", "30", "24,00"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=11, documento_origen_id=7, expediente_id=1, baja_lote=Decimal("0.10"), orden_aparicion=0
    )

    assert linea["clave_linea"] == "P-001"
    assert linea["expediente_id"] == 1
    assert linea["matricula"] == "697500900"
    assert linea["descripcion"] == "GUANTE X"
    assert linea["cantidad"] == Decimal("30")
    assert linea["precio_unitario"] == Decimal("24.00")
    assert linea["precio_adjudicado"] == Decimal("21.600")  # 24,00 * 0,90
    assert linea["documento_origen_id"] == 7
    assert linea["pagina"] == 11


def test_construir_linea_catalogo_guarda_la_unidad_en_su_forma_unica_y_la_original_aparte():
    # Sesión 2026-09-16 (noche): "UN" es "ud"; lo que decía la celda, aparte.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": 4, "precio_unitario": 5}
    fila = ["P-001", "697500900", "GUANTE X", "UN", "30", "24,00"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=11, documento_origen_id=7, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea["unidad_medida"] == "ud"
    assert linea["unidad_medida_original"] == "UN"


def test_construir_linea_catalogo_sin_baja_no_deriva_precio_adjudicado():
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    fila = ["P-050", "PARTIDA ALZADA", "100.000,00"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=18, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea["precio_unitario"] == Decimal("100000.00")
    assert linea["precio_adjudicado"] is None


def test_construir_linea_catalogo_codigo_partido_por_salto_de_linea_se_limpia():
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    fila = ["P-\n001", "Traviesa", "1,00\n€"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=23, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea["codigo_precio"] == "P-001"
    assert linea["precio_unitario"] == Decimal("1.00")


def test_clave_linea_usa_codigo_precio_por_encima_de_matricula():
    assert calcular_clave_linea("P-001", "697500900", "x", 0) == "P-001"


def test_construir_linea_catalogo_descarta_pie_de_tabla():
    # Sesión de rodaje 2026-09-03 (expedientes 6.23/28510.0104 y otros): una
    # fila de resumen ("IVA", "TOTAL CON IVA", "PRESUPUESTO DE LICITACIÓN")
    # no es una línea de material — el mapeo de cabecera la trata como una
    # fila normal y su etiqueta cae en la columna de matrícula, que es
    # varchar(9) y revienta el INSERT con cualquier texto más largo.
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": None, "unidad_medida": None, "cantidad": None, "precio_unitario": 1}
    for etiqueta in ("IVA", "PRESUPUESTO DE LICITACIÓN", "TOTAL CON IVA"):
        fila = [etiqueta, "11.634,00 €"]
        linea = construir_linea_catalogo(
            fila, mapeo, pagina=13, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
        )
        assert linea is None, etiqueta


def test_construir_linea_catalogo_recupera_partida_alzada_mal_alineada():
    # Expediente 6.24/28510.0064 (sesión de rodaje 2026-09-03): una partida
    # alzada no tiene celda de matrícula propia, así que sus columnas se
    # desplazan y el texto que debía caer en descripción aterriza en
    # matrícula. CONTEXTO.md sección 2: la partida alzada es una línea
    # legítima del catálogo — se recupera, no se descarta como un pie de
    # tabla, pero nunca con texto en la columna de matrícula.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": None, "cantidad": None, "precio_unitario": 3}
    fila = ["P-405", "Partida alzada a justificar para imprevistos", "", "5.000,00 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=28, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["matricula"] is None
    assert linea["descripcion"] == "Partida alzada a justificar para imprevistos"
    assert linea["precio_unitario"] == Decimal("5000.00")
    assert linea["motivo_revision"] is None


def test_construir_linea_catalogo_recupera_descripcion_de_columna_fantasma():
    # Expediente real 6.20/28510.0054 (sesión de duplicados de partidas
    # alzadas, 2026-09-05): el contrato firmado incluye como anejo propio una
    # copia íntegra del mismo cuadro de precios que ya trae el documento
    # `anejo` independiente. En esa copia, `pdfplumber` intercala una columna
    # en blanco de más entre matrícula y descripción -- la celda de
    # descripción sale vacía y el texto real cae en la columna siguiente, sin
    # mapear. Sin matrícula que perder (partida alzada, CONTEXTO.md sección 2),
    # se recupera de esa columna en vez de perderse -- de lo contrario, la
    # misma partida alzada del documento `anejo` (con descripción) y esta
    # copia (sin ella) generan claves distintas (`calcular_clave_linea` cae al
    # hash de descripción+orden para filas sin matrícula ni código de precio)
    # y quedan como dos filas duplicadas en vez de fundirse en una.
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": 3, "cantidad": 5, "precio_unitario": 4}
    fila = ["", "", "PARTIDA ALZADA A JUSTIFICAR PARA IMPREVISTOS", None, "161.999,04 €", "1"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=120, documento_origen_id=231, expediente_id=1, baja_lote=None, orden_aparicion=174
    )

    assert linea is not None
    assert linea["matricula"] is None
    assert linea["descripcion"] == "PARTIDA ALZADA A JUSTIFICAR PARA IMPREVISTOS"
    assert linea["precio_unitario"] == Decimal("161999.04")
    assert linea["motivo_revision"] is not None


def test_construir_linea_catalogo_no_recupera_descripcion_si_la_columna_siguiente_esta_en_uso():
    # Cuando descripción y el siguiente campo del mapeo son columnas
    # contiguas de verdad (no hay ninguna columna fantasma), esa celda es el
    # dato legítimo de otro campo -- copiarla como descripción inventaría un
    # valor que no es tal. Una descripción vacía aquí no se recupera.
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": 2, "cantidad": None, "precio_unitario": 3}
    fila = ["P-050", "", "UD", "100.000,00 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=18, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["descripcion"] == ""


def test_construir_linea_catalogo_matricula_no_reconocible_se_vacia_y_marca_revision():
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": None, "cantidad": None, "precio_unitario": 3}
    fila = ["P-016", "ifireV", "PÉRTIGA VERIFICADORA", "2.298,82 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=10, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["matricula"] is None
    assert linea["motivo_revision"] is not None


def test_construir_linea_catalogo_recupera_matricula_de_celda_con_ruido_en_otra_linea():
    # Caso real, bloque 2, sesión 2026-09-12 (continuación):
    # `6.24/28510.0184_CONTRATO_b15b77d1fff4f23f.pdf` p.96 -- un pie de
    # verificación de firma electrónica ajeno a la tabla (invertido y con
    # cada carácter duplicado por cómo pdfplumber lo superpone en esa
    # página) cae en su propia línea dentro de la misma celda de matrícula
    # que la fila siguiente.
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    fila = ["iirreeVV\n664410216", "DIUT2", ""]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=96, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["matricula"] == "664410216"
    assert linea["motivo_revision"] is not None
    assert "recuperada de una celda" in linea["motivo_revision"]


def test_construir_linea_catalogo_recupera_matricula_de_celda_con_ruido_sin_salto_de_linea():
    # Misma familia de defecto que el test de arriba, pero el ruido queda
    # pegado a la matrícula real SIN salto de línea (el solape vertical de
    # los dos textos varía de fila a fila) -- verificado contra el mismo
    # documento real, p.97-98.
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    fila = ["664410433pp", "Cargador JABRA 920", ""]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=10, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["matricula"] == "664410433"


def test_construir_linea_catalogo_no_recupera_matricula_si_hay_dos_candidatas():
    # Fila fusionada por pdfplumber con dos matrículas reales pegadas
    # (CONTEXTO.md sección 8) -- dos números de 9 dígitos válidos a la vez,
    # ninguno con más derecho a ser "la" matrícula de esta fila: se
    # descarta sin adivinar, como antes de este arreglo.
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    fila = ["611150110611150111", "BRIDA", "3,50 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=10, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["matricula"] is None
    assert "no reconocible" in linea["motivo_revision"]


def test_construir_linea_catalogo_guion_suelto_en_matricula_no_marca_revision():
    # CONTEXTO.md sección 26 (arreglo de los 3 que seguían en revisión tras el
    # criterio de lote laxo): expediente real 6.24/28510.0117, 39 filas
    # reales con este patrón exacto -- un guion suelto en la celda de
    # matrícula es la convención del documento para "vacío", no un valor
    # ilegible que haga falta revisar.
    mapeo = {
        "codigo_precio": 0, "matricula": 1, "descripcion": 3,
        "unidad_medida": 4, "cantidad": 6, "precio_unitario": 7,
    }
    fila = ["P-066", "-", "-", "MVI69-104S MODULO COMUNICACIONES 104 para CompactLogix", "UD", "0", "3", "3.015,00 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=5, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["matricula"] is None
    assert linea["precio_unitario"] == Decimal("3015.00")
    assert linea["motivo_revision"] is None


def test_construir_linea_catalogo_guion_suelto_en_cantidad_no_marca_revision():
    # Expediente real 6.24/28510.0203: tabla de características técnicas
    # (CONTEXTO.md sección 17.2, "sin columna de precio ni de cantidad" es un
    # caso ya conocido) donde la celda de cantidad trae un guion en vez de
    # quedar vacía.
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": 2, "precio_unitario": 3}
    fila = ["PN09", "Traviesa monobloque de hormigón pretensado singular", "-", "4000,00 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=12, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["cantidad"] is None
    assert linea["precio_unitario"] == Decimal("4000.00")
    assert linea["motivo_revision"] is None


def test_construir_linea_catalogo_valor_ilegible_no_revienta_marca_revision():
    # CONTEXTO.md, sesión de rodaje 2026-09-03: un valor de precio que no se
    # puede interpretar (fuente sin ToUnicode) no debe tirar la fila entera
    # ni la tabla — la línea se guarda igual, con el campo en None y un
    # motivo de revisión.
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    fila = ["P-003", "Remonte de balasto", "(cid:1005)(cid:853)(cid:1004)(cid:1004)(cid:1004)(cid:1004)"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=120, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["precio_unitario"] is None
    assert linea["motivo_revision"] is not None
    assert "no interpretable" in linea["motivo_revision"]


def test_construir_linea_catalogo_descarta_fila_totales_de_pie_de_tabla():
    # Sesión de filas fantasma (2026-09-04), expediente real 6.23/28510.0066
    # (ANEJO_1, cuadro de balasto por lote): la fila TOTALES de pie de tabla
    # ("CODIFICACIÓN DEL PRECIO", "DESCRIPCIÓN", "UNIDADES", "CANTIDADES...",
    # "PRECIO...", "TOTALES") no trae etiqueta reconocible por
    # `_ETIQUETAS_PIE_TABLA` -- solo un importe en la sexta columna, que
    # ninguna cabecera mapea a `precio_unitario`. No es una línea de
    # material: sin ninguna descripción real en la fila, no hay nada que
    # recuperar, y se descarta tal como pedía el encargo original.
    mapeo = {
        "codigo_precio": 0, "matricula": None, "descripcion": 1,
        "unidad_medida": 2, "cantidad": 3, "precio_unitario": 4,
    }
    fila = [None, None, None, None, None, "960.480,00 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=17, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is None


def test_construir_linea_catalogo_descarta_fila_fantasma_de_desbordamiento_de_descripcion():
    # Expediente real 6.23/28510.0051 (CONTRATO_2 p.153, sesión 2026-09-06):
    # en esta tabla la primera línea de una descripción envuelta cae en la
    # banda visual de la fila ANTERIOR, así que pdfplumber emite una fila
    # propia solo con ese fragmento de texto y todas las demás columnas en
    # blanco -- no es una línea de material nueva (el material real, con su
    # código, su unidad y su precio, se cuenta en la fila de al lado). Antes
    # de este arreglo se guardaba como línea de catálogo con la baja del
    # lote heredada pero sin ningún precio que derivar.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": None, "precio_unitario": 5}
    fila = [None, None, "I-TC", None, "ALTO", None]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=153, documento_origen_id=40, expediente_id=18, baja_lote=Decimal("0.2531"), orden_aparicion=0
    )

    assert linea is None


def test_construir_linea_catalogo_no_descarta_fila_con_codigo_aunque_no_tenga_precio():
    # Contraste de la prueba anterior: una fila que sí trae código de precio
    # (identifica un material real) pero no precio por otro motivo no es una
    # fila fantasma -- sigue su camino normal, a revisión si hace falta,
    # nunca se descarta en silencio.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": None, "precio_unitario": 5}
    fila = ["P-100", None, "Material real sin precio", "UD.", "ALTO", None]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=1, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["codigo_precio"] == "P-100"


def test_construir_linea_catalogo_no_separa_si_los_precios_no_casan_uno_a_uno():
    # Dos códigos fusionados pero un solo precio (no dos): no hay pareja
    # código-precio uno a uno que recuperar sin adivinar cuál de los dos
    # códigos se queda sin precio. Esta prueba llama directamente a
    # `construir_linea_catalogo` (sin pasar por `_dividir_fila_multiple`,
    # que solo interviene desde `construir_lineas_desde_tabla`), para
    # comprobar el camino normal de siempre: el precio único sí se
    # interpreta bien, pero el código fusionado sigue sin reconocerse.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": None, "precio_unitario": 5}
    fila = ["P-0058\nP-0059", None, "CAM1H-60-1500-TC-D\nCAM1H-60-1500-TC-I", "UD.\nUD.", "ALTO\nALTO", "306.351,49 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=153, documento_origen_id=None, expediente_id=1, baja_lote=Decimal("0.10"), orden_aparicion=0
    )

    assert linea is not None
    assert linea["precio_unitario"] == Decimal("306351.49")
    assert linea["codigo_precio"] == "P-0058P-0059"
    assert "no reconocido" in linea["motivo_revision"]


def test_construir_lineas_desde_tabla_no_separa_si_los_precios_no_casan_uno_a_uno():
    # Mismo caso, pero pasando por `construir_lineas_desde_tabla` (donde sí
    # interviene `_dividir_fila_multiple`): con solo un precio para dos
    # códigos, la fila no se separa -- sigue como una única línea, igual que
    # la prueba anterior.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": None, "precio_unitario": 5}
    tabla = TablaExtraida(
        cabecera=["CÓDIGO", "MATRÍCULA", "DESCRIPCIÓN", "UNIDAD", "IMPACTO", "PRECIO"],
        filas=[
            ["P-0058\nP-0059", None, "CAM1H-60-1500-TC-D\nCAM1H-60-1500-TC-I", "UD.\nUD.", "ALTO\nALTO", "306.351,49 €"],
        ],
        pagina=153,
        bbox=(0.0, 0.0, 100.0, 100.0),
    )

    lineas = construir_lineas_desde_tabla(tabla, mapeo, None, expediente_id=1, baja_lote=None, orden_inicial=0)

    assert len(lineas) == 1
    assert lineas[0]["codigo_precio"] == "P-0058P-0059"


def test_construir_lineas_desde_tabla_separa_fila_fusionada_con_dos_precios():
    # Expediente real 6.23/28510.0051 (CONTRATO_2 p.155, sesión 2026-09-06):
    # dos filas de datos reales y consecutivas (P-0090, P-0091) sin
    # suficiente diferencia de altura entre ellas se funden en una sola fila
    # extraída por pdfplumber, con el código y el precio unitario trayendo
    # dos valores reales -- uno por línea de texto -- en la misma celda.
    # Antes de este arreglo, "P-0090P-0091" no encajaba en ningún formato de
    # código conocido, el precio quedaba sin interpretar, y la línea se
    # guardaba con la baja del lote pero sin precio adjudicado que derivar
    # (el bug reportado por el cliente). La fila fantasma final (solo
    # descripción) no debe generar ninguna línea de catálogo.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": None, "precio_unitario": 5}
    tabla = TablaExtraida(
        cabecera=["CÓDIGO", "MATRÍCULA", "DESCRIPCIÓN", "UNIDAD", "IMPACTO", "PRECIO"],
        filas=[
            ["P-0089", None, "cruz obtuso DMRDH-G-60-\n250-0,11-CR-D-TC\nSemicambio izq (sencillo)", "UD.", "ALTO", "38.012,29 €"],
            [
                "P-0090\nP-0091", None,
                "DMRDH-G-60-250-0,11-CR-\nD-TC con 2 motores\nSemicambio dcha (doble) SIN\ncruz obtuso DMRDH-G-60-",
                "UD.\nUD.", "ALTO\nALTO", "29.240,23 €\n38.012,29 €",
            ],
            [None, None, "250-0,11-CR-D-TC con 2\nmotores\nSemicambio izq (sencillo)", None, None, None],
        ],
        pagina=155,
        bbox=(0.0, 0.0, 100.0, 100.0),
    )

    lineas = construir_lineas_desde_tabla(tabla, mapeo, 40, expediente_id=18, baja_lote=Decimal("0.2531"), orden_inicial=0)

    por_codigo = {linea["codigo_precio"]: linea for linea in lineas}
    assert set(por_codigo) == {"P-0089", "P-0090", "P-0091"}
    assert por_codigo["P-0090"]["precio_unitario"] == Decimal("29240.23")
    assert por_codigo["P-0091"]["precio_unitario"] == Decimal("38012.29")
    esperado_90 = Decimal("29240.23") * (Decimal("1") - Decimal("0.2531"))
    esperado_91 = Decimal("38012.29") * (Decimal("1") - Decimal("0.2531"))
    assert por_codigo["P-0090"]["precio_adjudicado"] == esperado_90
    assert por_codigo["P-0091"]["precio_adjudicado"] == esperado_91
    for codigo in ("P-0090", "P-0091"):
        assert "línea recuperada de una fila que fusionaba" in por_codigo[codigo]["motivo_revision"]
    assert len(lineas) == 3


def test_construir_lineas_desde_tabla_separa_fila_fusionada_con_precios_iguales():
    # Mismo documento, P-0058/P-0059: dos códigos reales con precio igual
    # por casualidad (no un valor duplicado dentro de la celda de un único
    # código -- eso ya lo cubre `_resolver_valor_duplicado`). Debe separarse
    # en dos líneas de catálogo con su propio código, no fundirse en una.
    #
    # Auditoría 2026-09-08, duplicado exacto reportado por el cliente en
    # 6.23/28510.0051: la descripción también se divide 1:1 (dos líneas de
    # texto para dos códigos, verificado contra el PDF real) -- cada línea
    # se queda con SU propia descripción ("...-TC-D" / "...-TC-I", dos
    # piezas D/I completas, mismo patrón que P-0056/P-0057 dos filas más
    # arriba en la misma tabla, sin fusionar), no con el bloque entero
    # repetido. Sin ambigüedad que confirmar, no lleva motivo_revision.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": None, "precio_unitario": 5}
    tabla = TablaExtraida(
        cabecera=["CÓDIGO", "MATRÍCULA", "DESCRIPCIÓN", "UNIDAD", "IMPACTO", "PRECIO"],
        filas=[
            [
                "P-0058\nP-0059", None, "CAM1H-60-1500-TC-D\nCAM1H-60-1500-TC-I",
                "UD.\nUD.", "ALTO\nALTO", "306.351,49 €\n306.351,49 €",
            ],
        ],
        pagina=153,
        bbox=(0.0, 0.0, 100.0, 100.0),
    )

    lineas = construir_lineas_desde_tabla(tabla, mapeo, None, expediente_id=1, baja_lote=None, orden_inicial=0)

    assert len(lineas) == 2
    por_codigo = {linea["codigo_precio"]: linea for linea in lineas}
    assert set(por_codigo) == {"P-0058", "P-0059"}
    assert por_codigo["P-0058"]["descripcion"] == "CAM1H-60-1500-TC-D"
    assert por_codigo["P-0059"]["descripcion"] == "CAM1H-60-1500-TC-I"
    assert all(linea["precio_unitario"] == Decimal("306351.49") for linea in lineas)
    assert all(not linea["motivo_revision"] for linea in lineas)


def test_construir_lineas_desde_tabla_separa_fila_fusionada_sin_precio_si_matricula_y_descripcion_cuadran():
    # Sesión 2026-09-17, `6.24/28510.0208` p.99: tabla de módulos sin ningún
    # precio; código, matrícula y descripción se dividen los tres en 2.
    mapeo = {"codigo_precio": 2, "matricula": 0, "descripcion": 1, "unidad_medida": None, "cantidad": 5, "precio_unitario": 3}
    tabla = TablaExtraida(
        cabecera=["Matrícula", "Designación", "REFERENCIA DEL FABRICANTE", "Importe Unitario", "Importe Reparación", "Cantidad Estimada"],
        filas=[[
            "66.452.0010\n66.452.0015",
            'Módulo Repartidor de Línea, "REPLIN -924\nMódulo Cierre de Estación, "CIESTA", P-942',
            "P-924\nP-942", "", "", "1",
        ]],
        pagina=99,
        bbox=(0.0, 0.0, 100.0, 100.0),
    )

    lineas = construir_lineas_desde_tabla(tabla, mapeo, None, expediente_id=1, baja_lote=None, orden_inicial=0)

    por_codigo = {linea["codigo_precio"]: linea for linea in lineas}
    assert set(por_codigo) == {"P-924", "P-942"}
    assert por_codigo["P-942"]["descripcion"] == 'Módulo Cierre de Estación, "CIESTA", P-942'


def test_construir_lineas_desde_tabla_sin_precio_ni_matricula_repartida_no_separa():
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": None, "cantidad": None, "precio_unitario": 3}
    tabla = TablaExtraida(
        cabecera=["CÓDIGO", "MATRÍCULA", "DESCRIPCIÓN", "PRECIO"],
        filas=[["P-244\nP-245\nP-246", "617050011", "SCV-V-60-II-1500 HORM", None]],
        pagina=123,
        bbox=(0.0, 0.0, 100.0, 100.0),
    )

    lineas = construir_lineas_desde_tabla(tabla, mapeo, None, expediente_id=1, baja_lote=None, orden_inicial=0)

    assert len(lineas) == 1


def test_construir_lineas_desde_tabla_separa_fila_fusionada_con_unidades_de_menos():
    # Sesión 2026-09-17, forma real de `6.21/28510.0152` p.114: cuatro
    # artículos fundidos, la partida alzada sin unidad (3 unidades para 4
    # filas) y descripciones envueltas. Se separan con su precio, cantidad y
    # matrícula; la unidad no se adivina y todas van a revisión. (En ese
    # documento la columna "CODIFICACIÓN DEL PRECIO" sigue sin mapearse, ver
    # `test_mapeo_determinista_no_reconoce_codificacion_del_precio`, así que
    # allí la fila no se separa todavía.)
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": 7, "precio_unitario": 8}
    tabla = TablaExtraida(
        cabecera=[
            "CODIFICACIÓN DEL PRECIO", "Nº MATRÍCULA", "DESCRIPCIÓN", "UNIDADES", "", "CANTIDADES A", "",
            "CANTIDADES ESTIMADAS DE REFERENCIA", "PRECIO UNITARIO DE REFERENCIA",
        ],
        filas=[[
            "P-1\nP-2\nP-3\nP-4", "619900701\n619900702\n619900703\nPA",
            "Rodillo de presión para\nel talón\nRodillo de presión para\nla punta\nPlaca resbaladera para\n"
            "rodillo de presión\nPartida alzada a\njustificar para\nimprevistos",
            "ud\nud\nud", None, "238\n68\n5", None, "600\n200\n20\n1", "366,00 €\n466,00 €\n155,00 €\n34.100,00 €",
        ]],
        pagina=114,
        bbox=(0.0, 0.0, 100.0, 100.0),
    )

    lineas = construir_lineas_desde_tabla(tabla, mapeo, None, expediente_id=1, baja_lote=None, orden_inicial=0)

    por_codigo = {linea["codigo_precio"]: linea for linea in lineas}
    assert set(por_codigo) == {"P-1", "P-2", "P-3", "P-4"}
    assert por_codigo["P-2"]["precio_unitario"] == Decimal("466.00")
    assert por_codigo["P-2"]["cantidad"] == Decimal("200")
    assert por_codigo["P-2"]["matricula"] == "619900702"
    assert por_codigo["P-4"]["precio_unitario"] == Decimal("34100.00")
    assert all(linea["unidad_medida"] is None for linea in lineas)
    assert all(linea["motivo_revision"] for linea in lineas)


def test_combinar_por_clave_no_funde_dos_lineas_de_la_misma_fila_fusionada():
    # Defecto encontrado verificando el arreglo de la fila fusionada contra
    # la base de datos real (expediente 18, lote 179): separar una fila
    # fusionada en dos códigos no bastaba si la descripción quedaba
    # AMBIGUA (número de líneas de descripción distinto de N, así que no se
    # reparte 1:1 -- auditoría 2026-09-08, ver
    # `test_construir_lineas_desde_tabla_separa_fila_fusionada_con_dos_precios`
    # para el caso real, P-0090/P-0091, donde la descripción trae 4 líneas
    # para solo 2 códigos). Las dos líneas salen entonces con la MISMA
    # descripción (el bloque entero de la fila), sin matrícula, y con
    # precios que pueden coincidir -- firma de material idéntica, así que
    # `_combinar_por_clave` volvía a fundirlas en una sola: en la base de
    # datos quedaba UNA fila, con `clave_linea` de un código y
    # `codigo_precio` del otro, y uno de los dos materiales desaparecía del
    # catálogo entero. El mismo fallo que el arreglo venía a corregir, un
    # paso más allá y con peor pinta (la línea superviviente parece
    # correcta). `_firma_material` no da firma a estas líneas mientras la
    # descripción siga sin poder repartirse con garantía.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": None, "precio_unitario": 5}
    tabla = TablaExtraida(
        cabecera=["CÓDIGO", "MATRÍCULA", "DESCRIPCIÓN", "UNIDAD", "IMPACTO", "PRECIO"],
        filas=[
            [
                "P-0090\nP-0091", None,
                "DMRDH-G-60-250-0,11-CR-\nD-TC con 2 motores\nSemicambio dcha (doble)",
                "UD.\nUD.", "ALTO\nALTO", "306.351,49 €\n306.351,49 €",
            ],
        ],
        pagina=57,
        bbox=(0.0, 0.0, 100.0, 100.0),
    )
    lineas = construir_lineas_desde_tabla(tabla, mapeo, None, expediente_id=18, baja_lote=None, orden_inicial=0)

    combinadas = _combinar_por_clave(lineas)

    assert len(combinadas) == 2
    assert {linea["codigo_precio"] for linea in combinadas} == {"P-0090", "P-0091"}
    assert {linea["clave_linea"] for linea in combinadas} == {"P-0090", "P-0091"}


def test_guardar_lineas_catalogo_no_pierde_un_codigo_de_una_fila_fusionada(db_session):
    # El mismo defecto, comprobado donde de verdad dolía: contra la base de
    # datos. Antes del arreglo esto guardaba una sola fila; ahora guarda los
    # dos materiales reales, cada uno con su código como clave. Auditoría
    # 2026-09-08: la descripción también se reparte 1:1 en este caso (dos
    # líneas para dos códigos), así que ninguna de las dos queda marcada
    # para revisión -- ver el caso ambiguo (descripción con más líneas que
    # códigos) en `test_combinar_por_clave_no_funde_dos_lineas_de_la_misma_fila_fusionada`.
    lote = _lote(db_session)
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": None, "precio_unitario": 5}
    tabla = TablaExtraida(
        cabecera=["CÓDIGO", "MATRÍCULA", "DESCRIPCIÓN", "UNIDAD", "IMPACTO", "PRECIO"],
        filas=[
            [
                "P-0058\nP-0059", None, "CAM1H-60-1500-TC-D\nCAM1H-60-1500-TC-I",
                "UD.\nUD.", "ALTO\nALTO", "306.351,49 €\n306.351,49 €",
            ],
        ],
        pagina=57,
        bbox=(0.0, 0.0, 100.0, 100.0),
    )
    lineas = construir_lineas_desde_tabla(
        tabla, mapeo, None, expediente_id=lote.expediente_id, baja_lote=None, orden_inicial=0
    )

    resultado = guardar_lineas_catalogo(db_session, lote.id, lineas)
    db_session.commit()

    assert resultado.creadas == 2
    guardadas = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id).all()
    assert {linea.codigo_precio for linea in guardadas} == {"P-0058", "P-0059"}
    assert {linea.clave_linea for linea in guardadas} == {"P-0058", "P-0059"}
    assert {linea.descripcion for linea in guardadas} == {"CAM1H-60-1500-TC-D", "CAM1H-60-1500-TC-I"}
    assert all(linea.precio_unitario == Decimal("306351.49") for linea in guardadas)
    assert all(not linea.motivo_revision for linea in guardadas)


def test_guardar_lineas_catalogo_fila_fusionada_reprocesada_no_duplica(db_session):
    # Contrapartida de la prueba anterior: quitarle la firma de material a
    # estas líneas no puede romper la idempotencia del reproceso (el ciclo
    # de mantenimiento vuelve a extraer los mismos documentos cada semana).
    # Su `clave_linea` es su propio código, que sí es estable: la segunda
    # pasada actualiza las dos filas, no crea dos más.
    lote = _lote(db_session)
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": None, "precio_unitario": 5}
    tabla = TablaExtraida(
        cabecera=["CÓDIGO", "MATRÍCULA", "DESCRIPCIÓN", "UNIDAD", "IMPACTO", "PRECIO"],
        filas=[
            [
                "P-0058\nP-0059", None, "CAM1H-60-1500-TC-D\nCAM1H-60-1500-TC-I",
                "UD.\nUD.", "ALTO\nALTO", "306.351,49 €\n306.351,49 €",
            ],
        ],
        pagina=57,
        bbox=(0.0, 0.0, 100.0, 100.0),
    )

    def _lineas():
        return construir_lineas_desde_tabla(
            tabla, mapeo, None, expediente_id=lote.expediente_id, baja_lote=None, orden_inicial=0
        )

    primera = guardar_lineas_catalogo(db_session, lote.id, _lineas())
    segunda = guardar_lineas_catalogo(db_session, lote.id, _lineas())
    db_session.commit()

    assert (primera.creadas, primera.actualizadas) == (2, 0)
    assert (segunda.creadas, segunda.actualizadas) == (0, 2)
    assert db_session.query(LineaCatalogo).filter_by(lote_id=lote.id).count() == 2


def test_construir_linea_catalogo_fragmento_wrap_sin_precio_se_descarta():
    # Expediente real 6.20/28510.0136 (ANEJO_3, hilo de contacto): fila de
    # continuación de una descripción envuelta entre filas de `pdfplumber`
    # -- el fragmento de texto ("120MM2 DE") cae en la columna 3, una
    # posición a la derecha de donde la cabecera sitúa "descripción" (2),
    # pero la fila no trae ningún precio en ninguna posición cercana. Sin la
    # pareja descripción+precio en el mismo desplazamiento, no es
    # recuperable: es relleno, se descarta como pedía el encargo original.
    mapeo = {
        "codigo_precio": None, "matricula": 0, "descripcion": 2,
        "unidad_medida": None, "cantidad": 8, "precio_unitario": 7,
    }
    fila = [None, None, None, "120MM2 DE", None, None, None, None, None]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=4, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is None


def test_construir_linea_catalogo_recupera_cabecera_desalineada_con_los_datos():
    # Hallazgo real de la sesión de filas fantasma (2026-09-04),
    # 6.24/28510.0187_ANEJO_1.pdf página 11: el modelo mapeó "descripción" a
    # la columna 4 y "precio_unitario" a la 13 porque ahí está el TEXTO de la
    # cabecera (centrado), pero los DATOS de esa misma tabla caen alineados a
    # la izquierda, una columna antes (3 y 12). El mapeo normal deja la línea
    # con descripción y precio vacíos pese a que la fila trae los dos datos
    # reales -- antes de esta sesión, esto se guardaba como fila fantasma
    # (o se habría descartado sin más con el filtro nuevo del punto 1). Debe
    # recuperarse desplazando el mapeo entero, nunca solo un campo, y debe
    # quedar marcada para que un humano la confirme.
    mapeo = {
        "codigo_precio": 1, "matricula": None, "descripcion": 4,
        "unidad_medida": 7, "cantidad": 10, "precio_unitario": 13,
    }
    fila = [
        "P01", None, None, "Tapa de canaleta prefabricada de hormigón\narmado", None, None,
        "dm3", None, None, "411000", None, None, "0,90 €", None, None,
    ]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=11, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["codigo_precio"] == "P01"
    assert linea["descripcion"] == "Tapa de canaleta prefabricada de hormigón armado"
    assert linea["unidad_medida"] == "dm3"
    assert linea["cantidad"] == Decimal("411000")
    assert linea["precio_unitario"] == Decimal("0.90")
    assert linea["motivo_revision"] is not None
    assert "desalineada" in linea["motivo_revision"]


def test_construir_linea_catalogo_recupera_partida_alzada_desalineada():
    # Segunda fila real del mismo documento (P02): sin cantidad, con la
    # descripción empezando literalmente por "Partida alzada" -- confirma
    # que la recuperación no confunde esto con el camino de
    # `_es_partida_alzada` (que solo actúa sobre la celda de matrícula) y
    # que una cantidad ausente en la posición desplazada no bloquea la
    # recuperación del precio.
    mapeo = {
        "codigo_precio": 1, "matricula": None, "descripcion": 4,
        "unidad_medida": 7, "cantidad": 10, "precio_unitario": 13,
    }
    fila = [
        "P02", None, None, "Partida alzada para suministro de tapas de canaleta singulares", None, None,
        None, None, None, None, None, None, "41.100,00\n€", None, None,
    ]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=11, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=1
    )

    assert linea is not None
    assert linea["matricula"] is None
    assert linea["cantidad"] is None
    assert linea["descripcion"] == "Partida alzada para suministro de tapas de canaleta singulares"
    assert linea["precio_unitario"] == Decimal("41100.00")
    assert linea["motivo_revision"] is not None


def test_construir_lineas_desde_tabla_filtra_pies_de_tabla():
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": None, "unidad_medida": None, "cantidad": None, "precio_unitario": 1}
    tabla = TablaExtraida(
        cabecera=["Matrícula", "Precio"],
        filas=[
            ["591000001", "554,00"],
            ["PRESUPUESTO DE LICITACIÓN", "55.400,00 €"],
            ["IVA", "11.634,00 €"],
            ["TOTAL CON IVA", "67.034,00 €"],
        ],
        pagina=13,
        bbox=(0.0, 0.0, 100.0, 100.0),
    )

    lineas = construir_lineas_desde_tabla(tabla, mapeo, None, expediente_id=1, baja_lote=None, orden_inicial=0)

    assert len(lineas) == 1
    assert lineas[0]["matricula"] == "591000001"


def test_clave_linea_cae_a_hash_de_descripcion_sin_codigo_ni_matricula():
    clave = calcular_clave_linea(None, None, "PARTIDA ALZADA", 3)
    assert clave != ""
    assert calcular_clave_linea(None, None, "PARTIDA ALZADA", 3) == clave
    assert calcular_clave_linea(None, None, "PARTIDA ALZADA", 4) != clave


def test_guardar_lineas_catalogo_primera_vez_crea(db_session):
    lote = _lote(db_session)
    lineas = [
        construir_linea_catalogo(
            ["P-001", "Guante", "24,00"],
            {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2},
            pagina=11,
            documento_origen_id=None,
            expediente_id=lote.expediente_id,
            baja_lote=None,
            orden_aparicion=0,
        )
    ]

    resultado = guardar_lineas_catalogo(db_session, lote.id, lineas)

    assert resultado.creadas == 1
    assert resultado.actualizadas == 0
    assert db_session.query(LineaCatalogo).count() == 1


def test_guardar_lineas_catalogo_no_hace_commit_el_llamador_decide(db_session):
    # CONTEXTO.md, sesión de rodaje 2026-09-03, punto 3: antes esta función
    # confirmaba por su cuenta, así que un documento con varias tablas podía
    # dejar guardado un grupo y fallar en el siguiente sin poder deshacer el
    # primero. Ahora es el llamador (`ejecutar_extraccion_expediente`) quien
    # decide cuándo confirmar — un rollback tras llamar a esta función debe
    # deshacer la línea igual que cualquier otro cambio pendiente de la
    # sesión.
    lote = _lote(db_session)
    lineas = [
        construir_linea_catalogo(
            ["P-001", "Guante", "24,00"],
            {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2},
            pagina=11,
            documento_origen_id=None,
            expediente_id=lote.expediente_id,
            baja_lote=None,
            orden_aparicion=0,
        )
    ]

    guardar_lineas_catalogo(db_session, lote.id, lineas)
    db_session.rollback()

    assert db_session.query(LineaCatalogo).count() == 0


def test_guardar_lineas_catalogo_reprocesar_no_duplica(db_session):
    # CONTEXTO.md sección 9.9: idempotencia. Reprocesar el mismo expediente
    # actualiza sus filas, nunca las duplica.
    lote = _lote(db_session)
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    fila = ["P-001", "Guante", "24,00"]
    lineas = [construir_linea_catalogo(fila, mapeo, 11, None, lote.expediente_id, None, 0)]

    guardar_lineas_catalogo(db_session, lote.id, lineas)
    resultado = guardar_lineas_catalogo(db_session, lote.id, lineas)

    assert resultado.creadas == 0
    assert resultado.actualizadas == 1
    assert db_session.query(LineaCatalogo).count() == 1


def test_guardar_lineas_catalogo_no_borra_campo_con_valor_nulo_entrante(db_session):
    # Caso real del fixture 6.24/28510.0088: el mismo código de precio
    # aparece en dos tablas del documento, una con cantidad y otra sin ella
    # (una tabla de "criterios técnicos" que repite código, descripción y
    # precio pero no trae cantidad). La segunda pasada no debe borrar la
    # cantidad que sí trajo la primera.
    lote = _lote(db_session)
    mapeo_con_cantidad = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": 2, "precio_unitario": 3}
    mapeo_sin_cantidad = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}

    primera = construir_linea_catalogo(["P-003", "Traviesa", "80000", "1,95"], mapeo_con_cantidad, 18, None, lote.expediente_id, None, 0)
    segunda = construir_linea_catalogo(["P-003", "Traviesa", "1,95"], mapeo_sin_cantidad, 23, None, lote.expediente_id, None, 0)

    guardar_lineas_catalogo(db_session, lote.id, [primera])
    guardar_lineas_catalogo(db_session, lote.id, [segunda])

    linea = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id, clave_linea="P-003").one()
    assert linea.cantidad == Decimal("80000")
    assert linea.pagina == 23  # la traza sí se actualiza a la pasada más reciente


def test_guardar_lineas_catalogo_invalidado_borra_codigo_precio_ya_guardado(db_session):
    # Bloque 3, sesión 2026-09-11 -- caso real: `6.20/28510.0042`/`0046`/
    # `0047` p.35, 33 líneas guardadas ANTES de `derivar_mapeo_por_contenido`
    # con `codigo_precio` igual a su propia matrícula (mapeo de modelo
    # equivocado sobre una tabla sin cabecera). Un `None` corriente nunca lo
    # habría corregido ("no pisa un valor ya conocido",
    # `test_guardar_lineas_catalogo_no_borra_campo_con_valor_nulo_entrante`
    # de arriba) -- `INVALIDADO` sí, porque la extracción SÍ miró la tabla y
    # determinó con confianza que no tiene columna de código de precio.
    lote = _lote(db_session)
    mapeo_viejo_equivocado = {
        "codigo_precio": 0, "matricula": None, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 2,
    }
    vieja = construir_linea_catalogo(
        ["612260110", "SCV-C-60-ID-318", "15.377,63"], mapeo_viejo_equivocado, 35, None, lote.expediente_id, None, 0
    )
    guardar_lineas_catalogo(db_session, lote.id, [vieja])
    linea = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id, clave_linea="612260110").one()
    assert linea.codigo_precio == "612260110"

    nueva = construir_linea_catalogo(
        ["612260110", "SCV-C-60-ID-318", "15.377,63"],
        {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2},
        35, None, lote.expediente_id, None, 0,
    )
    nueva["codigo_precio"] = INVALIDADO
    guardar_lineas_catalogo(db_session, lote.id, [nueva])

    db_session.refresh(linea)
    assert linea.codigo_precio is None
    assert linea.matricula == "612260110"


def test_guardar_lineas_catalogo_invalidado_en_fila_nueva_se_guarda_como_none(db_session):
    lote = _lote(db_session)
    mapeo = {
        "codigo_precio": None, "matricula": 0, "descripcion": 1,
        "unidad_medida": None, "cantidad": None, "precio_unitario": 2,
    }
    linea = construir_linea_catalogo(
        ["612260110", "SCV-C-60-ID-318", "15.377,63"], mapeo, 35, None, lote.expediente_id, None, 0
    )
    linea["codigo_precio"] = INVALIDADO

    guardar_lineas_catalogo(db_session, lote.id, [linea])

    guardada = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id, clave_linea="612260110").one()
    assert guardada.codigo_precio is None
    assert guardada.matricula == "612260110"


def test_guardar_lineas_catalogo_borra_precio_adjudicado_cuando_la_baja_deja_de_conocerse(db_session):
    # Hallazgo real, sesión de medición del alcance "Nº Lote: NNN"
    # (2026-09-08): a diferencia del resto de campos (`cantidad`,
    # `unidad_medida`...), `precio_adjudicado` es SIEMPRE derivado --
    # `precio_unitario * (1 - baja_lote)`, nunca leído del documento. Si una
    # pasada posterior determina que la baja ya no se puede derivar (p.ej.
    # se corrige de una baja global equivocada a "desconocida"), su
    # `precio_adjudicado` sale `None` en `datos`, y ese `None` SÍ debe
    # borrar el valor ya guardado -- no es "esta pasada no trajo el dato",
    # es "ya no se puede calcular". 336 líneas de `6.20/28510.0041` se
    # quedaron con el precio derivado de una baja ya inexistente porque
    # `guardar_lineas_catalogo` trataba este campo igual que cualquier otro.
    #
    # Mismo hueco encontrado de nuevo en `baja_lote` (bloque 3, cambios del
    # cliente tras revisar el catálogo): se copia de `lote.baja_lote`, que
    # `app.extraccion.orquestador` ya sobrescribe sin condición en cada
    # extracción -- reprocesar `6.20/28510.0041` con el extractor multi-lote
    # PCSP ya corregido dejaba `lotes.baja_lote` en blanco, pero el 97,73 %
    # de la baja contaminada del hermano seguía en cada línea del catálogo,
    # porque este mismo bucle tampoco borraba `baja_lote`.
    lote = _lote(db_session)
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}

    con_baja = construir_linea_catalogo(
        ["P-001", "Material X", "1000"], mapeo, 1, None, lote.expediente_id, Decimal("0.10"), 0
    )
    guardar_lineas_catalogo(db_session, lote.id, [con_baja])
    linea = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id, clave_linea="P-001").one()
    assert linea.precio_adjudicado == Decimal("900.0000")

    sin_baja = construir_linea_catalogo(
        ["P-001", "Material X", "1000"], mapeo, 1, None, lote.expediente_id, None, 0
    )
    guardar_lineas_catalogo(db_session, lote.id, [sin_baja])

    # `existente` dentro de `guardar_lineas_catalogo` es el mismo objeto que
    # `linea` (identity map de SQLAlchemy) -- se comprueba directo, sin
    # `refresh()`: sin un `commit()` de por medio, `refresh()` descartaría
    # el cambio todavía pendiente y volvería a leer el valor viejo de la
    # base de datos real.
    assert linea.precio_adjudicado is None
    assert linea.baja_lote is None
    assert linea.precio_unitario == Decimal("1000")  # el resto de campos sigue intacto


def test_guardar_lineas_catalogo_limpia_motivo_revision_cuando_la_pasada_nueva_no_encuentra_nada(db_session):
    # Bloque 2, sesión de comparación documento-vs-listado interno: cuarta
    # aparición del mismo defecto que `precio_adjudicado`/`baja_lote`
    # (`test_guardar_lineas_catalogo_borra_precio_adjudicado_cuando_la_baja_
    # deja_de_conocerse`, arriba) y que motivó el estado `INVALIDADO`.
    # `_construir_campos` recalcula `motivo_revision` de cero en cada
    # llamada -- un `None` en una pasada posterior significa "ya no hay
    # motivo", nunca "no se evaluó", y debe limpiar el aviso viejo.
    lote = _lote(db_session)
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": 2, "precio_unitario": 3}

    con_motivo = construir_linea_catalogo(
        ["P-001", "Material X", "no-es-un-numero", "24,00"], mapeo, 1, None, lote.expediente_id, None, 0
    )
    guardar_lineas_catalogo(db_session, lote.id, [con_motivo])
    linea = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id, clave_linea="P-001").one()
    assert linea.motivo_revision is not None
    assert "cantidad no interpretable" in linea.motivo_revision

    sin_motivo = construir_linea_catalogo(
        ["P-001", "Material X", "30", "24,00"], mapeo, 1, None, lote.expediente_id, None, 0
    )
    guardar_lineas_catalogo(db_session, lote.id, [sin_motivo])

    # Mismo objeto (identity map de SQLAlchemy), sin `commit()` de por
    # medio -- comprobado directo, igual que el test de `precio_adjudicado`.
    assert linea.motivo_revision is None
    assert linea.cantidad == Decimal("30")  # el resto de campos sigue actualizándose con normalidad


def test_combinar_por_clave_funde_repeticiones_dentro_del_mismo_lote_de_lineas():
    # Bug real (sesión de validación del mapeo de cabecera contra la API):
    # SessionLocal (app/db.py) usa autoflush=False, así que un mismo
    # clave_linea repetido más de una vez dentro de un único `lineas` (el
    # mismo cuadro de precios reaparece en el documento — CONTEXTO.md sección
    # 3) llegaba sin fundir hasta el INSERT final y violaba la constraint
    # UNIQUE de golpe, tirando el trabajo entero. `_combinar_por_clave` debe
    # resolverlo en Python, sin depender de autoflush.
    primera = {"clave_linea": "P-003", "cantidad": Decimal("80000"), "precio_unitario": None, "pagina": 18}
    segunda = {"clave_linea": "P-003", "cantidad": None, "precio_unitario": Decimal("1.95"), "pagina": 23}
    otra = {"clave_linea": "P-004", "cantidad": Decimal("10"), "precio_unitario": Decimal("5.00"), "pagina": 18}

    combinadas = _combinar_por_clave([primera, segunda, otra])

    assert len(combinadas) == 2
    p003 = next(c for c in combinadas if c["clave_linea"] == "P-003")
    assert p003["cantidad"] == Decimal("80000")  # el None de `segunda` no borra el valor de `primera`
    assert p003["precio_unitario"] == Decimal("1.95")
    assert p003["pagina"] == 23  # el campo si presente en ambas se queda con el más reciente


def test_guardar_lineas_catalogo_funde_clave_repetida_en_un_solo_lote(db_session):
    lote = _lote(db_session)
    mapeo_con_cantidad = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": 2, "precio_unitario": 3}
    mapeo_sin_cantidad = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    primera = construir_linea_catalogo(["P-003", "Traviesa", "80000", "1,95"], mapeo_con_cantidad, 18, None, lote.expediente_id, None, 0)
    segunda = construir_linea_catalogo(["P-003", "Traviesa", "1,95"], mapeo_sin_cantidad, 23, None, lote.expediente_id, None, 1)

    resultado = guardar_lineas_catalogo(db_session, lote.id, [primera, segunda])

    assert resultado.creadas == 1
    assert resultado.actualizadas == 0
    linea = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id, clave_linea="P-003").one()
    assert linea.cantidad == Decimal("80000")


def test_guardar_lineas_catalogo_huerfana_sin_lote_no_se_duplica_al_reprocesar(db_session):
    # CONTEXTO.md, encargo de esta sesión, punto 3 (ajuste 1 del usuario): una
    # línea cuya tabla de origen no se pudo asociar a un lote sin ambigüedad
    # se guarda con lote_id=None, no con un lote centinela. La idempotencia
    # de esas huérfanas la garantiza el filtro por expediente_id + lote_id
    # IS NULL, no la constraint UNIQUE (que no deduplica NULLs).
    lote = _lote(db_session)
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    fila = ["P-009", "Balasto", "10,00"]
    lineas = [construir_linea_catalogo(fila, mapeo, 22, None, lote.expediente_id, None, 0)]

    r1 = guardar_lineas_catalogo(db_session, None, lineas)
    r2 = guardar_lineas_catalogo(db_session, None, lineas)

    assert r1.creadas == 1
    assert r2.creadas == 0 and r2.actualizadas == 1
    huerfanas = db_session.query(LineaCatalogo).filter_by(lote_id=None, expediente_id=lote.expediente_id).all()
    assert len(huerfanas) == 1


# --- Bloque 4, sesión de huérfanos de banda vacía (2026-09-07): señal
# informativa de "posible duplicado" en la cola de revisión, nunca una
# decisión automática (ver docstring de `buscar_posible_duplicado_huerfana`
# para el caso real de balasto multi-lote que descartó el descarte automático).


def test_buscar_posible_duplicado_huerfana_encuentra_coincidencia_por_firma(db_session):
    lote = _lote(db_session)
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": None, "cantidad": None, "precio_unitario": 3}
    resuelta = construir_linea_catalogo(
        ["P-1", "601020180", "Balasto sobre camion en cantera", "10,85"], mapeo, 22, None, lote.expediente_id, None, 0
    )
    guardar_lineas_catalogo(db_session, lote.id, [resuelta])
    db_session.commit()

    huerfana_datos = construir_linea_catalogo(
        ["P-1", "601020180", "Balasto sobre camion en cantera", "10,85"], mapeo, 24, None, lote.expediente_id, None, 0
    )
    guardar_lineas_catalogo(db_session, None, [huerfana_datos])
    huerfana = db_session.query(LineaCatalogo).filter_by(lote_id=None, expediente_id=lote.expediente_id).one()

    resultado = buscar_posible_duplicado_huerfana(db_session, huerfana)

    assert resultado is not None
    linea_resuelta, lote_resuelto = resultado
    assert linea_resuelta.codigo_precio == "P-1"
    assert lote_resuelto.identificador_lote == lote.identificador_lote


def test_buscar_posible_duplicado_huerfana_ninguna_coincidencia_devuelve_none(db_session):
    # Caso real que motivó no descartar automáticamente (6.25/28510.0027):
    # una huérfana con precio DISTINTO del de la línea resuelta (el
    # transporte varía por lote, aunque la carga en cantera no) no es un
    # posible duplicado.
    lote = _lote(db_session)
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    resuelta = construir_linea_catalogo(
        ["P-2", "T de balasto transportado", "21,56"], mapeo, 23, None, lote.expediente_id, None, 0
    )
    guardar_lineas_catalogo(db_session, lote.id, [resuelta])
    db_session.commit()

    huerfana_datos = construir_linea_catalogo(
        ["P-2", "T de balasto transportado", "12,32"], mapeo, 24, None, lote.expediente_id, None, 0
    )
    guardar_lineas_catalogo(db_session, None, [huerfana_datos])
    huerfana = db_session.query(LineaCatalogo).filter_by(lote_id=None, expediente_id=lote.expediente_id).one()

    assert buscar_posible_duplicado_huerfana(db_session, huerfana) is None


def test_buscar_posible_duplicado_huerfana_no_aplica_a_linea_con_lote(db_session):
    lote = _lote(db_session)
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    datos = construir_linea_catalogo(["P-1", "Balasto", "10,85"], mapeo, 22, None, lote.expediente_id, None, 0)
    guardar_lineas_catalogo(db_session, lote.id, [datos])
    linea = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id).one()

    assert buscar_posible_duplicado_huerfana(db_session, linea) is None


# --- Inventario de celdas vacías (2026-09-06, bloque 3): cantidad recuperada
# de una columna fantasma en la cabecera --- (docs/inventario-celdas-vacias.md)


def test_construir_linea_catalogo_recupera_cantidad_de_columna_fantasma():
    # Expediente real 6.25/28510.0019, ANEJO_1 página 28 (verificado con
    # pdfplumber directamente sobre el PDF real, no solo con el dato ya
    # guardado): la cabecera es ["CÓDIGO DEL PRECIO", "Nº MATRÍCULA",
    # "DESCRIPCIÓN", "UNIDAD DE MEDIDA", None, "CANTIDADES ESTIMADAS DE
    # REFERENCIA", "PRECIO DE REFERENCIA"] -- el mapeo determinista ata
    # "cantidad" a la columna 5 (la que trae ese texto), pero en TODAS las
    # filas de datos de esta tabla el número real cae en la columna 4
    # (fantasma sin etiquetar en la cabecera), y la 5 sale siempre vacía.
    mapeo = {
        "codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3,
        "cantidad": 5, "precio_unitario": 6,
    }
    fila = ["P-431", "", "Tirante TI-22-D-AT1", "UN", "10", None, "3.270,00 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=28, documento_origen_id=170, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["cantidad"] == Decimal("10")
    assert linea["precio_unitario"] == Decimal("3270.00")
    assert linea["motivo_revision"] is not None
    assert "cantidad recuperada" in linea["motivo_revision"]


def test_la_partida_alzada_con_un_solo_importe_no_lo_toma_como_cantidad():
    # Sesión 2026-09-21, bloque 1: `6.25/28510.0019` CONTRATO_2 p.118, misma
    # cabecera que el test de arriba. La fila P-323 trae UN solo importe,
    # "116.000,00 €", en la columna fantasma de la cantidad (la 4), y la
    # recuperación de precio también lo alcanzaba: 116.000 × 116.000.
    mapeo = {
        "codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3,
        "cantidad": 5, "precio_unitario": 6,
    }
    fila = ["P-323", "Partida alzada a justificar para imprevistos", None, None, "116.000,00 €", None, None]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=118, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea["cantidad"] is None
    assert linea["precio_unitario"] == Decimal("116000.00")


def test_el_importe_con_euro_en_la_columna_fantasma_de_cantidad_es_el_precio_si_no_hay_otro():
    # `6.21/28510.0003` PLIEGO p.5: la partida alzada de repuestos salía con
    # 42.948,65 de cantidad y sin precio.
    mapeo = {
        "codigo_precio": None, "matricula": None, "descripcion": 0, "unidad_medida": None,
        "cantidad": 5, "precio_unitario": 8,
    }
    fila = ["Partida alzada a justificar de repuestos", None, None, None, None, None, "42.948,65 €", None, None]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=5, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea["cantidad"] is None
    assert linea["precio_unitario"] == Decimal("42948.65")


def test_construir_linea_catalogo_no_recupera_cantidad_si_la_columna_anterior_no_es_numerica():
    # La columna anterior a "cantidad" puede ser una matrícula vacía de
    # verdad, no una columna fantasma con el número desplazado -- no se
    # inventa una cantidad de una celda que no parece serlo.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": None, "cantidad": 1, "precio_unitario": 3}
    fila = ["P-001", "", "Balasto", "24,00"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=1, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["cantidad"] is None


def test_construir_linea_catalogo_no_recupera_cantidad_si_la_cabecera_no_declara_ese_campo():
    # Sin columna de cantidad en el mapeo (la cabecera de esta tabla no la
    # trae en absoluto, distinto del caso de arriba), no hay nada que
    # recuperar -- sigue siendo un hueco "no consta", no un fallo.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": None, "precio_unitario": 4}
    fila = ["P-001", "", "Balasto", "UN", "24,00"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=1, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["cantidad"] is None


def test_construir_linea_catalogo_recupera_precio_unitario_de_columna_fantasma():
    # Expediente real 6.23/28510.0051, CONTRATO_1 página 112 (verificado con
    # pdfplumber sobre el PDF real): mismo fenómeno que la cantidad de
    # arriba, pero con la columna fantasma al otro lado -- la cabecera es
    # ["CÓDIGO DEL ELEMENTO", "Nº MATRÍCULA", "DESCRIPCIÓN", "UNIDAD DE
    # MEDIDA", "CANTIDADES ESTIMADAS DE REFERENCIA", None, "PRECIO UNITARIO
    # DE REFERENCIA"] -- "precio_unitario" queda atado a la columna 6, pero
    # en las filas de datos el importe real cae en la 5 (fantasma), y la 6
    # sale siempre vacía.
    mapeo = {
        "codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3,
        "cantidad": 4, "precio_unitario": 6,
    }
    fila = ["P-0014", "619260075", "DIMDH-G-60-500-0,071-CR-TC-D", "UD.", "0", "259.439,64 €", None]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=112, documento_origen_id=39, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["cantidad"] == Decimal("0")
    assert linea["precio_unitario"] == Decimal("259439.64")
    assert linea["motivo_revision"] is not None
    assert "precio unitario recuperado" in linea["motivo_revision"]


def test_construir_linea_catalogo_no_recupera_precio_unitario_si_ninguna_columna_vecina_es_numerica():
    # Los dos vecinos de "precio_unitario" (descripción a la izquierda, nada
    # a la derecha) ya están en uso o no existen -- no se inventa un precio.
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    fila = ["P-001", "Balasto", ""]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=1, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["precio_unitario"] is None


def test_guardar_lineas_catalogo_huerfana_con_clave_sufijada_no_se_duplica_al_reprocesar(db_session):
    # Auditoría 2026-09-05 (docs/correccion-defectos-auditoria.md): una
    # huérfana real trae `clave_linea` con el sufijo de página/franja que
    # añade `app.extraccion.pipeline_anejo` (p.ej. "P-094@p24y198"), no el
    # `codigo_precio` desnudo -- a diferencia de
    # `test_guardar_lineas_catalogo_huerfana_sin_lote_no_se_duplica_al_reprocesar`,
    # que sin querer no ejercitaba el bug porque su clave ya coincidía con
    # su propio `codigo_precio`. Antes del guard de `fusion_material` en
    # `guardar_lineas_catalogo`, el segundo guardado "canonicalizaba" la
    # clave de vuelta a "P-094" -- el tercer reproceso, que vuelve a
    # calcular la clave CON sufijo (como haría `pipeline_anejo` de nuevo
    # sobre el mismo documento), ya no encontraba la fila y creaba otra.
    lote = _lote(db_session)
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    fila = ["P-094", "Traviesa", "10,00"]

    def _linea_con_sufijo():
        linea = construir_linea_catalogo(fila, mapeo, 24, None, lote.expediente_id, None, 0)
        linea["clave_linea"] = f"{linea['clave_linea']}@p24y198"
        return linea

    r1 = guardar_lineas_catalogo(db_session, None, [_linea_con_sufijo()])
    r2 = guardar_lineas_catalogo(db_session, None, [_linea_con_sufijo()])
    r3 = guardar_lineas_catalogo(db_session, None, [_linea_con_sufijo()])

    assert (r1.creadas, r2.creadas, r3.creadas) == (1, 0, 0)
    huerfanas = db_session.query(LineaCatalogo).filter_by(lote_id=None, expediente_id=lote.expediente_id).all()
    assert len(huerfanas) == 1
    assert huerfanas[0].clave_linea == "P-094@p24y198"


def test_guardar_lineas_catalogo_limpia_huerfana_superada_por_herencia_de_lote(db_session):
    # Sesión de herencia de lote entre páginas de continuación (2026-09-08):
    # una línea que se guardó como huérfana en un reproceso anterior
    # ("P-094@p24y198") y ahora resuelve a un lote real ("P-094" a secas)
    # tiene que sustituir a la huérfana vieja, no duplicarla -- el hallazgo
    # real que motivó este arreglo (2.152 filas así en los primeros
    # expedientes verificados). `clave_huerfana_hipotetica` es la clave
    # exacta que la línea resuelta habría tenido de haberse quedado
    # huérfana (la calcula `app.extraccion.pipeline_anejo` para toda línea,
    # resuelva o no) -- comparación exacta, nunca por contenido.
    lote = _lote(db_session)
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    fila = ["P-094", "Traviesa", "10,00"]

    huerfana = construir_linea_catalogo(fila, mapeo, 24, None, lote.expediente_id, None, 0)
    huerfana["clave_linea"] = "P-094@p24y198"
    guardar_lineas_catalogo(db_session, None, [huerfana])
    assert db_session.query(LineaCatalogo).filter_by(lote_id=None, expediente_id=lote.expediente_id).count() == 1

    resuelta = construir_linea_catalogo(fila, mapeo, 24, None, lote.expediente_id, Decimal("0.10"), 0)
    resuelta["clave_huerfana_hipotetica"] = "P-094@p24y198"
    guardado = guardar_lineas_catalogo(db_session, lote.id, [resuelta])

    assert guardado.creadas == 1
    todas = db_session.query(LineaCatalogo).filter_by(expediente_id=lote.expediente_id).all()
    assert len(todas) == 1
    assert todas[0].lote_id == lote.id
    assert todas[0].clave_linea == "P-094"


def test_guardar_lineas_catalogo_no_borra_huerfana_con_precio_coincidente_de_otra_tabla(db_session):
    # Guard de seguridad (caso real del balasto, `6.25/28510.0027`): un
    # precio de referencia puede repetirse igual entre tablas de LOTES
    # DISTINTOS de la misma página ("P-1 Balasto..." a 10,85 € en varios
    # lotes) -- la huérfana de un lote no declarado no se borra solo
    # porque otro lote, ya resuelto, tenga una línea con el mismo código,
    # descripción y precio. Solo se borra con una clave EXACTAMENTE igual
    # a `clave_huerfana_hipotetica` (misma franja vertical de la misma
    # tabla) -- aquí la huérfana viene de una tabla distinta ("y198" frente
    # a "y50" de la resuelta), así que sobrevive.
    lote = _lote(db_session)
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    fila = ["P-1", "Balasto sobre camión en cantera", "10,85"]

    huerfana = construir_linea_catalogo(fila, mapeo, 24, None, lote.expediente_id, None, 0)
    huerfana["clave_linea"] = "P-1@p24y198"
    guardar_lineas_catalogo(db_session, None, [huerfana])

    resuelta = construir_linea_catalogo(fila, mapeo, 24, None, lote.expediente_id, Decimal("0.10"), 0)
    resuelta["clave_huerfana_hipotetica"] = "P-1@p24y50"  # otra tabla, otra franja
    guardar_lineas_catalogo(db_session, lote.id, [resuelta])

    huerfanas = db_session.query(LineaCatalogo).filter_by(lote_id=None, expediente_id=lote.expediente_id).all()
    assert len(huerfanas) == 1
    assert huerfanas[0].clave_linea == "P-1@p24y198"
    assert db_session.query(LineaCatalogo).filter_by(lote_id=lote.id).count() == 1


def test_construir_lineas_desde_tabla_usa_orden_inicial():
    tabla = TablaExtraida(
        cabecera=["Código", "Descripción", "Precio"],
        filas=[["P-001", "A", "1,00"], ["P-002", "B", "2,00"]],
        pagina=1,
        bbox=(0.0, 0.0, 100.0, 50.0),
    )
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}

    lineas = construir_lineas_desde_tabla(tabla, mapeo, None, 1, None, orden_inicial=5)

    assert [l["orden_aparicion"] for l in lineas] == [5, 6]


# --- Auditoría 2026-09-05: codigo_precio corrupto por pie de página CSV ---
# (docs/correccion-defectos-auditoria.md, encargo de esta sesión punto 1)


def test_normalizar_codigo_precio_formato_conocido_pasa_sin_motivo():
    assert _normalizar_codigo_precio("P-001") == ("P-001", None)
    assert _normalizar_codigo_precio("PN09") == ("PN09", None)
    assert _normalizar_codigo_precio("P01") == ("P01", None)


def test_normalizar_codigo_precio_prefijo_cod_pasa_sin_motivo():
    # Bloque 3, sesión de expedientes en revisión por trabajo pendiente real
    # (2026-09-07): 4.26/28510.0020, "Cod0001".."Cod0305" — sexto formato real
    # de codigo_precio, ausente hasta esta sesión de ambos regex de esta capa
    # (`app.extraccion.tabla` ya lo acepta antes de llegar aquí).
    assert _normalizar_codigo_precio("Cod0001") == ("Cod0001", None)
    assert _normalizar_codigo_precio("Cod0305") == ("Cod0305", None)


def test_normalizar_codigo_precio_numero_suelto_bajo_cabecera_partida():
    # Caso real, 6.26/28510.0016 (sesión de trabajo pendiente real,
    # 2026-09-05): la cabecera de la tabla dice literalmente "PARTIDA", no
    # "Código de precio" -- 41 filas numeradas 1..41 sin ningún prefijo de
    # letra, verificadas únicas dentro del lote.
    assert _normalizar_codigo_precio("1") == ("1", None)
    assert _normalizar_codigo_precio("41") == ("41", None)


def test_normalizar_codigo_precio_recupera_pie_de_pagina_csv_al_final():
    # Caso real, 6.24/28510.0180 (uno de los 7 `completado`): el pie de
    # verificación CSV invertido queda pegado delante del código.
    codigo, motivo = _normalizar_codigo_precio("j.adilav/vscPN005")

    assert codigo == "PN005"
    assert motivo is not None
    assert "recuperado" in motivo


def test_normalizar_codigo_precio_recupera_pie_de_pagina_csv_partido_alrededor():
    # Caso real, 6.23/28510.0042: el ruido puede caer a ambos lados del
    # código real, no solo delante.
    codigo, motivo = _normalizar_codigo_precio("hneP-015elbac")

    assert codigo == "P-015"
    assert "recuperado" in motivo


def test_normalizar_codigo_precio_descarta_ruido_sin_codigo_recuperable():
    # Ninguna coincidencia de formato conocido dentro de la cadena: es puro
    # ruido de pie de página, sin ningún código que aislar.
    codigo, motivo = _normalizar_codigo_precio("psj.adilav/vsc")

    assert codigo is None
    assert motivo is not None
    assert "descartado" in motivo


def test_normalizar_codigo_precio_no_funde_sufijo_de_una_letra_con_el_codigo_base():
    # Hallazgo real, 6.24/28510.0185: "P-001b".."P-021b" son códigos
    # DISTINTOS de "P-001".."P-021" -- mismo material, precio distinto (dos
    # tablas de precios reales del documento), no ruido de pie de página.
    # Con solo 1 carácter de cola no hay evidencia suficiente para tratarlo
    # como el mismo ruido de las URLs invertidas (siempre 2+ caracteres en
    # el corpus real) -- se conserva tal cual, sin fundirlo con "P-001".
    codigo, motivo = _normalizar_codigo_precio("P-001b")

    assert codigo == "P-001b"
    assert motivo is not None
    assert "no reconocido" in motivo


def test_normalizar_codigo_precio_formato_no_reconocido_no_se_guarda_en_silencio():
    # Comprobación general del encargo (punto 1): un valor que no es ruido
    # de pie de página conocido pero tampoco encaja en ningún formato
    # catalogado se conserva (podría ser legítimo) pero siempre con motivo.
    codigo, motivo = _normalizar_codigo_precio("X-9912")

    assert codigo == "X-9912"
    assert motivo is not None
    assert "no reconocido" in motivo


def test_construir_linea_catalogo_recupera_codigo_precio_corrupto():
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": None, "cantidad": None, "precio_unitario": 3}
    fila = ["j.adilav/vscPN005", "", "m² cartelón de indicación de estación", "421,79 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=1, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea["codigo_precio"] == "PN005"
    assert linea["clave_linea"] == "PN005"
    assert linea["motivo_revision"] is not None
    assert "recuperado" in linea["motivo_revision"]


def test_construir_linea_catalogo_codigo_precio_irrecuperable_no_pierde_el_resto_de_la_linea():
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": None, "cantidad": None, "precio_unitario": 3}
    fila = ["psj.adilav/vsc", "643470030", "PAT 3 MORDAZA PUESTA A TIERRA", "112,25 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=1, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["codigo_precio"] is None
    assert linea["matricula"] == "643470030"
    assert linea["precio_unitario"] == Decimal("112.25")
    assert linea["clave_linea"] == "643470030"  # cae a la matrícula, no se pierde la línea
    assert "descartado" in linea["motivo_revision"]


# --- Auditoría 2026-09-05: líneas duplicadas por segunda tabla técnica sin
# codigo_precio propio (docs/correccion-defectos-auditoria.md, encargo de
# esta sesión punto 2) ---


def test_combinar_por_clave_funde_por_firma_de_material_entre_claves_distintas():
    # Caso real, 6.23/28510.0018 lote 1, matrícula 601020180: la tabla de la
    # página 12 trae codigo_precio ("P-02"), la de la página 16 repite el
    # mismo material y precio sin código -- antes de esta sesión,
    # `calcular_clave_linea` les daba claves distintas (codigo_precio vs.
    # matrícula) y quedaban como dos líneas de catálogo para el mismo
    # material real.
    con_codigo = {
        "clave_linea": "P-02", "matricula": "601020180", "descripcion": "CARRIL RN 45 BARRA 180 M.",
        "codigo_precio": "P-02", "precio_unitario": Decimal("58.43"), "pagina": 12,
    }
    sin_codigo = {
        "clave_linea": "601020180", "matricula": "601020180", "descripcion": "CARRIL RN 45 BARRA 180 M.",
        "codigo_precio": None, "precio_unitario": Decimal("58.43"), "pagina": 16,
    }

    combinadas = _combinar_por_clave([con_codigo, sin_codigo])

    assert len(combinadas) == 1
    assert combinadas[0]["clave_linea"] == "P-02"
    assert combinadas[0]["codigo_precio"] == "P-02"
    assert combinadas[0]["pagina"] == 16  # el resto de campos se funde igual que siempre


def test_combinar_por_clave_no_funde_por_firma_material_en_huerfanas():
    # `permitir_fusion_material=False` es lo que usa `guardar_lineas_catalogo`
    # para lote_id=None: dos huérfanas de lotes distintos pueden compartir
    # matrícula+descripción+precio (mismo material de catálogo, ofertado en
    # dos lotes de un acuerdo marco) y deben seguir siendo dos líneas.
    huerfana_1 = {
        "clave_linea": "P-1@p3y100", "matricula": "601020180", "descripcion": "MATERIAL X",
        "codigo_precio": "P-1", "precio_unitario": Decimal("10.00"),
    }
    huerfana_2 = {
        "clave_linea": "P-1@p5y100", "matricula": "601020180", "descripcion": "MATERIAL X",
        "codigo_precio": "P-1", "precio_unitario": Decimal("10.00"),
    }

    combinadas = _combinar_por_clave([huerfana_1, huerfana_2], permitir_fusion_material=False)

    assert len(combinadas) == 2


def test_combinar_por_clave_no_funde_dos_codigos_propios_de_la_misma_pagina_por_firma():
    # Caso real, 6.22/28510.0125 / 0126 / 0094 (las tres comparten el mismo
    # CONTRATO, que reproduce el cuadro de precios completo dos veces, una
    # por lote NORTE/SUR). P-133 (matrícula 611050081) y P-137 (matrícula
    # 611050121) son dos materiales reales y distintos que además comparten
    # descripción y precio en el documento -- coincidencia legítima del
    # catálogo. En la copia de la página 126 la extracción pierde la
    # matrícula de las dos filas (queda `None`), así que su firma se vuelve
    # indistinguible entre ellas para esa página. Sin el guard de página en
    # conflicto, `_combinar_por_clave` fundía la segunda bajo la clave de la
    # primera y el bucle de fusión, que copia campo a campo, dejaba su
    # propio `codigo_precio` pisando el de la fila ganadora --
    # `clave_linea="P-133"` con `codigo_precio="P-137"`, un choque directo
    # con `uq_linea_lote_clave` en cuanto la fila se guardaba de verdad.
    p133_pagina120 = {
        "clave_linea": "P-133", "matricula": "611050081", "descripcion": "",
        "codigo_precio": "P-133", "precio_unitario": Decimal("241039.59"), "pagina": 120,
    }
    p137_pagina120 = {
        "clave_linea": "P-137", "matricula": "611050121", "descripcion": "",
        "codigo_precio": "P-137", "precio_unitario": Decimal("241039.59"), "pagina": 120,
    }
    p133_pagina126 = {
        "clave_linea": "P-133", "matricula": None, "descripcion": "ES-B1-54-320-1:8,5-CC-I-3.808",
        "codigo_precio": "P-133", "precio_unitario": Decimal("241039.59"), "pagina": 126,
    }
    p137_pagina126 = {
        "clave_linea": "P-137", "matricula": None, "descripcion": "ES-B1-54-320-1:8,5-CC-I-3.808",
        "codigo_precio": "P-137", "precio_unitario": Decimal("241039.59"), "pagina": 126,
    }

    combinadas = _combinar_por_clave([p133_pagina120, p137_pagina120, p133_pagina126, p137_pagina126])

    por_codigo = {l["codigo_precio"]: l for l in combinadas}
    assert set(por_codigo) == {"P-133", "P-137"}
    # Cada fila conserva su propia clave (nunca roba la de la otra) y se
    # completa igual con el campo que trajo la copia de la otra página.
    assert por_codigo["P-133"]["clave_linea"] == "P-133"
    assert por_codigo["P-133"]["matricula"] == "611050081"
    assert por_codigo["P-133"]["descripcion"] == "ES-B1-54-320-1:8,5-CC-I-3.808"
    assert por_codigo["P-137"]["clave_linea"] == "P-137"
    assert por_codigo["P-137"]["matricula"] == "611050121"
    assert por_codigo["P-137"]["descripcion"] == "ES-B1-54-320-1:8,5-CC-I-3.808"


def test_guardar_lineas_catalogo_funde_material_repetido_entre_documentos_distintos(db_session):
    # Caso real, 6.23/28510.0102 y 6.25/28510.0016: la tabla sin código vive
    # en un documento (ANEJO_3) y la que sí trae codigo_precio en otro
    # (ANEJO_1) -- dos llamadas a `guardar_lineas_catalogo` completamente
    # distintas, `_combinar_por_clave` en memoria nunca las ve juntas.
    lote = _lote(db_session)
    mapeo_sin_codigo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    mapeo_con_codigo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": None, "cantidad": None, "precio_unitario": 3}

    de_anejo_3 = construir_linea_catalogo(
        ["601020180", "CARRIL RN 45 BARRA 180 M.", "58,43"], mapeo_sin_codigo, 3, None, lote.expediente_id, None, 0
    )
    de_anejo_1 = construir_linea_catalogo(
        ["P-02", "601020180", "CARRIL RN 45 BARRA 180 M.", "58,43"], mapeo_con_codigo, 12, None, lote.expediente_id, None, 0
    )

    r1 = guardar_lineas_catalogo(db_session, lote.id, [de_anejo_3])
    db_session.commit()
    r2 = guardar_lineas_catalogo(db_session, lote.id, [de_anejo_1])
    db_session.commit()

    assert r1.creadas == 1
    assert r2.creadas == 0 and r2.actualizadas == 1
    lineas = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id, matricula="601020180").all()
    assert len(lineas) == 1
    assert lineas[0].clave_linea == "P-02"  # la clave sube a la canónica al conocerse el código
    assert lineas[0].codigo_precio == "P-02"


def test_guardar_lineas_catalogo_absorbe_duplicado_heredado_al_subir_la_clave(db_session):
    # Hallazgo real, 6.24/28510.0116, lote 25, "P-01": un duplicado ya
    # guardado en el catálogo ANTES de existir la fusión por firma de
    # material (dos filas, una con clave de matrícula y otra con clave
    # "P-01", igual que el escenario de `_firma_material`, pero de una
    # sesión anterior). Al reprocesar, la fila sin código sube su clave a
    # "P-01" al fundirse con la extracción nueva -- pero esa clave YA
    # pertenece a la otra fila heredada. Debe absorberla, no reventar la
    # constraint UNIQUE.
    lote = _lote(db_session)
    sin_codigo = LineaCatalogo(
        lote_id=lote.id, expediente_id=lote.expediente_id, clave_linea="645750101", orden_aparicion=0,
        matricula="645750101", descripcion="DISPOSITIVO LIMITADOR TENSIÓN TIPO VLD-F", cantidad=Decimal("900"),
        precio_unitario=Decimal("1485.00"), pagina=18,
    )
    con_codigo = LineaCatalogo(
        lote_id=lote.id, expediente_id=lote.expediente_id, clave_linea="P-01", orden_aparicion=1,
        codigo_precio="P-01", matricula="645750101", descripcion="DISPOSITIVO LIMITADOR TENSIÓN TIPO VLD-F",
        precio_unitario=Decimal("1485.00"), pagina=22,
    )
    db_session.add_all([sin_codigo, con_codigo])
    db_session.commit()

    # La extracción fresca reproduce las dos tablas reales del mismo
    # documento (página 18 sin código, página 22 con "P-01") — igual que en
    # producción, `_combinar_por_clave` las funde en un único `datos` antes
    # de llegar a `guardar_lineas_catalogo`.
    mapeo_sin_codigo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": None, "cantidad": 2, "precio_unitario": 3}
    mapeo_con_codigo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": None, "cantidad": None, "precio_unitario": 3}
    de_pagina_18 = construir_linea_catalogo(
        ["645750101", "DISPOSITIVO LIMITADOR TENSIÓN TIPO VLD-F", "900", "1.485,00"],
        mapeo_sin_codigo, 18, None, lote.expediente_id, None, 0,
    )
    de_pagina_22 = construir_linea_catalogo(
        ["P-01", "645750101", "DISPOSITIVO LIMITADOR TENSIÓN TIPO VLD-F", "1.485,00"],
        mapeo_con_codigo, 22, None, lote.expediente_id, None, 1,
    )

    resultado = guardar_lineas_catalogo(db_session, lote.id, [de_pagina_18, de_pagina_22])

    assert resultado.creadas == 0
    assert resultado.actualizadas == 1
    lineas = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id, matricula="645750101").all()
    assert len(lineas) == 1
    assert lineas[0].clave_linea == "P-01"
    assert lineas[0].cantidad == Decimal("900")  # se conserva el dato que solo tenía la fila absorbida


def test_guardar_lineas_catalogo_absorbe_las_dos_filas_heredadas_cuando_la_clave_exacta_no_encuentra_ninguna(db_session):
    # Hallazgo real, 6.23/28510.0042, matrícula 643480020: TRES filas
    # heredadas de antes de este arreglo para la misma pieza física (una ya
    # con la clave limpia, dos con ruido de pie de página sin recuperar
    # entonces). Cuando la búsqueda por clave exacta de la fila recién
    # extraída no encuentra NINGUNA de ellas (ninguna coincide todavía con
    # la clave limpia), la búsqueda por firma debe encontrarlas TODAS, no
    # solo la primera por id -- quedarse con `.first()` antes de saber que
    # la exacta había fallado dejaba la segunda sin absorber nunca.
    lote = _lote(db_session)
    heredada_1 = LineaCatalogo(
        lote_id=lote.id, expediente_id=lote.expediente_id, clave_linea="RUIDO-VIEJO-1", orden_aparicion=0,
        codigo_precio="RUIDO-VIEJO-1", matricula="643480020", descripcion="VAT-1 PÉRTIGA", pagina=10,
        precio_unitario=Decimal("2365.67"),
    )
    heredada_2 = LineaCatalogo(
        lote_id=lote.id, expediente_id=lote.expediente_id, clave_linea="RUIDO-VIEJO-2", orden_aparicion=1,
        codigo_precio="RUIDO-VIEJO-2", matricula="643480020", descripcion="VAT-1 PÉRTIGA", pagina=105,
        precio_unitario=Decimal("2365.67"), cantidad=Decimal("14"),
    )
    db_session.add_all([heredada_1, heredada_2])
    db_session.commit()

    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": None, "cantidad": None, "precio_unitario": 3}
    reextraida = construir_linea_catalogo(
        ["P-012", "643480020", "VAT-1 PÉRTIGA", "2.365,67"], mapeo, 12, None, lote.expediente_id, None, 0,
    )

    resultado = guardar_lineas_catalogo(db_session, lote.id, [reextraida])

    assert resultado.actualizadas == 1
    lineas = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id, matricula="643480020").all()
    assert len(lineas) == 1
    assert lineas[0].clave_linea == "P-012"


# Sesión de limpieza del Excel al cliente, bloque 2 (2026-09-06): tres
# defectos reales encontrados verificando las dos anotaciones pendientes de
# la sesión anterior (docs/excel-cliente-correccion.md) contra el corpus
# real -- ninguno de los tres estaba cubierto por los tests existentes.


def test_construir_linea_catalogo_recupera_descripcion_de_columna_fantasma_con_matricula():
    # Hallazgo real, `6.20/28510.0136_ANEJO_3.pdf` p.4, matrícula
    # `740540009`: el guard original de `_construir_campos` exigía
    # `matricula is None` para intentar la recuperación de columna fantasma,
    # asumiendo que el desplazamiento solo ocurre en filas huérfanas
    # (partida alzada). Falso -- la misma fila, CON matrícula válida en su
    # propia columna, trae la descripción vacía y el texto real desplazado
    # una columna a la derecha. La función de recuperación no toca la
    # columna de matrícula (ya extraída aparte): exigir su ausencia solo
    # dejaba la descripción vacía para siempre en una línea que sí se podía
    # recuperar.
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 2, "unidad_medida": None, "cantidad": 8, "precio_unitario": 7}
    fila = ["740540009", "AC 120\nCuMg 0,5", "", "HILO DE CONTACTO DE", "", "ET ADIF\n03.364.291.9", "LAC-HC-AC120-\nCA", "9,29 €/Kg", "70000 Kg"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=4, documento_origen_id=20, expediente_id=15, baja_lote=None, orden_aparicion=8
    )

    assert linea is not None
    assert linea["matricula"] == "740540009"
    assert linea["descripcion"] == "HILO DE CONTACTO DE"
    assert linea["precio_unitario"] == Decimal("9.29")
    assert linea["motivo_revision"] is not None


def test_construir_linea_catalogo_recupera_descripcion_de_columna_fantasma_anterior():
    # Bloque 1, sesión 2026-09-12 (auditoría del defecto de mapeo sin
    # cabecera en `6.22/28510.0094`/`0126`): fila real de
    # `ANEJO_53d9b3928f16babb.pdf` p.5 (P-101, matrícula 618050300). El
    # mapeo derivado del contenido de la tabla (mayoritario en sus 44 filas)
    # sitúa descripción en el índice 3, pero en esta fila concreta
    # `pdfplumber` fusiona la columna vacía intermedia con la de descripción
    # -- el texto real cae en el índice 2 y los índices 3 y 4 salen `None`
    # en vez de cadena vacía. La recuperación "columna siguiente" (índice 4)
    # no encuentra nada; esta prueba que la "columna anterior" sí.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 3, "unidad_medida": 5, "cantidad": None, "precio_unitario": 9}
    fila = ["P-101", "618050300", "EN-54", None, None, "UD.", "P16.5000.00", "ALTO", "", "91.314,71 €", ""]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=5, documento_origen_id=672, expediente_id=1, baja_lote=None, orden_aparicion=40
    )

    assert linea is not None
    assert linea["matricula"] == "618050300"
    assert linea["descripcion"] == "EN-54"
    assert linea["precio_unitario"] == Decimal("91314.71")
    assert linea["motivo_revision"] is not None


def test_construir_linea_catalogo_recupera_descripcion_de_celda_fundida_con_la_anterior():
    # Sesión 2026-09-14, tercera parte: fila real de `ANEJO_57694f5d5dacb236.pdf`
    # p.23 (`6.22/28510.0126`, LOTE 2). La celda de descripción sale `None`
    # (fundida con la anterior) y la siguiente es la unidad, reclamada.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 3, "unidad_medida": 4, "cantidad": 5, "precio_unitario": 7}
    fila = ["P-101", "618050300", "EN-54", None, "UD.", "0", "", "91.314,71 €", ""]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=23, documento_origen_id=670, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea["descripcion"] == "EN-54"
    assert linea["unidad_medida"] == "ud"
    # Una celda vacía de verdad ('') con la unidad al lado no es este caso.
    vacia = construir_linea_catalogo(
        ["P-101", "618050300", "EN-54", "", "UD.", "0", "", "91.314,71 €", ""], mapeo,
        pagina=23, documento_origen_id=670, expediente_id=1, baja_lote=None, orden_aparicion=0,
    )
    assert not vacia["descripcion"]


def test_construir_lineas_desde_tabla_encadena_fragmentos_de_descripcion_envuelta():
    # Mismo hallazgo real, generalizado: el resto de la frase envuelta
    # ("SECCIÓN CIRCULAR DE", "120 MM2 DE", "ALEACIÓN COBRE-", "MAGNESIO
    # 0,5 CON", "RANURA TIPO A") sigue en las filas siguientes, cada una sin
    # ningún otro dato propio (matrícula, precio, cantidad vacíos) -- exactamente
    # el fenómeno que `_combinar_filas_cabecera` ya resuelve para la cabecera,
    # aquí para una fila de datos. `construir_lineas_desde_tabla` (no
    # `construir_linea_catalogo`, que ve una fila a la vez) es quien tiene
    # acceso a las filas siguientes para encadenarlas.
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 2, "unidad_medida": None, "cantidad": 8, "precio_unitario": 7}
    tabla = TablaExtraida(
        cabecera=["Nº MATRÍCULA", "REF. ADIF", "DESCRIPCIÓN", None, None, "NORMATIVA APLICABLE", "PLANO DE REFERENCIA", "PRECIO DE REFERENCIA", "CANTIDADES DE REFERENCIA"],
        filas=[
            ["740540009", "AC 120\nCuMg 0,5", "", "HILO DE CONTACTO DE", "", "ET ADIF\n03.364.291.9", "LAC-HC-AC120-\nCA", "9,29 €/Kg", "70000 Kg"],
            [None, None, None, "SECCIÓN CIRCULAR DE", None, None, None, None, None],
            [None, None, None, "120 MM2 DE", None, None, None, None, None],
            [None, None, None, "ALEACIÓN COBRE-", None, None, None, None, None],
            [None, None, None, "MAGNESIO 0,5 CON", None, None, None, None, None],
            [None, None, None, "RANURA TIPO A", None, None, None, None, None],
            ["642910250", "AC 120\nCuAg 0.1", "HILO DE CONTACTO DE SECCIÓN CIRCULAR", None, None, "ET ADIF\n03.364.291.9", "LAC-HC-AC120-\nCA", "10,61 €/Kg", "70000 Kg"],
        ],
        pagina=4,
        bbox=(0, 0, 0, 0),
    )

    lineas = construir_lineas_desde_tabla(tabla, mapeo, documento_origen_id=20, expediente_id=15, baja_lote=None, orden_inicial=0)

    assert len(lineas) == 2  # las 5 filas de fragmento se absorben, no generan líneas propias
    primera = lineas[0]
    assert primera["matricula"] == "740540009"
    assert primera["descripcion"] == (
        "HILO DE CONTACTO DE SECCIÓN CIRCULAR DE 120 MM2 DE ALEACIÓN COBRE- MAGNESIO 0,5 CON RANURA TIPO A"
    )
    assert lineas[1]["matricula"] == "642910250"  # la siguiente fila de datos real no se toca


def test_construir_lineas_desde_tabla_recupera_precio_de_la_fila_siguiente():
    # Verificación del Excel exportado (2026-09-08): imagen especular de
    # `test_construir_lineas_desde_tabla_encadena_fragmentos_de_descripcion_envuelta`
    # de arriba -- ahí el fragmento que se desborda es la descripción, aquí
    # es el precio. Fixture real, `6.19/28510.0194_ANEJO_1.pdf` p.9: la
    # banda visual del precio queda una fila por debajo de matrícula y
    # descripción, tanto para una fila normal como para una partida alzada.
    # Sin este arreglo, cada material generaba DOS líneas de catálogo: la
    # real sin precio (sin ningún motivo_revision, indistinguible de un
    # precio genuinamente no publicado) y una fantasma con solo el precio,
    # sin descripción ni matrícula -- la fila "sin expediente, ni matrícula,
    # ni descripción, solo un precio" del Excel entregado al cliente.
    mapeo = {
        "codigo_precio": None, "matricula": 0, "descripcion": 1,
        "unidad_medida": 2, "cantidad": 5, "precio_unitario": 6,
    }
    tabla = TablaExtraida(
        cabecera=["MATRICULA", "DESIGNACIÓN", "MEDIDA", None, "ET", "PEDIDO INICIAL", "PRECIO"],
        filas=[
            ["650400190", "SISTEMA DE TRANSFERENCIA ESTÁTICO", "Unidad", None, "", "28", ""],
            [None, None, None, None, None, None, "1.264,59 €"],
            [None, None, None, None, None, None, ""],
            ["", "Partida alzada a justificar de repuestos para cubrir necesidades", "", None, "", "", ""],
            [None, None, None, None, None, None, "9.105,05 €"],
            [None, None, None, None, None, None, ""],
        ],
        pagina=9,
        bbox=(0, 0, 0, 0),
    )

    lineas = construir_lineas_desde_tabla(tabla, mapeo, documento_origen_id=20, expediente_id=15, baja_lote=None, orden_inicial=0)

    # Las dos filas fantasma de precio se absorben; las dos filas en blanco
    # finales (precio también vacío) se descartan como siempre.
    assert len(lineas) == 2
    primera, segunda = lineas
    assert primera["matricula"] == "650400190"
    assert primera["descripcion"] == "SISTEMA DE TRANSFERENCIA ESTÁTICO"
    assert primera["precio_unitario"] == Decimal("1264.59")
    assert "precio unitario recuperado de la fila siguiente" in primera["motivo_revision"]
    assert segunda["matricula"] is None
    assert segunda["descripcion"].startswith("Partida alzada")
    assert segunda["precio_unitario"] == Decimal("9105.05")
    assert "precio unitario recuperado de la fila siguiente" in segunda["motivo_revision"]


def test_linea_sin_descripcion_ni_matricula_con_fragmento_vacio_se_descarta():
    # Encargo de esta sesión: una fila sin descripción y sin matrícula no
    # identifica ningún material. Si además el resto de la fila está en
    # blanco (relleno puro de tabla), se descarta -- ya lo hacía el guard de
    # `precio_unitario is None`, se deja como fixture de regresión.
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    fila = [None, None, None]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=5, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is None


def test_fila_de_totales_sin_etiqueta_en_la_matricula_es_pie_de_tabla():
    # Sesión 2026-09-16 (noche): el pie de totales con la etiqueta en la
    # columna de código (`6.22/28510.0174` p.10) o pegada a su importe en la
    # de cantidad (`6.21/28510.0026` p.11: "21% IVA 7.350,00 €", que se leía
    # como 217.350 €) no es una línea de material.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": 4, "precio_unitario": 5}
    for fila in (
        ["PRESUPUESTO DE LICITACIÓN", "", "", "", "", "59.960,00 €"],
        ["IVA", "", "", "", "", "12.591,60 €"],
        ["TOTAL CON IVA", "", "", "", "", "72.551,60 €"],
        ["", "", "", "", "PRESUPUESTO DE LICITACIÓN 35.000,00 €", ""],
        ["", "", "", "", "21% IVA 7.350,00 €", ""],
    ):
        linea = construir_linea_catalogo(
            fila, mapeo, pagina=10, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
        )
        assert linea is None, fila


def test_linea_sin_descripcion_ni_matricula_con_precio_va_a_revision():
    # Variante real del encargo: la fila SÍ trae un precio real (y un
    # código de precio), pero ni descripción ni matrícula sobreviven a
    # ningún intento de recuperación -- nadie puede saber qué material es.
    # No se descarta en silencio (hay contenido real en el fragmento: el
    # propio precio) ni se inventa una descripción: se conserva marcada para
    # revisión humana contra el documento de origen.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": None, "cantidad": None, "precio_unitario": 3}
    fila = ["P-099", "", "", "45,00 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=5, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["descripcion"] == ""
    assert linea["matricula"] is None
    assert linea["motivo_revision"] is not None
    assert "sin descripción ni matrícula" in linea["motivo_revision"]


def test_linea_partida_alzada_recupera_descripcion_de_columna_codigo_precio_sin_mapear():
    # Verificación del Excel exportado (2026-09-08), fixture real
    # `6.22/28510.0039_ANEJO_1.pdf` p.14: la cabecera dice "CODIFICACIÓN DEL
    # PRECIO" (no casa con el alias "codigo" de `codigo_precio`, así que esa
    # columna queda sin mapear del todo) y "Nº MATRÍCULA"/"DESCRIPCIÓN" en
    # sus columnas de siempre. La fila de la partida alzada solo trae dos
    # valores reales: su texto en la columna sin mapear, y el precio en la
    # suya -- sin este arreglo, la línea se guardaba sin descripción, sin
    # matrícula y sin código de expediente cruzado.
    mapeo = {
        "codigo_precio": None, "matricula": 1, "descripcion": 3,
        "unidad_medida": 4, "cantidad": 5, "precio_unitario": 6,
    }
    fila = ["Partida alzada a justificar para imprevistos", None, None, None, None, None, "624.050\n,00€"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=14, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["descripcion"] == "Partida alzada a justificar para imprevistos"
    assert linea["matricula"] is None
    assert linea["precio_unitario"] == Decimal("624050.00")
    assert "columna sin asignar en el mapeo" in linea["motivo_revision"]


def test_linea_partida_alzada_recupera_descripcion_de_columna_codigo_adif_sin_mapear():
    # Mismo hallazgo, segunda variante real, `6.25/28510.0213_ANEJO_1.pdf`
    # p.18: aquí SÍ hay `codigo_precio` real ("P-06"), pero "matricula" no
    # se reconoció para esta cabecera ("CÓDIGO ADIF" no casa con ningún
    # alias) y es esa columna sin mapear la que se lleva el texto real.
    mapeo = {
        "codigo_precio": 0, "matricula": None, "descripcion": 2,
        "unidad_medida": 3, "cantidad": 7, "precio_unitario": 8,
    }
    fila = ["P-06", "PARTIDA ALZADA A JUSTIFICAR PARA IMPREVISTOS", None, None, None, None, None, None, "30.000,00 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=18, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["descripcion"] == "PARTIDA ALZADA A JUSTIFICAR PARA IMPREVISTOS"
    assert linea["codigo_precio"] == "P-06"
    assert linea["matricula"] is None
    assert linea["precio_unitario"] == Decimal("30000.00")
    assert "columna sin asignar en el mapeo" in linea["motivo_revision"]


def test_linea_sin_descripcion_ni_matricula_con_dos_columnas_candidatas_no_adivina():
    # Guard de `_recuperar_descripcion_ultimo_recurso`: con DOS columnas sin
    # mapear que parecen descripción, no hay forma de saber cuál es la
    # buena -- se deja la línea como antes (a revisión), sin adivinar.
    mapeo = {"codigo_precio": None, "matricula": None, "descripcion": 2, "unidad_medida": None, "cantidad": None, "precio_unitario": 3}
    fila = ["Texto candidato uno", "Texto candidato dos", None, "45,00 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=5, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["descripcion"] == ""
    assert "sin descripción ni matrícula" in linea["motivo_revision"]
    assert "columna sin asignar" not in linea["motivo_revision"]


def test_combinar_por_clave_funde_por_firma_sin_matricula_dentro_del_mismo_lote():
    # Hallazgo real, `6.24/28510.0180_ANEJO_1.pdf`: una tabla de "impacto
    # del fallo del elemento en la seguridad operacional" repite el mismo
    # material (misma descripción, mismo precio) que ya trae la tabla real
    # de precios, bajo un `codigo_precio` de numeración propia y sin
    # matrícula ninguna de las dos veces -- `_firma_material` antes exigía
    # matrícula, así que estas dos nunca se fundían pese a ser, con
    # certeza razonable, la misma línea de catálogo.
    de_precios = {
        "clave_linea": "PN004", "matricula": None, "descripcion": "m² placa hito hectométrico en fibra",
        "codigo_precio": "PN004", "precio_unitario": Decimal("367.38"), "cantidad": Decimal("1200"), "pagina": 18,
    }
    de_impacto_seguridad = {
        "clave_linea": "PN004ps", "matricula": None, "descripcion": "m² placa hito hectométrico en fibra",
        "codigo_precio": "PN004ps", "precio_unitario": Decimal("367.38"), "cantidad": None, "pagina": 23,
    }

    combinadas = _combinar_por_clave([de_precios, de_impacto_seguridad])

    assert len(combinadas) == 1
    assert combinadas[0]["cantidad"] == Decimal("1200")  # se conserva el dato que solo traía una de las dos
    assert "sin matrícula" in combinadas[0]["motivo_revision"]


def test_fusion_por_firma_no_se_lleva_el_codigo_de_la_tabla_de_criterios_p0996(db_session):
    """Sesión 2026-09-14, tercera parte. `6.23/28510.0051_ANEJO_1`: el cuadro
    de precios (p.49) y el anejo de criterios (p.95) numeran distinto el
    mismo material -- "ENF-54 Curva", matrícula 618050403, es P-0994 en el
    cuadro y P-0996 en criterios; P-0996 es en el cuadro otro material
    ("ESF-B1-UIC54-186-1/10.5- CR-I-E:3500"). La fusión por firma se llevaba
    el código de criterios a la línea del cuadro y, al guardar, la clave
    pasaba a "P-0996": `uq_linea_lote_clave`, y el documento entero se
    deshacía en cada reproceso. Las dos filas guardadas son las de la base
    real (la primera, de una pasada anterior, ya con el código cambiado)."""
    lote = _lote(db_session)
    db_session.add_all([
        LineaCatalogo(
            lote_id=lote.id, expediente_id=lote.expediente_id, clave_linea="P-0994", orden_aparicion=0,
            codigo_precio="P-0996", matricula="618050403", descripcion="ENF-54 Curva", pagina=95,
            precio_unitario=Decimal("54788.83"),
        ),
        LineaCatalogo(
            lote_id=lote.id, expediente_id=lote.expediente_id, clave_linea="P-0996", orden_aparicion=1,
            codigo_precio="P-0996", descripcion="ESF-B1-UIC54-186-1/10.5- CR-I-E:3500", pagina=49,
            precio_unitario=Decimal("204094.04"),
        ),
    ])
    db_session.commit()
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": None, "cantidad": None, "precio_unitario": 3}
    filas = [
        (["P-0994", "618050403", "ENF-54 Curva", "54.788,83"], 49),
        (["P-0996", None, "ESF-B1-UIC54-186-1/10.5- CR-I-E:3500", "204.094,04"], 49),
        (["P-0996", "618050403", "ENF-54 Curva", "54.788,83"], 95),
    ]
    lineas = [
        construir_linea_catalogo(fila, mapeo, pagina, None, lote.expediente_id, None, orden)
        for orden, (fila, pagina) in enumerate(filas)
    ]

    guardar_lineas_catalogo(db_session, lote.id, lineas)
    db_session.commit()

    por_clave = {l.clave_linea: l for l in db_session.query(LineaCatalogo).filter_by(lote_id=lote.id)}
    assert set(por_clave) == {"P-0994", "P-0996"}
    assert por_clave["P-0994"].codigo_precio == "P-0994"
    assert por_clave["P-0994"].descripcion == "ENF-54 Curva"
    assert por_clave["P-0996"].descripcion == "ESF-B1-UIC54-186-1/10.5- CR-I-E:3500"
    assert por_clave["P-0996"].precio_unitario == Decimal("204094.04")


def test_fusion_por_firma_no_junta_dos_codigos_de_la_misma_tabla():
    # `6.23/28510.0051`, cuadro de precios del LOTE 1: P-0166 (p.21) y P-0178
    # (p.22, continuación de la misma tabla) traen el mismo texto y precio.
    # Son dos entradas del catálogo, no un eco.
    comunes = {"matricula": None, "descripcion": "Semicambio izq (sencillo) DIRD-B1-54-190-0.11-CR-D",
               "precio_unitario": Decimal("22712.17")}
    p0166 = {**comunes, "clave_linea": "P-0166", "codigo_precio": "P-0166", "pagina": 21, "tabla_origen": (36, 1)}
    p0178 = {**comunes, "clave_linea": "P-0178", "codigo_precio": "P-0178", "pagina": 22, "tabla_origen": (36, 1)}
    assert sorted(l["codigo_precio"] for l in _combinar_por_clave([p0166, p0178])) == ["P-0166", "P-0178"]
    # De tablas distintas (el eco de otra tabla con su propia numeración),
    # sí se funden, con el código de la primera.
    eco = {**p0178, "tabla_origen": (36, 2)}
    combinadas = _combinar_por_clave([p0166, eco])
    assert [l["codigo_precio"] for l in combinadas] == ["P-0166"]


def test_guardar_no_absorbe_una_linea_de_esta_misma_pasada_con_otro_codigo(db_session):
    # `6.23/28510.0051`: P-0167 y P-0179, mismo texto y precio, guardadas
    # desde el ANEJO; el Contrato trae la misma tabla y, al guardar su P-0167,
    # la búsqueda por firma se tragaba la P-0179 y la borraba.
    lote = _lote(db_session)
    comunes = dict(
        lote_id=lote.id, expediente_id=lote.expediente_id, descripcion="Semicambio dcha (sencillo) DIRD-B1-54-190-0.11-CR-D",
        precio_unitario=Decimal("22712.17"), pagina=22,
    )
    p0167 = LineaCatalogo(clave_linea="P-0167", codigo_precio="P-0167", orden_aparicion=0, **comunes)
    p0179 = LineaCatalogo(clave_linea="P-0179", codigo_precio="P-0179", orden_aparicion=1, **comunes)
    db_session.add_all([p0167, p0179])
    db_session.commit()
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    del_contrato = construir_linea_catalogo(
        ["P-0167", "Semicambio dcha (sencillo) DIRD-B1-54-190-0.11-CR-D", "22.712,17"], mapeo, 118, None,
        lote.expediente_id, None, 0,
    )

    guardar_lineas_catalogo(db_session, lote.id, [del_contrato], ids_vivas=frozenset({p0167.id, p0179.id}))
    db_session.commit()

    assert sorted(l.codigo_precio for l in db_session.query(LineaCatalogo).filter_by(lote_id=lote.id)) == [
        "P-0167", "P-0179",
    ]


def test_reguardar_una_pareja_de_codigos_de_la_misma_tabla_conserva_los_ids(db_session):
    # Determinismo (misma sesión): P-0166 y P-0178 ya guardadas por la
    # pasada anterior. Al volver a guardar las dos, la de P-0166 no debe
    # tragarse la P-0178 (que esta misma llamada va a escribir) para que se
    # recree con otro `id`.
    lote = _lote(db_session)
    texto = "Semicambio izq (sencillo) DIRD-B1-54-190-0.11-CR-D"
    guardadas = [
        LineaCatalogo(
            lote_id=lote.id, expediente_id=lote.expediente_id, clave_linea=codigo, codigo_precio=codigo,
            orden_aparicion=i, descripcion=texto, precio_unitario=Decimal("22712.17"), pagina=21 + i,
        )
        for i, codigo in enumerate(["P-0166", "P-0178"])
    ]
    db_session.add_all(guardadas)
    db_session.commit()
    ids = sorted(l.id for l in guardadas)
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    lineas = []
    for i, codigo in enumerate(["P-0166", "P-0178"]):
        linea = construir_linea_catalogo([codigo, texto, "22.712,17"], mapeo, 21 + i, None, lote.expediente_id, None, i)
        linea["tabla_origen"] = (36, 1)
        lineas.append(linea)

    guardar_lineas_catalogo(db_session, lote.id, lineas)
    db_session.commit()

    assert sorted(l.id for l in db_session.query(LineaCatalogo).filter_by(lote_id=lote.id)) == ids


def test_limpiar_huerfana_superada_no_toca_la_de_otro_documento(db_session):
    # `4.25/28510.0208`: su Contrato y el del LOTE 1 tienen la misma tabla en
    # la misma posición. Guardar la del primero (en su lote) no debe borrar
    # la huérfana del segundo, con la misma clave de huérfana.
    lote = _lote(db_session)
    otra = LineaCatalogo(
        lote_id=None, expediente_id=lote.expediente_id, clave_linea="P-01@p109y186", codigo_precio="P-01",
        orden_aparicion=0, descripcion="Vagón de bogies", precio_unitario=Decimal("61.60"), pagina=109,
        documento_origen_id=None,
    )
    db_session.add(otra)
    db_session.commit()
    from app.catalogo import _limpiar_huerfana_superada

    _limpiar_huerfana_superada(db_session, lote.expediente_id, "P-01@p109y186", documento_origen_id=858)
    db_session.commit()

    assert db_session.get(LineaCatalogo, otra.id) is not None


def test_guardar_si_absorbe_el_mismo_codigo_leido_con_ruido(db_session):
    # `6.21/28510.0109_ANEJO_1` p.30 dice "P-63"; la extracción leyó "VP-63".
    # El mismo código con ruido delante no es otra entrada del catálogo.
    lote = _lote(db_session)
    ruidosa = LineaCatalogo(
        lote_id=lote.id, expediente_id=lote.expediente_id, clave_linea="VP-63", codigo_precio="VP-63",
        orden_aparicion=0, descripcion="Semicambio para desvío tipo B1 de radio 320/197",
        precio_unitario=Decimal("15015.00"), pagina=30,
    )
    db_session.add(ruidosa)
    db_session.commit()
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    buena = construir_linea_catalogo(
        ["P-63", "Semicambio para desvío tipo B1 de radio 320/197", "15.015,00"], mapeo, 14, None,
        lote.expediente_id, None, 0,
    )

    guardar_lineas_catalogo(db_session, lote.id, [buena], ids_vivas=frozenset({ruidosa.id}))
    db_session.commit()

    assert [l.codigo_precio for l in db_session.query(LineaCatalogo).filter_by(lote_id=lote.id)] == ["P-63"]


def test_fusion_por_firma_nunca_renombra_a_una_clave_de_otra_linea(db_session):
    # Red de seguridad de la misma sesión: una fila sin código (eco de una
    # tabla sin columna de código) encuentra por firma la línea que una
    # pasada anterior dejó con clave P-0994 y código P-0996. Renombrarla a
    # su código chocaría con la P-0996 real del lote: se conserva la clave.
    lote = _lote(db_session)
    db_session.add_all([
        LineaCatalogo(
            lote_id=lote.id, expediente_id=lote.expediente_id, clave_linea="P-0994", orden_aparicion=0,
            codigo_precio="P-0996", matricula="618050403", descripcion="ENF-54 Curva", pagina=95,
            precio_unitario=Decimal("54788.83"),
        ),
        LineaCatalogo(
            lote_id=lote.id, expediente_id=lote.expediente_id, clave_linea="P-0996", orden_aparicion=1,
            codigo_precio="P-0996", descripcion="ESF-B1-UIC54-186-1/10.5- CR-I-E:3500", pagina=49,
            precio_unitario=Decimal("204094.04"),
        ),
    ])
    db_session.commit()
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    eco = construir_linea_catalogo(["618050403", "ENF-54 Curva", "54.788,83"], mapeo, 12, None, lote.expediente_id, None, 0)

    guardar_lineas_catalogo(db_session, lote.id, [eco])
    db_session.commit()

    claves = sorted(l.clave_linea for l in db_session.query(LineaCatalogo).filter_by(lote_id=lote.id))
    assert claves == ["P-0994", "P-0996"]


def test_guardar_lineas_catalogo_funde_por_firma_sin_matricula_entre_documentos_distintos(db_session):
    # Mismo hallazgo, pero cuando las dos tablas viven en documentos
    # distintos del mismo expediente (`6.23/28510.0042`: ANEJO_1 y
    # CONTRATO_1) -- dos llamadas a `guardar_lineas_catalogo` separadas,
    # `_combinar_por_clave` en memoria nunca las ve juntas.
    lote = _lote(db_session)
    de_precios = {
        "clave_linea": "P-016", "expediente_id": lote.expediente_id, "orden_aparicion": 15,
        "matricula": None, "descripcion": "PÉRTIGA VERIFICADORA", "codigo_precio": "P-016",
        "precio_unitario": Decimal("2298.82"), "cantidad": None, "unidad_medida": None,
        "baja_lote": None, "precio_adjudicado": None, "documento_origen_id": 30, "pagina": 10,
        "fragmento": "", "motivo_revision": None,
    }
    de_impacto_seguridad = {
        "clave_linea": "P-016b", "expediente_id": lote.expediente_id, "orden_aparicion": 15,
        "matricula": None, "descripcion": "PÉRTIGA VERIFICADORA", "codigo_precio": "P-016b",
        "precio_unitario": Decimal("2298.82"), "cantidad": None, "unidad_medida": None,
        "baja_lote": None, "precio_adjudicado": None, "documento_origen_id": 33, "pagina": 105,
        "fragmento": "", "motivo_revision": None,
    }

    r1 = guardar_lineas_catalogo(db_session, lote.id, [de_precios])
    db_session.commit()
    r2 = guardar_lineas_catalogo(db_session, lote.id, [de_impacto_seguridad])
    db_session.commit()

    assert r1.creadas == 1
    assert r2.creadas == 0 and r2.actualizadas == 1
    lineas = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id, descripcion="PÉRTIGA VERIFICADORA").all()
    assert len(lineas) == 1
    assert "sin matrícula" in lineas[0].motivo_revision


def test_combinar_por_clave_no_repite_el_motivo_al_fundir_mas_de_dos_firmas_iguales():
    # Una firma sin matrícula puede absorber más de dos filas (la misma
    # tabla repetida tres veces): el motivo de revisión no debe repetirse
    # una vez por cada fusión (CONTEXTO.md sección 9, idempotencia).
    filas = [
        {
            "clave_linea": f"C-{i}", "matricula": None, "descripcion": "PARTIDA ALZADA A JUSTIFICAR PARA IMPREVISTOS",
            "codigo_precio": None, "precio_unitario": Decimal("300000.00"), "pagina": i,
        }
        for i in range(3)
    ]

    combinadas = _combinar_por_clave(filas)

    assert len(combinadas) == 1
    motivo = combinadas[0]["motivo_revision"]
    assert motivo.count("sin matrícula") == 1


# Aviso del cliente, sesión 2026-09-07: el campo Cantidad del catálogo a
# veces contiene lo que parece un año. Rastreado hasta `6.20/28510.0054`
# ANEJO_8 p.10 (traviesas): el modelo mapeó "unidad_medida" a la columna
# "E.T." (referencia normativa, no una unidad -- `cache_mapeo_cabecera` ids
# 71-75, las 5 variantes de esta cabecera resueltas por el modelo) en vez de
# a ninguna columna. "cantidad" en sí SÍ está bien mapeada -- la cabecera
# del documento dice literalmente "CANTIDAD DE REFERENCIA" -- pero su valor
# real en el documento cae en un rango que parece un año (1872, 1996-2005).


def test_construir_linea_catalogo_descarta_unidad_medida_con_forma_de_normativa():
    # Mismo hallazgo: "03.360.571.8" tiene la forma de una referencia
    # normativa de ADIF (varios grupos numéricos separados por puntos), no
    # de una unidad de medida real -- se descarta en vez de guardarse como
    # si fuera "ud" o "m".
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": 2, "cantidad": 3, "precio_unitario": 4}
    fila = ["607000000", "TRAVIESA AI-VE", "03.360.571.8", "1997", "73,15 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=10, documento_origen_id=241, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["unidad_medida"] is None
    assert "solo numérica" in linea["motivo_revision"]


def test_construir_linea_catalogo_descarta_unidad_medida_puramente_numerica():
    # Segunda variante real del mismo hallazgo: `6.20/28510.0094` ANEJO p.4
    # (candado/llave) -- el modelo mapeó "unidad_medida" a una columna en
    # blanco que en realidad trae la cantidad ("956") desplazada por una
    # columna fantasma, no una referencia normativa con puntos como la otra
    # variante. El mismo patrón (solo dígitos, sin ninguna letra) cubre las
    # dos. Con el mapeo tal cual quedó cacheado ANTES de corregirlo (id 77,
    # `unidad_medida: 2`), esta prueba solo cubre la red de seguridad de
    # `_construir_campos`: descarta el valor, pero `cantidad` sigue sin
    # recuperar porque el propio mapeo sigue reclamando el índice 2 para
    # "unidad_medida" (`_recuperar_columna_fantasma` nunca le quita un
    # valor a otro campo del mapeo, aunque ese campo acabe descartado más
    # tarde) -- la siguiente prueba cubre el mapeo ya corregido.
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": 2, "cantidad": 3, "precio_unitario": 5}
    fila = ["690540008", "CANDADO 70mm CERRAMIENTO LINEAS FERROVIARIAS", "956", None, None, "83,47 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=4, documento_origen_id=229, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["unidad_medida"] is None
    assert linea["cantidad"] is None


def test_construir_linea_catalogo_recupera_cantidad_tras_corregir_el_mapeo():
    # Mismo caso real, con el mapeo ya corregido en `cache_mapeo_cabecera`
    # (id 77, `unidad_medida: null`, sesión 2026-09-07): sin nada
    # reclamando el índice 2, `_recuperar_cantidad_columna_fantasma` (ya
    # existente, no nuevo) sí encuentra "956" ahí -- arreglar el mapeo, no
    # solo la validación de `_construir_campos`, es lo que de verdad
    # recupera la cantidad perdida en este caso real.
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": None, "cantidad": 3, "precio_unitario": 5}
    fila = ["690540008", "CANDADO 70mm CERRAMIENTO LINEAS FERROVIARIAS", "956", None, None, "83,47 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=4, documento_origen_id=229, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["unidad_medida"] is None
    assert linea["cantidad"] == Decimal("956")


def test_construir_linea_catalogo_no_descarta_unidad_medida_real():
    # Contraste: una unidad de medida real de verdad ("UD.", "M", "t") no
    # tiene la forma de una referencia normativa y no se toca.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": 4, "precio_unitario": 5}
    fila = ["P-009", "", "CABLE ARMADO DE Cu", "M", "2.000,00", "4,79 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=115, documento_origen_id=95, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["unidad_medida"] == "m"


# Bloque 3, segunda tanda de cambios del cliente tras revisar el catálogo
# (sesión 2026-09-09): `6.20/28510.0136_ANEJO_3.pdf` ("hilo de contacto")
# no declara ninguna columna de unidad, pero la trae pegada al número de
# cantidad o tras "€/" en el precio -- verificado contra el PDF real,
# matrícula 642910100.
def test_construir_linea_catalogo_recupera_unidad_embebida_en_cantidad():
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": None, "cantidad": 2, "precio_unitario": 3}
    fila = ["642910100", "HILO DE CONTACTO DE SECCIÓN CIRCULAR DE 107MM2", "120000 Kg", "9,61 €/Kg"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=3, documento_origen_id=20, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["unidad_medida"] == "kg"
    # La cantidad y el precio ya salían bien sin este arreglo
    # (parsear_numero_es/parsear_importe_es descartan cualquier carácter
    # que no sea dígito o separador) -- este bloque es solo sobre la unidad.
    assert linea["cantidad"] == Decimal("120000")
    assert linea["precio_unitario"] == Decimal("9.61")
    assert "recuperada de la propia celda" in linea["motivo_revision"]


def test_construir_linea_catalogo_recupera_unidad_embebida_en_precio_cuando_cantidad_vacia():
    # Verificado contra el PDF real: matrículas 740560006/740570001, cantidad
    # vacía del todo, la unidad solo aparece en el precio ("14,70 €/Kg").
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": None, "cantidad": 2, "precio_unitario": 3}
    fila = ["740560006", "CABLE FLEXIBLE DE 16 MM2 DE BRONCE BZ II", None, "14,70 €/Kg"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=5, documento_origen_id=20, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["unidad_medida"] == "kg"
    assert linea["precio_unitario"] == Decimal("14.70")


def test_construir_linea_catalogo_recupera_unidad_embebida_metros():
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": None, "cantidad": 2, "precio_unitario": 3}
    fila = ["665100001", "EAPSP de 1x4x0,9 mm", "1200 m", "4,05 €/m"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=7, documento_origen_id=20, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["unidad_medida"] == "m"


def test_construir_linea_catalogo_no_extrae_unidad_de_un_codigo_que_solo_parece_tenerla():
    # Contraste: un valor de cantidad que no es "número + unidad" tal cual
    # (p.ej. un código con una letra suelta en medio) no debe disparar la
    # extracción -- el patrón exige que la celda ENTERA sea número + Kg/m.
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": None, "cantidad": 2, "precio_unitario": 3}
    fila = ["715500320", "ACC.DE AGUJA L-826H PABN", "1", "9.028,66 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=90, documento_origen_id=487, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["unidad_medida"] is None


def test_construir_linea_catalogo_no_pisa_unidad_ya_resuelta_en_su_columna():
    # La unidad ya viene de su propia columna: la recuperación de celda
    # embebida ni se intenta.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": 4, "precio_unitario": 5}
    fila = ["P-009", "", "CABLE ARMADO DE Cu", "UD.", "2000 Kg", "4,79 €/Kg"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=115, documento_origen_id=95, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["unidad_medida"] == "ud"


def test_construir_linea_catalogo_marca_cantidad_con_forma_de_anio():
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": None, "cantidad": 2, "precio_unitario": 3}
    fila = ["607010254", "TRAVIESA PR-VE 54E1", "2004", "76,19 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=10, documento_origen_id=241, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["cantidad"] == Decimal("2004")
    assert "parece un año" in linea["motivo_revision"]


def test_construir_linea_catalogo_marca_cantidad_cero():
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": 4, "precio_unitario": 5}
    fila = ["P-0087", "", "Semicambio dcha (doble) SIN cruz obtuso", "UD.", "0", "29.525,82 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=17, documento_origen_id=36, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["cantidad"] == Decimal("0")
    assert "cantidad es 0" in linea["motivo_revision"]


def test_construir_linea_catalogo_no_marca_cantidad_plausible():
    # Contraste: una cantidad real y corriente (30 unidades) no dispara
    # ningún motivo de revisión por este mecanismo.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": 4, "precio_unitario": 5}
    fila = ["P-001", "697500900", "GUANTE X", "UN", "30", "24,00"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=1, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["cantidad"] == Decimal("30")
    assert linea["motivo_revision"] is None


def test_construir_linea_catalogo_no_marca_cantidad_redonda_fuera_de_rango_de_anio():
    # Una cantidad real y grande (2500 metros de cable) que cae fuera del
    # rango de año no se marca -- el rango es deliberadamente estrecho
    # (1900-2100) para no generar ruido sobre cantidades legítimas mayores.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": 4, "precio_unitario": 5}
    fila = ["P-010", "", "CABLE ARMADO DE Cu", "M", "2.500,00", "5,20 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=1, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["cantidad"] == Decimal("2500")
    assert linea["motivo_revision"] is None


# Bloque 4, segunda tanda de cambios del cliente tras revisar el catálogo
# (sesión 2026-09-09): defecto real de extracción de unidad de medida,
# verificado contra `6.22_28510.0126_ANEJO_53d9b3928f16babb.pdf` p.3.
# Cabecera real: [CÓDIGO DEL ELEMENTO(0), Nº MATRÍCULA(1), DESCRIPCIÓN(2),
# None(3), None(4), UNIDAD DE MEDIDA(5), PLANO DE REFERENCIA(6),
# IMPACTO...(7), PRECIO UNITARIO(8), None(9), None(10)]. Las filas "D"
# (P-001, P-003, P-005...) traen la descripción y el precio reales una
# columna más a la derecha de lo que el mapeo espera -- dos columnas
# fantasma independientes en la misma fila -- mientras que código de
# precio, matrícula y unidad de medida SÍ están en su columna de siempre.
_MAPEO_ANEJO_0126 = {
    "codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 5, "cantidad": None, "precio_unitario": 8,
}


def test_construir_linea_catalogo_dos_columnas_fantasma_no_desplaza_codigo_ni_unidad():
    fila_d = [
        "P-001", "611150110", "", "DS-B1-54-320/230-0,11-CR-D", "", "UD.",
        "P16.2627.00", "ALTO", "", "122.624,14 €", "",
    ]

    linea = construir_linea_catalogo(
        fila_d, _MAPEO_ANEJO_0126, pagina=3, documento_origen_id=672, expediente_id=1,
        baja_lote=None, orden_aparicion=0,
    )

    assert linea is not None
    # Antes del arreglo, desplazar el mapeo entero "arreglaba" descripción y
    # precio pero rompía estos dos -- código de precio pasaba a leer la
    # matrícula, y unidad de medida pasaba a leer "Plano de Referencia".
    assert linea["codigo_precio"] == "P-001"
    assert linea["unidad_medida"] == "ud"
    assert linea["descripcion"] == "DS-B1-54-320/230-0,11-CR-D"
    assert linea["precio_unitario"] == Decimal("122624.14")
    assert "propia columna fantasma" in linea["motivo_revision"]


def test_construir_linea_catalogo_columna_fantasma_de_referencia_vacia_tambien_se_recupera():
    # Caso real, matrícula 611150412: la misma fila "D", pero con "Plano de
    # Referencia" vacío en vez de relleno -- no cambia el resultado, la
    # recuperación no depende de esa columna.
    fila_d = [
        "P-015", "611150412", "", "DSI-B1-54-320/230-0,11-CR-D", "", "UD.",
        "", "ALTO", "", "107.198,44 €", "",
    ]

    linea = construir_linea_catalogo(
        fila_d, _MAPEO_ANEJO_0126, pagina=3, documento_origen_id=672, expediente_id=1,
        baja_lote=None, orden_aparicion=0,
    )

    assert linea is not None
    assert linea["codigo_precio"] == "P-015"
    assert linea["matricula"] == "611150412"
    assert linea["unidad_medida"] == "ud"
    assert linea["precio_unitario"] == Decimal("107198.44")


def test_construir_linea_catalogo_fila_i_sin_columnas_fantasma_no_se_toca():
    # Contraste: la fila "I" hermana no tiene columnas fantasma -- descripción
    # y precio ya están en su columna de siempre, así que ni la recuperación
    # nueva ni el desplazamiento completo llegan a intentarse.
    fila_i = ["P-002", "611150111", "DS-B1-54-320/230-0,11-CR-I", None, None, "UD.", "P16.2627.00\nSIM", "ALTO", "107.198,44 €", None, None]

    linea = construir_linea_catalogo(
        fila_i, _MAPEO_ANEJO_0126, pagina=3, documento_origen_id=672, expediente_id=1,
        baja_lote=None, orden_aparicion=0,
    )

    assert linea is not None
    assert linea["codigo_precio"] == "P-002"
    assert linea["unidad_medida"] == "ud"
    assert linea["motivo_revision"] is None


# Nota: la cobertura de que una fila SÍ realmente desalineada (código de
# precio también vacío en la columna de siempre) sigue cayendo en el
# desplazamiento completo de siempre la da la suite ya existente de
# `_intentar_recuperar_desalineacion` más arriba en este fichero -- ahí
# `codigo_precio` sale `None` con el mapeo sin desplazar, así que la
# recuperación nueva (que exige codigo_precio o matrícula ya resueltos) ni
# se intenta, y el comportamiento no cambia.


def test_construir_linea_catalogo_matricula_fusionada_de_dos_filas_no_revienta_varchar():
    # Hallazgo real, verificado reprocesando 6.22/28510.0126 contra el
    # stack real tras el arreglo de arriba (bloque 5, cambios del cliente
    # tras revisar el catálogo): con más filas recuperadas de columna
    # fantasma, una fila fusionada por pdfplumber con dos matrículas reales
    # pegadas en la misma celda ("611150110\n611150111") llegaba hasta
    # `varchar(9)` y reventaba el INSERT -- `^\d+$` sin límite de longitud
    # la dejaba pasar como "matrícula válida" por no tener ninguna letra.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": 4, "precio_unitario": 5}
    fila = ["P-001", "611150110\n611150111", "CABLE ARMADO DE Cu", "UD.", "1", "24,00 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=123, documento_origen_id=667, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["matricula"] is None
    assert "no reconocible" in linea["motivo_revision"]


def test_construir_linea_catalogo_matricula_de_nueve_digitos_sigue_valida():
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": 4, "precio_unitario": 5}
    fila = ["P-001", "611150110", "CABLE ARMADO DE Cu", "UD.", "1", "24,00 €"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=123, documento_origen_id=667, expediente_id=1, baja_lote=None, orden_aparicion=0
    )

    assert linea is not None
    assert linea["matricula"] == "611150110"


# --- ids_tocadas / podar_lineas_obsoletas_de_documento (bloque 4, sesión 2026-09-10) ---


def test_guardar_lineas_catalogo_devuelve_ids_tocadas(db_session):
    lote = _lote(db_session)
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    fila = ["P-001", "Guante", "24,00"]
    lineas = [construir_linea_catalogo(fila, mapeo, 11, None, lote.expediente_id, None, 0)]

    creada = guardar_lineas_catalogo(db_session, lote.id, lineas)
    db_session.commit()
    linea_id = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id, clave_linea="P-001").one().id

    assert creada.ids_tocadas == frozenset({linea_id})

    actualizada = guardar_lineas_catalogo(db_session, lote.id, lineas)
    assert actualizada.ids_tocadas == frozenset({linea_id})


def _linea_directa(db_session, *, expediente_id, documento_origen_id, clave, heredado_de_matriz=None):
    linea = LineaCatalogo(
        expediente_id=expediente_id,
        lote_id=None,
        clave_linea=clave,
        orden_aparicion=0,
        descripcion=f"Material {clave}",
        documento_origen_id=documento_origen_id,
        heredado_de_matriz=heredado_de_matriz,
    )
    db_session.add(linea)
    db_session.commit()
    return linea


def test_podar_lineas_obsoletas_de_documento_borra_lo_que_ya_no_se_toco(db_session):
    # Caso real del bloque 4: dos filas del mismo documento en un reproceso
    # anterior, una de las cuales ya no aparece en el reproceso actual (su
    # clave cambió, p.ej. porque un arreglo de mapeo cambió qué texto cae en
    # `descripcion`) -- debe podarse, la otra no.
    expediente = Expediente(codigo_expediente="6.24/28510.8888")
    db_session.add(expediente)
    db_session.commit()
    conservada = _linea_directa(db_session, expediente_id=expediente.id, documento_origen_id=50, clave="a")
    obsoleta = _linea_directa(db_session, expediente_id=expediente.id, documento_origen_id=50, clave="b-vieja")

    podadas = podar_lineas_obsoletas_de_documento(db_session, expediente.id, 50, frozenset({conservada.id}))

    assert podadas == 1
    assert db_session.get(LineaCatalogo, obsoleta.id) is None
    assert db_session.get(LineaCatalogo, conservada.id) is not None


def test_podar_lineas_obsoletas_de_documento_no_toca_otro_documento(db_session):
    expediente = Expediente(codigo_expediente="6.24/28510.8887")
    db_session.add(expediente)
    db_session.commit()
    de_otro_documento = _linea_directa(db_session, expediente_id=expediente.id, documento_origen_id=51, clave="c")

    podadas = podar_lineas_obsoletas_de_documento(db_session, expediente.id, 50, frozenset())

    assert podadas == 0
    assert db_session.get(LineaCatalogo, de_otro_documento.id) is not None


def test_podar_lineas_obsoletas_de_documento_no_toca_otro_expediente(db_session):
    expediente_1 = Expediente(codigo_expediente="6.24/28510.8886")
    expediente_2 = Expediente(codigo_expediente="6.24/28510.8885")
    db_session.add_all([expediente_1, expediente_2])
    db_session.commit()
    de_otro_expediente = _linea_directa(db_session, expediente_id=expediente_2.id, documento_origen_id=50, clave="d")

    podadas = podar_lineas_obsoletas_de_documento(db_session, expediente_1.id, 50, frozenset())

    assert podadas == 0
    assert db_session.get(LineaCatalogo, de_otro_expediente.id) is not None


def test_podar_lineas_obsoletas_de_documento_no_borra_heredada_de_matriz(db_session):
    # Una línea heredada de la matriz nunca debería aparecer bajo el
    # `documento_origen_id` que el PEDIDO procesa por su cuenta (ese
    # documento es de la matriz, CONTEXTO.md sección 3) -- pero se excluye
    # explícitamente igual, como red de seguridad barata.
    expediente = Expediente(codigo_expediente="6.24/28510.8884")
    db_session.add(expediente)
    db_session.commit()
    heredada = _linea_directa(
        db_session, expediente_id=expediente.id, documento_origen_id=50, clave="e", heredado_de_matriz=True
    )

    podadas = podar_lineas_obsoletas_de_documento(db_session, expediente.id, 50, frozenset())

    assert podadas == 0
    assert db_session.get(LineaCatalogo, heredada.id) is not None


def test_podar_lineas_obsoletas_de_documento_sin_nada_que_podar(db_session):
    expediente = Expediente(codigo_expediente="6.24/28510.8883")
    db_session.add(expediente)
    db_session.commit()

    assert podar_lineas_obsoletas_de_documento(db_session, expediente.id, 50, frozenset()) == 0


# --- Sesión 2026-09-15: marcas de origen y líneas heredadas obsoletas ---


def test_podar_lineas_heredadas_obsoletas_borra_las_que_la_herencia_ya_no_escribe(db_session):
    # `4.25/28510.0207`: heredó de `0124` las cuatro líneas del cuadro común
    # antes de saber que es el LOTE 1; ya no hereda, y las P-03/P-04 del
    # LOTE 2 seguían en su lote.
    expediente = Expediente(codigo_expediente="6.24/28510.8882")
    db_session.add(expediente)
    db_session.commit()
    sigue = _linea_directa(db_session, expediente_id=expediente.id, documento_origen_id=50, clave="f",
                           heredado_de_matriz=True)
    vieja = _linea_directa(db_session, expediente_id=expediente.id, documento_origen_id=50, clave="g",
                           heredado_de_matriz=True)
    propia = _linea_directa(db_session, expediente_id=expediente.id, documento_origen_id=50, clave="h")

    podadas = podar_lineas_heredadas_obsoletas(db_session, expediente.id, frozenset({sigue.id}))

    assert podadas == 1
    assert db_session.get(LineaCatalogo, vieja.id) is None
    assert db_session.get(LineaCatalogo, sigue.id) is not None
    assert db_session.get(LineaCatalogo, propia.id) is not None


def test_podar_lineas_heredadas_obsoletas_sin_herencia_borra_todas_las_heredadas(db_session):
    expediente = Expediente(codigo_expediente="6.24/28510.8881")
    db_session.add(expediente)
    db_session.commit()
    heredada = _linea_directa(db_session, expediente_id=expediente.id, documento_origen_id=50, clave="i",
                              heredado_de_matriz=True)

    assert podar_lineas_heredadas_obsoletas(db_session, expediente.id, frozenset()) == 1
    assert db_session.get(LineaCatalogo, heredada.id) is None


def _linea_guante(lote, **marcas):
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None,
             "precio_unitario": 2}
    linea = construir_linea_catalogo(["P-001", "Guante", "24,00"], mapeo, 11, None, lote.expediente_id, None, 0)
    linea.update(marcas)
    return linea


def test_guardar_lineas_catalogo_recalcula_las_marcas_de_origen_en_cada_pasada(db_session):
    # Con "un `None` no pisa un valor ya conocido", un `True` de una pasada
    # vieja se quedaba para siempre.
    lote = _lote(db_session)
    guardar_lineas_catalogo(db_session, lote.id, [_linea_guante(
        lote, heredado_de_matriz=True, lote_heredado_de_pagina_anterior=True, lote_del_expediente=True
    )])
    db_session.commit()

    guardar_lineas_catalogo(db_session, lote.id, [_linea_guante(
        lote, lote_heredado_de_pagina_anterior=None, lote_del_expediente=None
    )])
    db_session.commit()

    linea = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id).one()
    assert linea.heredado_de_matriz is None
    assert linea.lote_heredado_de_pagina_anterior is None
    assert linea.lote_del_expediente is None


def test_guardar_lineas_catalogo_marca_de_origen_en_la_misma_pasada_exige_acuerdo(db_session):
    # Dos documentos del mismo expediente escriben la misma línea en la
    # misma pasada: uno lee su lote en una cabecera, el otro lo hereda de
    # la página anterior. La línea no es "de lote heredado".
    lote = _lote(db_session)
    primera = guardar_lineas_catalogo(db_session, lote.id, [_linea_guante(lote)])
    db_session.commit()

    guardar_lineas_catalogo(
        db_session, lote.id, [_linea_guante(lote, lote_heredado_de_pagina_anterior=True)],
        ids_vivas=primera.ids_tocadas,
    )
    db_session.commit()

    linea = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id).one()
    assert linea.lote_heredado_de_pagina_anterior is None


def test_guardar_lineas_catalogo_no_rellena_marcas_de_origen_desde_la_fila_absorbida(db_session):
    lote = _lote(db_session)
    vieja = LineaCatalogo(
        expediente_id=lote.expediente_id, lote_id=lote.id, clave_linea="hash-viejo", orden_aparicion=0,
        descripcion="Guante", precio_unitario=Decimal("24.00"), heredado_de_matriz=True,
    )
    db_session.add(vieja)
    db_session.commit()

    guardar_lineas_catalogo(db_session, lote.id, [_linea_guante(lote)])
    db_session.commit()

    linea = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id).one()
    assert linea.clave_linea == "P-001"
    assert linea.heredado_de_matriz is None


# --- Sesión 2026-09-14 (revisión del cliente sobre el Excel) ---


def test_normalizar_codigo_precio_sufijo_de_variante_en_mayuscula_es_valido():
    # `6.21/28510.0109_ANEJO_7bfc92005f43e68e.pdf`: "P-39B", "P-41 A".
    assert _normalizar_codigo_precio("P-39B") == ("P-39B", None)
    assert _normalizar_codigo_precio("P-41 A") == ("P-41A", None)


def test_normalizar_codigo_precio_minuscula_pegada_sigue_sin_ser_valida():
    # "P-13\np": la "p" es el sello CSV invertido ("psj.adilav..."), no una
    # variante -- sigue su camino de siempre (conservado, con motivo).
    codigo, motivo = _normalizar_codigo_precio("P-13\np")
    assert motivo is not None
    assert codigo == "P-13p"


def test_normalizar_codigo_precio_conserva_el_sufijo_al_quitar_ruido_de_pie_de_pagina():
    # `6.21/28510.0109_ANEJO_ce1df15b39efdb8c.pdf` p.24-25, celdas reales: el
    # ruido comparte celda con el código; antes se perdía el sufijo y P-43 A,
    # P-43 B y P-43 acababan fundidos en una sola línea.
    assert _normalizar_codigo_precio("P-43 A\npsj")[0] == "P-43A"
    assert _normalizar_codigo_precio(".adilav/v\nP-43 B")[0] == "P-43B"
    assert _normalizar_codigo_precio("ne\nP-45 B elbaci")[0] == "P-45B"
    assert _normalizar_codigo_precio("fireV\nP-46 A")[0] == "P-46A"
    assert _normalizar_codigo_precio("V\nP-55 A")[0] == "P-55A"
    # Sin sufijo, la recuperación de siempre no cambia.
    assert _normalizar_codigo_precio("lbacifireV\nP-17")[0] == "P-17"
    assert _normalizar_codigo_precio("ptth\nP-16\nne\ne")[0] == "P-16"


def test_construir_linea_catalogo_codigo_material_de_la_columna_repuesto():
    # Decisión del cliente (sesión 2026-09-14): con columna REPUESTO, el
    # Código del material es su valor literal, no el derivado de la
    # descripción ("Corazón de punta móvil..." daría "CORAZÓN").
    mapeo = {
        "codigo_precio": 1, "matricula": None, "descripcion": 3, "unidad_medida": 6,
        "cantidad": None, "precio_unitario": 5, "codigo_material": 2,
    }
    fila = ["17.000", "P-69", "Cruzamiento", "Corazón de punta móvil para desvío", "11", "190.772,\n40", "€/UD"]
    linea = construir_linea_catalogo(
        fila, mapeo, pagina=23, documento_origen_id=588, expediente_id=1, baja_lote=None, orden_aparicion=0
    )
    assert linea["codigo_material"] == "CRUZAMIENTO"
    assert linea["precio_unitario"] == Decimal("190772.40")


def test_construir_linea_catalogo_repuesto_vacio_cae_a_la_descripcion():
    mapeo = {
        "codigo_precio": 1, "matricula": None, "descripcion": 3, "unidad_medida": 6,
        "cantidad": None, "precio_unitario": 5, "codigo_material": 2,
    }
    fila = ["Aparatos de dilatación", "P-35", "", "Conjunto aguja -contra-aguja para ADIH", "2,9", "62.186,25", "€/UD"]
    linea = construir_linea_catalogo(
        fila, mapeo, pagina=8, documento_origen_id=588, expediente_id=1, baja_lote=None, orden_aparicion=0
    )
    assert linea["codigo_material"] == "CONJUNTO"


def test_construir_linea_catalogo_descarta_plano_de_referencia_como_unidad():
    # `6.21/28510.0016_ANEJO_e40fc4e4546ec90b.pdf`: la columna "PLANO DE
    # REFERENCIA" acababa en unidad_medida.
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 2, "unidad_medida": 3, "cantidad": 4, "precio_unitario": 5}
    fila = ["642190360", "RT58", "ALMOHADILLA PARA AISLADORES", "03PAI-\n032-01", "100", "1,53 €"]
    linea = construir_linea_catalogo(
        fila, mapeo, pagina=13, documento_origen_id=495, expediente_id=1, baja_lote=None, orden_aparicion=0
    )
    assert linea["unidad_medida"] is None
    assert linea["matricula"] == "642190360"
    assert linea["cantidad"] == Decimal("100")
    assert "tres o más dígitos" in linea["motivo_revision"]


def test_construir_linea_catalogo_descarta_trozo_de_plano_cortado_como_unidad():
    # Misma tabla, fila partida a final de página: "03PME-" (la otra mitad,
    # "015-05", cae en la página siguiente) -- solo dos dígitos.
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 2, "unidad_medida": 3, "cantidad": 4, "precio_unitario": 5}
    fila = ["643550621", "RT62a", "ARANDELA", "03PME-", "200", "2,17 €"]
    linea = construir_linea_catalogo(
        fila, mapeo, pagina=13, documento_origen_id=495, expediente_id=1, baja_lote=None, orden_aparicion=0
    )
    assert linea["unidad_medida"] is None


def test_construir_linea_catalogo_unidad_real_con_un_digito_se_conserva():
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": 2, "cantidad": 3, "precio_unitario": 4}
    fila = ["P-8", "Acopio de material en fábrica", "€/Ton*mes", "500", "12,00"]
    linea = construir_linea_catalogo(
        fila, mapeo, pagina=49, documento_origen_id=586, expediente_id=1, baja_lote=None, orden_aparicion=0
    )
    # Sin el prefijo de la base del precio (decisión del cliente, sesión
    # 2026-09-15, quinta parte).
    assert linea["unidad_medida"] == "t·mes"
    fila_m3 = ["P-1", "Balasto sobre camión", "m3", "22.780,516", "12,40"]
    linea_m3 = construir_linea_catalogo(
        fila_m3, mapeo, pagina=30, documento_origen_id=319, expediente_id=1, baja_lote=None, orden_aparicion=0
    )
    assert linea_m3["unidad_medida"] == "m3"


def test_construir_linea_catalogo_matricula_escrita_con_puntos():
    # `6.21/28510.0016_ANEJO_e40fc4e4546ec90b.pdf` p.16: "643.910.630".
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 2, "unidad_medida": None, "cantidad": 4, "precio_unitario": 5}
    fila = ["643.910.630", "G51", "G51 GUARDACABOS P/PÉNDOLA EQUIPOT.", "03PPE-002", "1000", "0,40 €"]
    linea = construir_linea_catalogo(
        fila, mapeo, pagina=16, documento_origen_id=495, expediente_id=1, baja_lote=None, orden_aparicion=0
    )
    assert linea["matricula"] == "643910630"


def test_construir_linea_catalogo_matricula_en_la_columna_fantasma_de_al_lado():
    # `6.24/28510.0173_ANEJO_5b5c1a3f82caef4c.pdf` p.9, fila real: la matrícula
    # cae en la columna sin nombre junto a "MATRÍCULA".
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 3, "unidad_medida": None, "cantidad": 8, "precio_unitario": 6}
    fila = ["1", "", "663500010", "Ventilador SUNON DP200, 220-240V para puerta", None, "19,12 €", None, "1", None]
    linea = construir_linea_catalogo(
        fila, mapeo, pagina=9, documento_origen_id=817, expediente_id=1, baja_lote=None, orden_aparicion=0
    )
    assert linea["matricula"] == "663500010"
    assert "columna sin etiquetar junto a la de matrícula" in linea["motivo_revision"]


def test_construir_linea_catalogo_partida_alzada_con_importe_en_la_columna_de_cantidad():
    # `6.21/28510.0016_ANEJO_e40fc4e4546ec90b.pdf` p.18, fila real: la
    # partida alzada ocupa menos columnas -- texto en la de matrícula,
    # importe en la de cantidad, precio vacío.
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 2, "unidad_medida": None, "cantidad": 4, "precio_unitario": 5}
    fila = ["Partida alzada a justificar para imprevistos", None, None, None, "3.457,00 €", None]
    linea = construir_linea_catalogo(
        fila, mapeo, pagina=18, documento_origen_id=495, expediente_id=1, baja_lote=None, orden_aparicion=0
    )
    assert linea["descripcion"] == "Partida alzada a justificar para imprevistos"
    assert linea["precio_unitario"] == Decimal("3457.00")
    assert linea["cantidad"] is None


def test_construir_linea_catalogo_cantidad_imposible_se_descarta_sin_tumbar_el_documento():
    # `6.22/28510.0156` CONTRATO_1 (doc 702) p.123, fila real: una tabla de
    # aplicabilidad con un "1" en cada casilla, leída como una sola cantidad
    # de 15 dígitos -- no cabe en `lineas_catalogo.cantidad` y al guardar
    # tumbaba el documento entero.
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": None, "cantidad": 2, "precio_unitario": 3}
    fila = ["617050011", "SCV-V-60-II-1500 HORM", "111111111111111", None]
    linea = construir_linea_catalogo(
        fila, mapeo, pagina=123, documento_origen_id=702, expediente_id=1, baja_lote=None, orden_aparicion=0
    )
    assert linea["cantidad"] is None
    assert "cantidad descartada ('111111111111111')" in linea["motivo_revision"]


def test_construir_linea_catalogo_fila_de_solo_importes_es_relleno():
    # Misma tabla real (p.123): filas con el mismo importe repetido por
    # columnas, sin código, sin matrícula y sin ninguna letra -- no dicen qué
    # material son. Antes nunca llegaban a guardarse porque el documento
    # entero reventaba; con el documento ya guardándose, aparecían como
    # líneas sin descripción (error de la auditoría).
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": None, "cantidad": None, "precio_unitario": 7}
    fila = [None, None, None, None, None, None, None, "21.206,61 €", "21.206,61 €", "21.206,61 €"]
    assert construir_linea_catalogo(
        fila, mapeo, pagina=123, documento_origen_id=702, expediente_id=1, baja_lote=None, orden_aparicion=0
    ) is None


def test_construir_linea_catalogo_unidad_que_no_cabe_en_la_columna_se_descarta():
    # Misma fila real: la columna de unidad trae "UD." repetido una vez por
    # casilla (111 caracteres) -- no cabe en `unidad_medida` (32).
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": 2, "cantidad": None, "precio_unitario": 3}
    fila = ["617050011", "SCV-V-60-II-1500 HORM", " ".join(["UD."] * 28), "21.206,61 €"]
    linea = construir_linea_catalogo(
        fila, mapeo, pagina=123, documento_origen_id=702, expediente_id=1, baja_lote=None, orden_aparicion=0
    )
    assert linea["unidad_medida"] is None
    assert "unidad de medida descartada por larga (111 caracteres" in linea["motivo_revision"]


def test_combinar_por_clave_mismo_codigo_con_precios_distintos_no_se_atribuye():
    # `6.19/28510.0025_ANEJO_02234c396aba465d.pdf`: un "PRESUPUESTO ... LOTE N"
    # por lote en el mismo documento; en un expediente de un solo lote todas
    # las tablas caen en el mismo lote y "P-2" choca consigo mismo.
    base = {"expediente_id": 1, "matricula": None, "descripcion": "M3 de balasto transportado", "motivo_revision": None}
    lineas = [
        {**base, "clave_linea": "P-2", "codigo_precio": "P-2", "precio_unitario": Decimal("1.80"),
         "cantidad": Decimal("22780.516"), "precio_adjudicado": Decimal("1.70"), "pagina": 30},
        {**base, "clave_linea": "P-2", "codigo_precio": "P-2", "precio_unitario": Decimal("6.60"),
         "cantidad": Decimal("22780.516"), "precio_adjudicado": Decimal("6.20"), "pagina": 30},
    ]
    combinadas = _combinar_por_clave(lineas)
    assert len(combinadas) == 1
    assert combinadas[0]["precio_unitario"] is INVALIDADO
    assert combinadas[0]["precio_adjudicado"] is None
    assert combinadas[0]["cantidad"] == Decimal("22780.516")  # igual en las dos: no hay choque
    assert "precios unitarios distintos" in combinadas[0]["motivo_revision"]


def test_combinar_por_clave_mismo_codigo_con_mismo_precio_se_funde_sin_aviso():
    base = {"expediente_id": 1, "clave_linea": "P-1", "codigo_precio": "P-1", "matricula": None,
            "descripcion": "Balasto sobre camión a cantera", "motivo_revision": None, "pagina": 30}
    lineas = [
        {**base, "precio_unitario": Decimal("12.40"), "cantidad": None},
        {**base, "precio_unitario": Decimal("12.40"), "cantidad": Decimal("5")},
    ]
    combinadas = _combinar_por_clave(lineas)
    assert len(combinadas) == 1
    assert combinadas[0]["precio_unitario"] == Decimal("12.40")
    assert combinadas[0]["cantidad"] == Decimal("5")
    # Solo el aviso de siempre de fusión sin matrícula, nunca el de choque.
    assert "varias veces en el documento" not in (combinadas[0]["motivo_revision"] or "")


def test_guardar_lineas_catalogo_con_choque_de_precio_borra_el_valor_anterior(db_session):
    lote = _lote(db_session)
    base = {"expediente_id": lote.expediente_id, "clave_linea": "P-2", "codigo_precio": "P-2", "matricula": None,
            "descripcion": "M3 de balasto transportado", "orden_aparicion": 0, "motivo_revision": None}
    guardar_lineas_catalogo(db_session, lote.id, [{**base, "precio_unitario": Decimal("6.60")}])
    db_session.commit()

    guardar_lineas_catalogo(db_session, lote.id, [
        {**base, "precio_unitario": Decimal("1.80"), "pagina": 30},
        {**base, "precio_unitario": Decimal("6.60"), "pagina": 30},
    ])
    db_session.commit()

    fila = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id, clave_linea="P-2").one()
    assert fila.precio_unitario is None
    assert "precios unitarios distintos" in fila.motivo_revision
    # Sesión 2026-09-14 (continuación): el motivo guardado dice qué campo
    # quedó vacío por la guarda -- es lo que usa `app.celdas_vacias`.
    assert campos_vacios_por_valor_de_otro_lote(fila.motivo_revision) == {"precio_unitario"}


def test_campos_vacios_por_valor_de_otro_lote_lee_el_motivo_de_la_guarda():
    base = {"expediente_id": 1, "clave_linea": "P-8", "codigo_precio": "P-8", "matricula": None,
            "descripcion": "Traviesa", "motivo_revision": None, "pagina": 4}
    combinadas = _combinar_por_clave([
        {**base, "precio_unitario": Decimal("80"), "cantidad": Decimal("700")},
        {**base, "precio_unitario": Decimal("95"), "cantidad": Decimal("650")},
    ])
    assert campos_vacios_por_valor_de_otro_lote(combinadas[0]["motivo_revision"]) == {"cantidad", "precio_unitario"}
    assert campos_vacios_por_valor_de_otro_lote("banda vacía: posible continuación") == frozenset()
    assert campos_vacios_por_valor_de_otro_lote(None) == frozenset()


def test_unidad_partida_por_el_ancho_de_columna_se_une():
    from app.catalogo import _unir_unidad_partida

    assert _unir_unidad_partida("m3x\nkm") == "m3xkm"
    assert _unir_unidad_partida("€/transport\ne") == "€/transporte"
    assert _unir_unidad_partida("t x\nkm") == "t x\nkm"
    assert _unir_unidad_partida("Precio\nmensual") == "Precio\nmensual"
    assert _unir_unidad_partida("ud\nud\nud") == "ud\nud\nud"
    assert _unir_unidad_partida("UD.") == "UD."


def test_cantidad_y_unidad_juntas_en_la_columna_de_unidad():
    # `6.21/28510.0041`, ANEJO p.3: "Mat. | Designación | Medición estimada |
    # Precio unitario | IMPORTE"; la medición y su unidad caen en la columna
    # que el mapeo da por unidad, y la de cantidad viene vacía.
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": 2, "cantidad": 3,
             "precio_unitario": 5}
    fila = ["601061018", "CARRIL 60E1 R350 SIN TALADRAR 18 M", "2211,67 m", None, None, "49,39 €", None, None,
            "109.238,72 €"]

    linea = construir_linea_catalogo(fila, mapeo, 3, None, 1, None, 0)

    assert linea["cantidad"] == Decimal("2211.67")
    assert linea["unidad_medida"] == "m"
    assert linea["precio_unitario"] == Decimal("49.39")
    assert "misma celda" in linea["motivo_revision"]


def test_unidad_que_no_es_una_unidad_conocida_se_descarta_con_motivo():
    # `6.24/28510.0125_CONTRATO_80584833e422c1ec.pdf` p.99: el mapeo del
    # modelo tomaba la columna "CARACTERÍSTICAS" por unidad.
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": 3, "cantidad": 4,
             "precio_unitario": 2}
    fila = ["666050009", "Pigtail SC/UPC 0,9 mm.", "4,09 €", "Fibra monomodo", "1", None]

    linea = construir_linea_catalogo(fila, mapeo, 99, None, 1, None, 0)

    assert linea["unidad_medida"] is None
    assert linea["matricula"] == "666050009"
    assert linea["precio_unitario"] == Decimal("4.09")
    assert "no ser una unidad conocida" in linea["motivo_revision"]
    assert "'Fibra monomodo'" in linea["motivo_revision"]


def test_precio_mensual_en_la_columna_de_unidad_se_descarta():
    # `4.26/28510.0020_ANEJO_8f2a33dd634a5454.pdf` p.14: el documento escribe
    # "Precio mensual" en la columna "Ud.".
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 8, "unidad_medida": 4, "cantidad": 5,
             "precio_unitario": 11}
    fila = ["P-1", None, None, None, "Precio\nmensual", "48", None, "",
            "Responsable Técnico de los Trabajos", "", "", "10.805,22 €"]

    linea = construir_linea_catalogo(fila, mapeo, 14, None, 1, None, 0)

    assert linea["unidad_medida"] is None
    assert linea["cantidad"] == Decimal("48")
    assert "no ser una unidad conocida" in linea["motivo_revision"]


def test_cabecera_repetida_en_mitad_de_la_tabla_no_es_una_linea():
    # `4.26/28510.0031_ANEJO_2296757d97322ecf.pdf` p.7: segunda sección de la
    # tabla con su propia fila de cabecera.
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": 2, "cantidad": None,
             "precio_unitario": 4}
    cabecera = ["CODIGO", "DESCRIPCIÓN", "UNIDAD", "MEDICIÓN", "Precio\nUnitario", "IMPORTE"]
    datos = ["P2.01", "Mantenimiento anual de cada\nestufa *", "Ud.", "12", "580,00 €", "6.960,00 €"]

    assert construir_linea_catalogo(cabecera, mapeo, 7, None, 1, None, 0) is None
    linea = construir_linea_catalogo(datos, mapeo, 7, None, 1, None, 1)
    assert linea["descripcion"] == "Mantenimiento anual de cada estufa *"
    assert linea["precio_unitario"] == Decimal("580.00")


def test_partida_alzada_con_un_signo_delante_en_la_columna_de_matricula():
    # `6.25/28510.0257_CONTRATO` p.20: "CÓDIGO ADIF" mapeada como matrícula por
    # contenido, y el texto de la partida alzada cae en ella con el "∅" del
    # sello lateral de verificación delante.
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": 7,
             "precio_unitario": 8}
    fila = ["ilav/\nP-22", "∅\nPartida alzada a justificar para imprevistos", None, None, None, None, None, None,
            "25.200,00 €"]

    linea = construir_linea_catalogo(fila, mapeo, 20, None, 1, None, 0)

    assert linea["descripcion"] == "Partida alzada a justificar para imprevistos"
    assert linea["matricula"] is None
    assert linea["codigo_precio"] == "P-22"
    assert linea["precio_unitario"] == Decimal("25200.00")


def test_unidad_sin_prefijo_de_precio_ni_llamada_de_nota():
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": 2, "cantidad": 3,
             "precio_unitario": 4}
    # `6.21/28510.0108`: la columna de unidad trae la base del precio.
    fila_euro = ["P-35", "Conjunto aguja-contraaguja para ADIH", "€/UD", "2,9", "62.186,25"]
    # `6.24/28510.0088` p.23: "dm3**", con la llamada a una nota al pie.
    fila_nota = ["P-001", "Traviesa sin sujeción de pino", "dm3**", None, "1,00"]
    # `6.21/28510.0108`: unidad partida por el ancho de columna.
    fila_partida = ["P-40", "Transporte por camión especial", "€/transport\ne", "1", "900,00"]

    assert construir_linea_catalogo(fila_euro, mapeo, 8, None, 1, None, 0)["unidad_medida"] == "ud"
    linea_nota = construir_linea_catalogo(fila_nota, mapeo, 23, None, 1, None, 0)
    assert linea_nota["unidad_medida"] == "dm3"
    assert not (linea_nota["motivo_revision"] or "").count("unidad")
    assert construir_linea_catalogo(fila_partida, mapeo, 8, None, 1, None, 0)["unidad_medida"] == "transporte"


def test_material_llamado_como_una_etiqueta_con_precio_no_es_cabecera():
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": 2, "cantidad": None,
             "precio_unitario": 3}
    fila = ["P-1", "Concepto", "Ud.", "12,00 €"]

    linea = construir_linea_catalogo(fila, mapeo, 1, None, 1, None, 0)

    assert linea is not None
    assert linea["precio_unitario"] == Decimal("12.00")


def test_construir_linea_catalogo_acepta_matricula_antigua_de_8_cifras():
    # Sesión 2026-09-17, decisión del cliente: `6.20/28510.0041` p.35,
    # "71590012 RODILLO DE AGUJA ZR 1E", se guardaba sin matrícula.
    mapeo = {"codigo_precio": None, "matricula": 0, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    linea = construir_linea_catalogo(
        ["71590012", "RODILLO DE AGUJA ZR 1E INCLUSO SOPORTE", "210,00 €"], mapeo,
        pagina=35, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0,
    )
    assert linea["matricula"] == "71590012"


def test_construir_linea_catalogo_descarta_resumen_de_presupuesto_al_pie():
    # Sesión 2026-09-17, `6.17/28510.0056` p.19 (leído por reconocimiento
    # óptico): el resumen del presupuesto bajo el cuadro entraba como cinco
    # líneas sin descripción, con importes de millones.
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": 2, "cantidad": None, "precio_unitario": 3}
    for etiqueta, importe in (
        ("Presupuesto de Ejecución Material", "2.975.673,96 €"),
        ("Gastos Generales (9%)", "267.810,66 €"),
        ("Beneficio Industrial (6%)", "178.540,44 €"),
        ("Suma", "3.422.025,06 €"),
        ("Presupuesto Base de Licitación", "4.140.650,32 €"),
    ):
        linea = construir_linea_catalogo(
            [etiqueta, "", "", importe, ""], mapeo,
            pagina=19, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0,
        )
        assert linea is None, etiqueta


def test_construir_linea_catalogo_descarta_concepto_de_presupuesto_en_la_descripcion():
    # Sesión 2026-09-17 (aviso del cliente): variantes reales del corpus con la
    # etiqueta en la columna de descripción, leídas como líneas de millones.
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": 2, "precio_unitario": 3}
    for etiqueta, importe in (
        ("Presupuesto Base de Licitación", "3.305.653,05 €"),        # 6.17/28510.0056
        ("Suma", "2.731.944,67 €"),
        ("IVA (21%)", "573.708,38 €"),
        ("PRESUPUESTO DE EJECUCIÓN MATERIAL", "993.714,32 €"),         # 6.17/28510.0007
        ("9% GASTOS GENERALES", "89.434,29 €"),
        ("6% BENEFICIO INDUSTRIAL", "59.622,86 €"),
        ("TOTAL PRESUPUESTO", "1.382.753,68 €"),
        ("Suma (€ Ejecución por Contrata)", "50.713,00"),              # 3.21/28510.0052
        ("Presupuesto Base de Licitación (€ IVA incluido)", "61.362,73"),
        ("TOTAL PRESUPUESTO DE LICITACIÓN CON IVA", "104.233,09 €"),   # 6.17/28510.0123
        ("Total", "70.000,00"),                                         # 6.23/28510.0105
    ):
        linea = construir_linea_catalogo(
            ["", etiqueta, "", importe], mapeo,
            pagina=20, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0,
        )
        assert linea is None, etiqueta


def test_construir_linea_catalogo_conserva_material_que_menciona_el_presupuesto():
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": 2, "precio_unitario": 3}
    for descripcion in ("Suministro de balasto según presupuesto de ejecución", "TORNILLO TOTAL M24X100", "Partida alzada total"):
        linea = construir_linea_catalogo(
            ["P-01", descripcion, "1", "120,00 €"], mapeo,
            pagina=1, documento_origen_id=None, expediente_id=1, baja_lote=None, orden_aparicion=0,
        )
        assert linea is not None, descripcion
