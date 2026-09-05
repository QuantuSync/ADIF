from decimal import Decimal

from app.catalogo import (
    _combinar_por_clave,
    _normalizar_codigo_precio,
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
    # matrícula. CLAUDE.md sección 2: la partida alzada es una línea
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
    # mapear. Sin matrícula que perder (partida alzada, CLAUDE.md sección 2),
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
    # CLAUDE.md sección 26 (arreglo de los 3 que seguían en revisión tras el
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
    # (CLAUDE.md sección 17.2, "sin columna de precio ni de cantidad" es un
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
    # CLAUDE.md, sesión de rodaje 2026-09-03: un valor de precio que no se
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
    # CLAUDE.md, sesión de rodaje 2026-09-03, punto 3: antes esta función
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
    # CLAUDE.md sección 9.9: idempotencia. Reprocesar el mismo expediente
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
    # mismo cuadro de precios reaparece en el documento — CLAUDE.md sección
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
    # CLAUDE.md, encargo de esta sesión, punto 3 (ajuste 1 del usuario): una
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
    assert lineas[0].cantidad == Decimal("14")  # dato heredado de la segunda fila absorbida
