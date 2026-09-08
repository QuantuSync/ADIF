from decimal import Decimal

from app.catalogo import (
    _combinar_por_clave,
    _normalizar_codigo_precio,
    buscar_posible_duplicado_huerfana,
    calcular_clave_linea,
    construir_linea_catalogo,
    construir_lineas_desde_tabla,
    guardar_lineas_catalogo,
)
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
    assert {linea["codigo_precio"] for linea in lineas} == {"P-0058", "P-0059"}
    assert all(linea["precio_unitario"] == Decimal("306351.49") for linea in lineas)


def test_combinar_por_clave_no_funde_dos_lineas_de_la_misma_fila_fusionada():
    # Defecto encontrado verificando el arreglo de la fila fusionada contra
    # la base de datos real (expediente 18, lote 179): separar la fila en
    # P-0058 y P-0059 no bastaba. Las dos líneas salen con la MISMA
    # descripción (el bloque entero de la fila, que nunca se reparte a
    # ciegas), sin matrícula, y con el mismo precio -- firma de material
    # idéntica, así que `_combinar_por_clave` volvía a fundirlas en una
    # sola: en la base de datos quedaba UNA fila, con `clave_linea="P-0058"`
    # y `codigo_precio="P-0059"`, y el material P-0058 desaparecía del
    # catálogo entero. El mismo fallo que el arreglo venía a corregir, un
    # paso más allá y con peor pinta (la línea superviviente parece
    # correcta). `_firma_material` no da firma a estas líneas.
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
    lineas = construir_lineas_desde_tabla(tabla, mapeo, None, expediente_id=18, baja_lote=None, orden_inicial=0)

    combinadas = _combinar_por_clave(lineas)

    assert len(combinadas) == 2
    assert {linea["codigo_precio"] for linea in combinadas} == {"P-0058", "P-0059"}
    assert {linea["clave_linea"] for linea in combinadas} == {"P-0058", "P-0059"}


def test_guardar_lineas_catalogo_no_pierde_un_codigo_de_una_fila_fusionada(db_session):
    # El mismo defecto, comprobado donde de verdad dolía: contra la base de
    # datos. Antes del arreglo esto guardaba una sola fila; ahora guarda los
    # dos materiales reales, cada uno con su código como clave y los dos
    # marcados para revisión (su descripción es el bloque compartido de la
    # fila del documento, hay que confirmarla contra el original).
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
    assert all(linea.precio_unitario == Decimal("306351.49") for linea in guardadas)
    assert all("fusionaba" in (linea.motivo_revision or "") for linea in guardadas)


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
    assert linea["unidad_medida"] == "M"


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
