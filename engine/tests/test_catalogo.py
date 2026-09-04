from decimal import Decimal

from app.catalogo import (
    _combinar_por_clave,
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
