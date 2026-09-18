"""CONTEXTO.md, encargo de esta sesión (Excel al cliente), punto 1: ninguna
convención de marcador de texto de la web viaja al Excel -- celda vacía en
su lugar, para no convertir una columna numérica en texto mixto."""
import io
from decimal import Decimal

from app.exportacion import (
    _CATEGORIA_DUPLICADO_SIN_PERDIDA,
    _CATEGORIAS_MOTIVO,
    _EXPLICACIONES_MOTIVO,
    _categoria_motivo,
    _celda_matricula,
    _celda_numero,
    _celda_texto,
    _celda_texto_o_espacio,
    _escribir_resumen,
    _formato_cantidad,
    generar_excel_catalogo,
)
from app.models import Expediente, Lote, LineaCatalogo
from collections import Counter

import openpyxl
from openpyxl import Workbook


def _linea(**kwargs) -> LineaCatalogo:
    base = dict(
        expediente_id=1, clave_linea="P-001", orden_aparicion=0,
        descripcion="BRIDA DE UNIÓN", matricula=None,
    )
    base.update(kwargs)
    return LineaCatalogo(**base)


def test_celda_matricula_presente():
    assert _celda_matricula(_linea(matricula="601020180")) == "601020180"


def test_celda_matricula_partida_alzada_vacia():
    linea = _linea(descripcion="Partida alzada a justificar para imprevistos")
    assert _celda_matricula(linea) is None


def test_celda_matricula_ausente_vacia():
    linea = _linea(descripcion="BRIDA DE UNIÓN")
    assert _celda_matricula(linea) is None


def test_celda_texto_vacio_es_none():
    assert _celda_texto(None) is None
    assert _celda_texto("") is None
    assert _celda_texto("L01") == "L01"


def test_celda_numero_vacio_es_none():
    assert _celda_numero(None) is None


def test_celda_numero_devuelve_float():
    assert _celda_numero(Decimal("0")) == 0.0
    assert _celda_numero(Decimal("12.5")) == 12.5


# Bloque 2, revisión del cliente: la columna Cantidad mostraba "20.000." (un
# punto colgando tras un valor entero) con la máscara "#,##0.###" anterior.
def test_formato_cantidad_entero_sin_punto():
    assert _formato_cantidad(Decimal("20000")) == "#,##0"
    assert _formato_cantidad(Decimal("20000.000")) == "#,##0"
    assert _formato_cantidad(Decimal("0")) == "#,##0"


def test_formato_cantidad_ausente_sin_punto():
    assert _formato_cantidad(None) == "#,##0"


# Bloque 2, segunda tanda de cambios del cliente tras revisar el catálogo:
# una celda de texto vacía del todo deja que Excel desborde encima el texto
# de la celda anterior -- un espacio lo evita. Solo en columnas de texto,
# nunca en las numéricas (_celda_numero, sin cambios: sigue devolviendo
# None, nunca un espacio que las convertiría en texto mixto).
def test_celda_texto_o_espacio_vacio_da_un_espacio():
    assert _celda_texto_o_espacio(None) == " "
    assert _celda_texto_o_espacio("") == " "


def test_celda_texto_o_espacio_presente_se_deja_igual():
    assert _celda_texto_o_espacio("L01") == "L01"


def test_celda_numero_sigue_devolviendo_none_nunca_espacio():
    assert _celda_numero(None) is None


def test_formato_cantidad_con_decimales_significativos():
    assert _formato_cantidad(Decimal("12.5")) == "#,##0.0"
    assert _formato_cantidad(Decimal("0.142")) == "#,##0.000"
    assert _formato_cantidad(Decimal("3.50")) == "#,##0.0"


def test_formato_cantidad_capa_en_tres_decimales():
    # `lineas_catalogo.cantidad` es NUMERIC(14,3): nunca debería llegar un
    # cuarto decimal significativo, pero el formato no debe reventar si lo
    # hiciera -- capa en 3, la precisión real de la columna.
    assert _formato_cantidad(Decimal("1.2345")) == "#,##0.000"


# Encargo de esta sesión: agrupar el motivo de las huérfanas excluidas del
# Excel en un puñado de categorías legibles (docstring de
# `app.extraccion.lote_tabla`, mismas cuatro redacciones reales).


def test_categoria_motivo_banda_vacia():
    motivo = "banda vacía: posible continuación de tabla partida entre páginas, sin inferir"
    assert _categoria_motivo(motivo) == "banda vacía: posible continuación de tabla partida entre páginas"


def test_categoria_motivo_varias_cabeceras():
    motivo = "varias cabeceras de lote en la franja que precede a esta tabla: ['2', '4']"
    assert _categoria_motivo(motivo) == "varias cabeceras de lote en la misma franja"


def test_categoria_motivo_ninguna_cabecera():
    motivo = "ninguna cabecera LOTE N encontrada en la franja que precede a esta tabla"
    assert _categoria_motivo(motivo) == "ninguna cabecera de lote reconocible en la franja"


def test_categoria_motivo_lote_no_declarado():
    motivo = "la tabla se asocia al LOTE 9, que no está entre los lotes declarados del expediente"
    assert _categoria_motivo(motivo) == "la tabla declara un lote no registrado en el expediente"


def test_categoria_motivo_anejo_de_criterios_y_seccion_de_otro_lote():
    # Sesión 2026-09-14, tercera parte.
    from app.extraccion.lote_tabla import MOTIVO_TABLA_DEL_CONJUNTO

    assert _categoria_motivo(MOTIVO_TABLA_DEL_CONJUNTO) == "anejo de criterios técnicos, común a todos los lotes"
    motivo = (
        "tabla sin cabecera de lote, pero la última mención de lote antes de ella es la del LOTE 1, no la de "
        "este expediente (LOTE 4): no se le atribuye"
    )
    assert _categoria_motivo(motivo) == "tabla sin título de lote, detrás de la sección de otro lote"


def test_categoria_motivo_sin_registrar():
    assert _categoria_motivo(None) == "sin_motivo_registrado"


def test_categoria_motivo_desconocido_cae_en_otro():
    assert _categoria_motivo("una redacción nueva que no existía todavía") == "otro_motivo_ambiguedad"


# Encargo de esta sesión, punto 4: la hoja "Resumen" tiene que explicarse en
# lenguaje llano, no en la jerga interna de `motivo_revision`. Cada categoría
# (incluidas las dos que caen por defecto, "otro" y "sin motivo") debe tener
# una explicación y una resolución no vacías, y ninguna de las dos puede
# arrastrar jerga del sistema (nombres de función, "motivo_revision", etc.).


def test_todas_las_categorias_tienen_explicacion_llana():
    categorias = {categoria for _marcador, categoria, _explicacion, _resolucion in _CATEGORIAS_MOTIVO}
    categorias |= {"otro_motivo_ambiguedad", "sin_motivo_registrado"}
    for categoria in categorias:
        explicacion, resolucion = _EXPLICACIONES_MOTIVO[categoria]
        assert explicacion.strip()
        assert resolucion.strip()
        assert "motivo_revision" not in explicacion
        assert "motivo_revision" not in resolucion


def test_escribir_resumen_incluye_motivos_en_lenguaje_llano():
    libro = Workbook()
    excluidas = Counter({"banda vacía: posible continuación de tabla partida entre páginas": 5})
    _escribir_resumen(libro, incluidas=10, excluidas_por_categoria=excluidas, incluir_pendientes_sin_lote=False)
    hoja = libro["Resumen"]
    textos = [str(celda.value) for fila in hoja.iter_rows() for celda in fila if celda.value is not None]
    contenido = "\n".join(textos)
    assert "parece continuar de una página a la siguiente" in contenido
    assert "abra el documento original" in contenido
    assert "Código del material" in contenido


def test_escribir_resumen_sin_pendientes_incluye_nota_codigo_material():
    libro = Workbook()
    _escribir_resumen(libro, incluidas=10, excluidas_por_categoria=Counter(), incluir_pendientes_sin_lote=False)
    hoja = libro["Resumen"]
    textos = [str(celda.value) for fila in hoja.iter_rows() for celda in fila if celda.value is not None]
    assert any("Código del material" in texto for texto in textos)


# --- Categoría "duplicado de material ya incluido" (encargo de sesión,
# hallazgo real `6.22/28510.0033`/`0057`/`0058`: un anejo de "criterios
# técnicos" repite íntegro el mismo cuadro de precios que otro documento del
# expediente ya trae, con lote asignado -- 603 líneas reales del corpus en
# este caso, verificadas antes de escribir el código). Nunca funde las dos
# líneas ni le asigna lote a la huérfana: solo cambia bajo qué categoría del
# Resumen se cuenta.


def _expediente_con_lote(db_session, codigo_expediente: str = "6.24/28510.9999"):
    expediente = Expediente(codigo_expediente=codigo_expediente)
    db_session.add(expediente)
    db_session.commit()
    lote = Lote(expediente_id=expediente.id, identificador_lote="1")
    db_session.add(lote)
    db_session.commit()
    return expediente, lote


def test_generar_excel_cuenta_huerfana_identica_como_duplicado_sin_perdida(db_session):
    expediente, lote = _expediente_con_lote(db_session)
    incluida = LineaCatalogo(
        expediente_id=expediente.id, lote_id=lote.id, clave_linea="601200010",
        orden_aparicion=0, matricula="601200010",
        descripcion="TORNILLO BRIDA Nº 1, C/T Y ARANDELA PLANA", precio_unitario=Decimal("4.29"),
    )
    huerfana_identica = LineaCatalogo(
        expediente_id=expediente.id, lote_id=None, clave_linea="hash-huerfana-1",
        orden_aparicion=1, matricula="601200010",
        descripcion="TORNILLO BRIDA Nº 1, C/T Y ARANDELA PLANA", precio_unitario=Decimal("4.29"),
        motivo_revision="ninguna cabecera LOTE N encontrada en la franja que precede a esta tabla",
    )
    db_session.add_all([incluida, huerfana_identica])
    db_session.commit()

    contenido = generar_excel_catalogo(db_session)
    libro = openpyxl.load_workbook(io.BytesIO(contenido))

    materiales = libro["Materiales"]
    assert materiales.max_row == 2  # cabecera + la única línea incluida

    resumen = libro["Resumen"]
    textos = [str(c.value) for fila in resumen.iter_rows() for c in fila if c.value is not None]
    contenido_resumen = "\n".join(textos)
    assert "duplicado" in contenido_resumen.lower()
    assert "ya aparece en la hoja" in contenido_resumen

    # La huérfana sigue exactamente igual en base de datos: sin lote, sin
    # fundir con la otra línea -- solo cambia cómo se cuenta en el Resumen.
    db_session.refresh(huerfana_identica)
    assert huerfana_identica.lote_id is None


def test_generar_excel_no_confunde_huerfana_distinta_con_duplicado(db_session):
    expediente, lote = _expediente_con_lote(db_session)
    incluida = LineaCatalogo(
        expediente_id=expediente.id, lote_id=lote.id, clave_linea="601200010",
        orden_aparicion=0, matricula="601200010",
        descripcion="TORNILLO BRIDA Nº 1, C/T Y ARANDELA PLANA", precio_unitario=Decimal("4.29"),
    )
    # Misma matrícula y descripción, precio distinto -- un material real que
    # cambió de precio no es "la misma línea otra vez", así que no debe
    # contarse como duplicado sin pérdida.
    huerfana_precio_distinto = LineaCatalogo(
        expediente_id=expediente.id, lote_id=None, clave_linea="hash-huerfana-2",
        orden_aparicion=1, matricula="601200010",
        descripcion="TORNILLO BRIDA Nº 1, C/T Y ARANDELA PLANA", precio_unitario=Decimal("9.99"),
        motivo_revision="ninguna cabecera LOTE N encontrada en la franja que precede a esta tabla",
    )
    db_session.add_all([incluida, huerfana_precio_distinto])
    db_session.commit()

    contenido = generar_excel_catalogo(db_session)
    libro = openpyxl.load_workbook(io.BytesIO(contenido))
    resumen = libro["Resumen"]
    textos = [str(c.value) for fila in resumen.iter_rows() for c in fila if c.value is not None]
    contenido_resumen = "\n".join(textos)
    assert "duplicado" not in contenido_resumen.lower()
    assert "no indica en ningún sitio cercano a qué lote pertenece" in contenido_resumen


# --- Bloque 1, sesión 2026-09-18: "Código de expediente" siempre relleno -----
# El cruce con el Excel de códigos de ADIF actuaba de interruptor sobre esa
# columna: sin cruce salía vacía aunque el número se conociera perfectamente,
# y el cliente filtraba por ella y concluía que faltaban expedientes que sí
# están. El cruce sigue gobernando "Código interno", "Código matriz" y
# "Estado del contrato (SAP)".


def _fila_unica(db_session, **campos_expediente):
    expediente = Expediente(codigo_expediente="6.26/28510.0016", **campos_expediente)
    db_session.add(expediente)
    db_session.commit()
    lote = Lote(expediente_id=expediente.id, identificador_lote="1")
    db_session.add(lote)
    db_session.commit()
    db_session.add(LineaCatalogo(
        expediente_id=expediente.id, lote_id=lote.id, clave_linea="P-001", orden_aparicion=0,
        codigo_precio="P-001", matricula="601200010", descripcion="TORNILLO BRIDA",
        precio_unitario=Decimal("4.29"),
    ))
    db_session.commit()
    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    hoja = libro["Materiales"]
    cabecera = [c.value for c in next(hoja.iter_rows())]
    valores = [c.value for c in list(hoja.iter_rows())[1]]
    return dict(zip(cabecera, valores)), libro


def test_codigo_de_expediente_se_rellena_aunque_no_cruce(db_session):
    fila, _ = _fila_unica(db_session, codigos_cruzados=False)
    assert fila["Código de expediente"] == "6.26/28510.0016"
    # Y coincide con la columna que siempre trajo el dato del documento.
    assert fila["Nº de expediente (documento)"] == "6.26/28510.0016"


def test_sin_cruce_las_otras_tres_columnas_siguen_vacias(db_session):
    fila, _ = _fila_unica(db_session, codigos_cruzados=False)
    assert fila["Código interno"] == " "
    assert fila["Código matriz"] == " "
    assert fila["Estado del contrato (SAP)"] == " "


def test_con_cruce_las_cuatro_columnas_se_rellenan(db_session):
    fila, _ = _fila_unica(
        db_session, codigos_cruzados=True, codigo_interno="24036",
        codigo_matriz="6.25/28510.0016", estado_contrato_sap="En ejecución",
    )
    assert fila["Código de expediente"] == "6.26/28510.0016"
    assert fila["Código interno"] == "24036"
    assert fila["Código matriz"] == "6.25/28510.0016"
    assert fila["Estado del contrato (SAP)"] == "En ejecución"


# --- Bloque 2: motivo para las celdas vacías de las columnas del expediente --


def test_las_columnas_del_expediente_vacias_llevan_motivo(db_session):
    fila, _ = _fila_unica(db_session, codigos_cruzados=False)
    motivo = fila["Motivo de las celdas vacías"]
    assert "Código interno: no consta" in motivo
    assert "Código matriz: no consta" in motivo
    assert "Estado del contrato (SAP): no consta" in motivo
    assert "Título expediente y Objeto del contrato (documento): no consta" in motivo
    # "Código de expediente" ya no puede quedar vacía, así que nunca aparece.
    assert "Código de expediente:" not in motivo


def test_expediente_completo_no_genera_motivos_de_sus_columnas(db_session):
    fila, _ = _fila_unica(
        db_session, codigos_cruzados=True, codigo_interno="24036",
        codigo_matriz="6.25/28510.0016", estado_contrato_sap="En ejecución",
        nombre_proyecto="Suministro de carril",
    )
    motivo = fila["Motivo de las celdas vacías"] or ""
    for columna in ("Código interno", "Código matriz", "Estado del contrato (SAP)", "Título expediente"):
        assert f"{columna}:" not in motivo


# --- Bloque 3, segunda parte: la nota doble del Resumen ---------------------


def test_resumen_explica_las_dos_formas_de_material_repetido():
    libro = Workbook()
    _escribir_resumen(libro, incluidas=10, excluidas_por_categoria=Counter(), incluir_pendientes_sin_lote=False)
    contenido = "\n".join(
        str(c.value) for fila in libro["Resumen"].iter_rows() for c in fila if c.value is not None
    )
    # 1) entre expedientes de la misma licitación, por compartir cuadro
    assert "comparten el mismo" in contenido or "compartir el mismo" in contenido
    assert "cuadro de precios" in contenido
    # 2) dentro de un mismo expediente, por dos códigos de precio distintos
    assert "dos códigos de" in contenido and "precio distintos" in contenido
    # y la promesa de que no se toca nada
    assert "no se junta ni se elimina ninguna" in contenido


def test_resumen_explica_por_que_comentarios_va_vacia():
    libro = Workbook()
    _escribir_resumen(libro, incluidas=10, excluidas_por_categoria=Counter(), incluir_pendientes_sin_lote=False)
    contenido = "\n".join(
        str(c.value) for fila in libro["Resumen"].iter_rows() for c in fila if c.value is not None
    )
    assert "Comentarios" in contenido
    assert "escriba en ella quien revise" in contenido
