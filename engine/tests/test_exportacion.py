"""CONTEXTO.md, encargo de esta sesión (Excel al cliente), punto 1: ninguna
convención de marcador de texto de la web viaja al Excel -- celda vacía en
su lugar, para no convertir una columna numérica en texto mixto."""
import io
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.conciliacion import (
    ACUERDO_MARCO_SIN_PRECIOS,
    APORTA_LINEAS,
    PUBLICADO_EN_FICHA_DE_OTRO,
    COLUMNAS_CONCILIACION,
    DescuadreConciliacion,
    FilaConciliacion,
    PENDIENTE_DE_PROCESAR,
    PRECIOS_EN_ACUERDO_MARCO,
    SIN_CUADRO,
    ESCANEADO_ILEGIBLE,
    OTRO,
    SITUACIONES,
    comprobar_cuadre,
)
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
from app.models import (
    CacheOcrDocumento,
    Documento,
    DocumentoExpediente,
    EstadoExpediente,
    Expediente,
    LineaCatalogo,
    Lote,
    SindicacionExpediente,
    TipoDocumento,
)
from collections import Counter

import openpyxl
from openpyxl import Workbook
from sqlalchemy import select

_AHORA = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)


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


def test_no_queda_una_segunda_columna_con_el_numero_de_expediente(db_session):
    """Bloque 1, sesión 2026-09-18 (decisión del cliente): "Nº de expediente
    (documento)" existía porque "Código de expediente" solo se rellenaba
    cuando el expediente cruzaba con el Excel de códigos. Desde que esa
    puerta desapareció las dos salían del mismo campo, así que se queda una
    sola -- y con el nombre por el que el cliente filtra."""
    fila, _ = _fila_unica(db_session, codigos_cruzados=False)
    assert "Nº de expediente (documento)" not in fila
    assert [c for c in fila if "6.26/28510.0016" == fila[c]] == ["Código de expediente"]


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


# --- Bloque 2, sesión 2026-09-18: el "Código interno" no se hereda de la ----
# fila de otro expediente. La celda queda vacía y su motivo lo dice en
# castellano llano, para quien lo busca en almacenes.


def test_codigo_interno_vacio_por_fila_ajena_lo_explica_para_almacenes(db_session):
    fila, _ = _fila_unica(db_session, codigos_cruzados=True, cruce_fila_propia=False)
    assert fila["Código interno"] == " "
    motivo = fila["Motivo de las celdas vacías"]
    assert "Código interno: no consta (este expediente no figura por sí mismo en el listado de " \
           "códigos de ADIF)" in motivo


def test_codigo_interno_vacio_cruzando_por_fila_propia_dice_otra_cosa(db_session):
    fila, _ = _fila_unica(db_session, codigos_cruzados=True, cruce_fila_propia=True)
    motivo = fila["Motivo de las celdas vacías"]
    assert "no trae número interno para este expediente" in motivo
    assert "no figura por sí mismo" not in motivo


# --- Bloque 5, sesión 2026-09-18: hoja "Conciliación" ----------------------


def _documento_descargado(db_session, expediente_id: int, hash_documento: str) -> None:
    """Un documento real bajado de la Plataforma: es la evidencia más fuerte
    de que el expediente está publicado, y sin ninguno la Situación correcta
    es "Pendiente de procesar" (no se puede afirmar qué trae)."""
    documento = Documento(
        tipo_documento=TipoDocumento.anejo, hash=hash_documento,
        ruta_almacenamiento=f"{hash_documento}.pdf",
    )
    db_session.add(documento)
    db_session.commit()
    db_session.add(DocumentoExpediente(
        documento_id=documento.id, expediente_id=expediente_id,
        nombre_archivo=f"{hash_documento}.pdf",
    ))
    db_session.commit()


def test_conciliacion_tiene_una_fila_por_expediente_publicado_y_cuadra(db_session):
    _fila_unica(db_session)
    # Un segundo expediente publicado que no aporta ninguna línea: la hoja
    # existe justamente para que este no desaparezca del entregable.
    sin_cuadro = Expediente(
        codigo_expediente="6.25/28510.0999", nombre_proyecto="Suministro sin cuadro",
        estado=EstadoExpediente.pendiente_revision, descargado_en=_AHORA, extraido_en=_AHORA,
        error="no se extrajo ninguna línea de catálogo de los documentos descargados",
    )
    db_session.add(sin_cuadro)
    db_session.commit()
    _documento_descargado(db_session, sin_cuadro.id, "hash-sin-cuadro")
    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    hoja = libro["Conciliación"]
    filas = list(hoja.iter_rows(min_row=2, values_only=True))
    codigos = {f[0] for f in filas}
    assert codigos == {"6.26/28510.0016", "6.25/28510.0999"}
    # La suma de la columna de líneas es el número de filas de "Materiales".
    columna_lineas = COLUMNAS_CONCILIACION.index("Líneas que aporta al catálogo")
    assert sum(f[columna_lineas] for f in filas) == libro["Materiales"].max_row - 1
    # Ningún expediente se queda sin Situación.
    columna_situacion = COLUMNAS_CONCILIACION.index("Situación")
    assert all(f[columna_situacion] in SITUACIONES for f in filas)
    por_codigo = {f[0]: f for f in filas}
    assert por_codigo["6.26/28510.0016"][columna_situacion] == APORTA_LINEAS
    assert por_codigo["6.25/28510.0999"][columna_situacion] == SIN_CUADRO


def test_conciliacion_deja_fuera_lo_que_la_plataforma_confirma_que_no_publica(db_session):
    _fila_unica(db_session)
    db_session.add(Expediente(
        codigo_expediente="6.25/28510.0998", estado=EstadoExpediente.sin_publicar,
    ))
    db_session.commit()
    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    codigos = {f[0] for f in libro["Conciliación"].iter_rows(min_row=2, values_only=True)}
    assert "6.25/28510.0998" not in codigos


def test_conciliacion_incluye_un_expediente_de_otro_departamento_si_aporta_filas(db_session):
    """Requisito duro del cliente: "todo expediente que aparezca en la hoja
    Materiales tiene que aparecer en Conciliación" -- también la matriz de
    otro departamento cuyo cuadro de precios sí se leyó."""
    _fila_unica(db_session)
    ajeno = Expediente(codigo_expediente="2.24/04110.0035", nombre_proyecto="Acuerdo marco de EPIs")
    db_session.add(ajeno)
    db_session.commit()
    lote = Lote(expediente_id=ajeno.id, identificador_lote="1")
    db_session.add(lote)
    db_session.commit()
    db_session.add(LineaCatalogo(
        expediente_id=ajeno.id, lote_id=lote.id, clave_linea="P-002", orden_aparicion=0,
        codigo_precio="P-002", descripcion="GUANTE", precio_unitario=Decimal("1.00"),
    ))
    db_session.commit()
    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    filas = list(libro["Conciliación"].iter_rows(min_row=2, values_only=True))
    assert "2.24/04110.0035" in {f[0] for f in filas}
    columna_lineas = COLUMNAS_CONCILIACION.index("Líneas que aporta al catálogo")
    assert sum(f[columna_lineas] for f in filas) == libro["Materiales"].max_row - 1


def test_el_excel_no_sale_si_la_conciliacion_no_cuadra():
    """"Si no cuadra, párate y dime la diferencia" (encargo del cliente):
    nunca se entrega un Excel descuadrado."""
    filas = [FilaConciliacion(
        codigo_expediente="6.26/28510.0016", titulo=None, organo_contratacion=None,
        estado_plataforma=None, estado_adif=None, documentos_descargados=1,
        documentos_reconocimiento_optico=0,
        lineas_en_catalogo=3, baja="No", situacion=APORTA_LINEAS, motivo="",
    )]
    comprobar_cuadre(filas, 3)
    with pytest.raises(DescuadreConciliacion) as exc:
        comprobar_cuadre(filas, 5)
    assert "diferencia de -2" in str(exc.value)


def test_el_excel_no_sale_si_una_situacion_no_es_de_la_lista():
    filas = [FilaConciliacion(
        codigo_expediente="6.26/28510.0016", titulo=None, organo_contratacion=None,
        estado_plataforma=None, estado_adif=None, documentos_descargados=1,
        documentos_reconocimiento_optico=0,
        lineas_en_catalogo=0, baja="No", situacion="lo que sea", motivo="",
    )]
    with pytest.raises(DescuadreConciliacion):
        comprobar_cuadre(filas, 0)


def test_el_resumen_dice_de_que_fecha_es_el_registro_de_lo_publicado(db_session):
    _fila_unica(db_session)
    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    contenido = "\n".join(
        str(c.value) for fila in libro["Resumen"].iter_rows() for c in fila if c.value is not None
    )
    assert "De qué fecha es el registro de lo publicado y qué cubre" in contenido
    assert "Sindicación mensual de la Plataforma" in contenido
    assert "Búsqueda directa en el buscador de la Plataforma" in contenido
    # El recuento por Situación, con las seis categorías del cliente.
    for situacion in SITUACIONES:
        assert situacion in contenido


def test_conciliacion_marca_pendiente_de_procesar_lo_que_no_se_ha_buscado(db_session):
    """Un expediente que consta publicado (lo listó la sindicación) pero que
    todavía no se ha ido a buscar a la Plataforma no puede decir "publicado sin
    cuadro de precios": no se sabe qué trae. Sale como trabajo pendiente."""
    _fila_unica(db_session)
    pendiente = Expediente(codigo_expediente="6.25/28510.0997")
    db_session.add(pendiente)
    db_session.commit()
    db_session.add(SindicacionExpediente(
        codigo_expediente="6.25/28510.0997", periodo_zip="202609", estado_pcsp="PUB",
        actualizado_en=_AHORA,
    ))
    db_session.commit()
    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    filas = {f[0]: f for f in libro["Conciliación"].iter_rows(min_row=2, values_only=True)}
    columna = COLUMNAS_CONCILIACION.index("Situación")
    assert filas["6.25/28510.0997"][columna] == PENDIENTE_DE_PROCESAR
    assert "todavía no se ha descargado" in filas["6.25/28510.0997"][
        COLUMNAS_CONCILIACION.index("Motivo")
    ]


def test_conciliacion_no_llama_pendiente_a_una_ficha_que_no_publica_documentos(db_session):
    """Bloque 4, sesión 2026-09-18 (continuación). `6.14/28510.0148` y `0177`
    se buscaron cinco veces en la Plataforma: las dos veces su ficha aparece y
    las cinco devuelve cero documentos descargables. Llamarlos "Pendiente de
    procesar" promete un trabajo que no existe -- no falta leerlos, no hay
    nada publicado que leer."""
    _fila_unica(db_session)
    db_session.add(Expediente(codigo_expediente="6.14/28510.0148", descargado_en=_AHORA))
    db_session.commit()
    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    filas = {f[0]: f for f in libro["Conciliación"].iter_rows(min_row=2, values_only=True)}
    fila = filas["6.14/28510.0148"]
    assert fila[COLUMNAS_CONCILIACION.index("Situación")] == SIN_CUADRO
    assert "no publica ningún documento" in fila[COLUMNAS_CONCILIACION.index("Motivo")]


def test_conciliacion_señala_el_acuerdo_marco_no_publicado(db_session):
    """Uno de los seis valores que pidió el cliente, y el motivo mayoritario
    real del corpus (49 expedientes): el pedido está publicado, pero sus
    precios viven en los documentos de un acuerdo marco que la Plataforma no
    publica."""
    _fila_unica(db_session)
    matriz = Expediente(
        codigo_expediente="2.18/04703.0019", estado=EstadoExpediente.sin_publicar,
    )
    pedido = Expediente(
        codigo_expediente="6.23/28510.0063", codigo_matriz="2.18/04703.0019",
        estado=EstadoExpediente.pendiente_revision, descargado_en=_AHORA, extraido_en=_AHORA,
        error="la matriz 2.18/04703.0019 no tiene ningún lote registrado (estado: sin_publicar)",
    )
    db_session.add_all([matriz, pedido])
    db_session.commit()
    _documento_descargado(db_session, pedido.id, "hash-pedido")
    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    filas = {f[0]: f for f in libro["Conciliación"].iter_rows(min_row=2, values_only=True)}
    assert "2.18/04703.0019" not in filas  # confirmado no publicado: no se concilia
    fila = filas["6.23/28510.0063"]
    assert fila[COLUMNAS_CONCILIACION.index("Situación")] == PRECIOS_EN_ACUERDO_MARCO
    assert "2.18/04703.0019" in fila[COLUMNAS_CONCILIACION.index("Motivo")]


# --- Bloque 3 y 4, sesión 2026-09-18 (continuación) ------------------------


def test_conciliacion_trae_el_estado_segun_adif_en_columna_propia(db_session):
    """El estado que manda ADIF en su listado y el que publica la Plataforma
    son dos hechos distintos, de dos fuentes distintas. Van en dos columnas,
    nunca mezclados en una."""
    _fila_unica(db_session)
    expediente = db_session.execute(
        select(Expediente).where(Expediente.codigo_expediente == "6.26/28510.0016")
    ).scalar_one()
    expediente.estado_adif = "En ejecución"
    db_session.commit()
    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    hoja = libro["Conciliación"]
    cabecera = [c.value for c in hoja[1]]
    assert cabecera == COLUMNAS_CONCILIACION
    assert "Estado según ADIF" in cabecera
    assert cabecera.index("Estado según ADIF") != cabecera.index(
        "Estado que consta publicado en la Plataforma"
    )
    fila = next(hoja.iter_rows(min_row=2, values_only=True))
    assert fila[cabecera.index("Estado según ADIF")] == "En ejecución"


def test_conciliacion_explica_el_hueco_del_estado_de_adif(db_session):
    _fila_unica(db_session)
    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    hoja = libro["Conciliación"]
    fila = next(hoja.iter_rows(min_row=2, values_only=True))
    celda = fila[COLUMNAS_CONCILIACION.index("Estado según ADIF")]
    assert "no figura en el listado de estados que ADIF envió" in celda


def test_el_resumen_atribuye_el_estado_de_adif_a_adif_y_no_a_la_plataforma(db_session):
    _fila_unica(db_session)
    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    contenido = "\n".join(
        str(c.value) for fila in libro["Resumen"].iter_rows() for c in fila if c.value is not None
    )
    assert "\"Estado según ADIF\" de esa hoja NO sale de la Plataforma" in contenido
    assert "no interviene en ningún momento en decidir si un expediente consta publicado" in contenido


def _expediente_leido(db_session, codigo: str, error: str) -> Expediente:
    expediente = Expediente(
        codigo_expediente=codigo, estado=EstadoExpediente.pendiente_revision,
        descargado_en=_AHORA, extraido_en=_AHORA, error=error,
    )
    db_session.add(expediente)
    db_session.commit()
    return expediente


def _documento_con_reconocimiento_optico(db_session, expediente_id: int, hash_documento: str) -> None:
    _documento_descargado(db_session, expediente_id, hash_documento)
    db_session.add(CacheOcrDocumento(
        documento_hash=hash_documento, version_logica_ocr="1", modelo="m",
        num_paginas=1, completo=True, paginas=[],
    ))
    db_session.commit()


def test_escaneado_ilegible_solo_cuando_es_la_unica_explicacion(db_session):
    """Bloque 4, sesión 2026-09-18 (continuación): la etiqueta significa "hubo
    documentos que leer, alguno hubo que leerlo por imagen y no salió nada de
    ellos". Ni más ni menos."""
    _fila_unica(db_session)
    expediente = _expediente_leido(
        db_session, "6.17/28510.0012",
        "no se extrajo ninguna línea de catálogo de los documentos descargados",
    )
    _documento_con_reconocimiento_optico(db_session, expediente.id, "hash-escaneado")
    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    filas = {f[0]: f for f in libro["Conciliación"].iter_rows(min_row=2, values_only=True)}
    assert filas["6.17/28510.0012"][COLUMNAS_CONCILIACION.index("Situación")] == ESCANEADO_ILEGIBLE


def test_un_documento_escaneado_no_tapa_la_causa_real_del_expediente(db_session):
    """El caso que motivó el arreglo: `3.18/28510.0047` tiene un anejo
    escaneado, pero lo que le pasa está escrito en su propio motivo y es otra
    cosa. Antes, cualquier documento pasado por reconocimiento óptico lo
    mandaba al cajón de los escaneados y tapaba la explicación real."""
    _fila_unica(db_session)
    expediente = _expediente_leido(
        db_session, "3.18/28510.0047",
        "cobertura parcial: 1 de 8 lotes declarados tienen baja/importe (con datos: 8)",
    )
    _documento_con_reconocimiento_optico(db_session, expediente.id, "hash-anejo-escaneado")
    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    filas = {f[0]: f for f in libro["Conciliación"].iter_rows(min_row=2, values_only=True)}
    fila = filas["3.18/28510.0047"]
    assert fila[COLUMNAS_CONCILIACION.index("Situación")] == OTRO
    assert "cobertura parcial" in fila[COLUMNAS_CONCILIACION.index("Motivo")]


def test_sin_anejo_ni_pliego_es_publicado_sin_cuadro_aunque_haya_un_escaneado(db_session):
    _fila_unica(db_session)
    expediente = _expediente_leido(
        db_session, "6.18/28510.0050",
        "no se extrajo ninguna línea de catálogo: el expediente no trae ningún Anejo ni Pliego "
        "técnico con posible cuadro de precios, solo contrato, resolucion_adjudicacion",
    )
    _documento_con_reconocimiento_optico(db_session, expediente.id, "hash-contrato-escaneado")
    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    filas = {f[0]: f for f in libro["Conciliación"].iter_rows(min_row=2, values_only=True)}
    assert filas["6.18/28510.0050"][COLUMNAS_CONCILIACION.index("Situación")] == SIN_CUADRO


# --- Bloques 3, 4 y 6, sesión 2026-09-18 (quinta parte) --------------------


def test_un_lote_publicado_en_la_ficha_de_otro_no_se_llama_no_publicado(db_session):
    """Bloque 3. `6.26/28510.0003` es el lote 2 de `6.25/28510.0221`: buscarlo
    en la Plataforma por su número no devuelve nada, pero su adjudicación está
    publicada dentro de la ficha del expediente principal. Antes caía fuera de
    la hoja, contado como "la Plataforma confirmó que no publica"."""
    _fila_unica(db_session)
    principal = Expediente(
        codigo_expediente="6.25/28510.0221", nombre_proyecto="Traviesas de madera. 2 LOTES",
        estado=EstadoExpediente.pendiente_revision, descargado_en=_AHORA, extraido_en=_AHORA,
        error="no se extrajo ninguna línea de catálogo de los documentos descargados",
    )
    lote_aparte = Expediente(
        codigo_expediente="6.26/28510.0003", estado=EstadoExpediente.sin_publicar,
    )
    db_session.add_all([principal, lote_aparte])
    db_session.commit()
    _documento_descargado(db_session, principal.id, "hash-principal")
    db_session.add(Lote(
        expediente_id=principal.id, identificador_lote="2",
        codigo_expediente_lote="6.26/28510.0003",
    ))
    db_session.commit()

    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    filas = {f[0]: f for f in libro["Conciliación"].iter_rows(min_row=2, values_only=True)}

    fila = filas["6.26/28510.0003"]
    assert fila[COLUMNAS_CONCILIACION.index("Situación")] == PUBLICADO_EN_FICHA_DE_OTRO
    motivo = fila[COLUMNAS_CONCILIACION.index("Motivo")]
    assert "lote 2" in motivo and "6.25/28510.0221" in motivo
    # Y el registro deja de contarlo entre los que la Plataforma no publica.
    registro = "\n".join(
        str(c.value) for f in libro["Resumen"].iter_rows() for c in f if c.value is not None
    )
    assert "SÍ están publicados" in registro


def test_sin_enlace_estructural_no_se_fuerza_nada(db_session):
    """Bloque 3, la otra mitad: mencionar el número en el texto de un
    documento ajeno no basta. Sin un lote que lo declare por número, el
    expediente sigue fuera de la hoja."""
    _fila_unica(db_session)
    otro = Expediente(
        codigo_expediente="6.25/28510.0221", estado=EstadoExpediente.pendiente_revision,
        descargado_en=_AHORA, extraido_en=_AHORA,
    )
    db_session.add_all([
        otro, Expediente(codigo_expediente="6.26/28510.0002", estado=EstadoExpediente.sin_publicar),
    ])
    db_session.commit()
    _documento_descargado(db_session, otro.id, "hash-otro")

    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    codigos = {f[0] for f in libro["Conciliación"].iter_rows(min_row=2, values_only=True)}

    assert "6.26/28510.0002" not in codigos


def test_acuerdo_marco_publicado_sin_precios_es_una_situacion_aparte(db_session):
    """Bloque 4. `4.23/04110.0256` sí está publicado; lo que publica es el
    modelo de proposición económica en blanco. No es lo mismo que un acuerdo
    marco que no está publicado, y el cliente lo va a preguntar."""
    _fila_unica(db_session)
    principal = Expediente(
        codigo_expediente="4.23/04110.0256", nombre_proyecto="Acuerdo Marco de EPIs (8 lotes)",
        estado=EstadoExpediente.pendiente_revision, descargado_en=_AHORA, extraido_en=_AHORA,
    )
    matriz = Expediente(codigo_expediente="4.24/04110.0187", estado=EstadoExpediente.sin_publicar)
    pedido = Expediente(
        codigo_expediente="6.26/28510.0073", codigo_matriz="4.24/04110.0187",
        nombre_proyecto=(
            "Pedido del acuerdo marco de EPIs, expediente principal 4.23/04110.0256 lote 4: "
            "guantes de protección contra riesgos mecánicos"
        ),
        estado=EstadoExpediente.pendiente_revision, descargado_en=_AHORA, extraido_en=_AHORA,
        error="la matriz 4.24/04110.0187 no tiene ningún lote registrado (estado: sin_publicar)",
    )
    db_session.add_all([principal, matriz, pedido])
    db_session.commit()
    _documento_descargado(db_session, principal.id, "hash-am")
    _documento_descargado(db_session, pedido.id, "hash-pedido-am")

    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    filas = {f[0]: f for f in libro["Conciliación"].iter_rows(min_row=2, values_only=True)}

    fila = filas["6.26/28510.0073"]
    assert fila[COLUMNAS_CONCILIACION.index("Situación")] == ACUERDO_MARCO_SIN_PRECIOS
    assert "4.23/04110.0256" in fila[COLUMNAS_CONCILIACION.index("Motivo")]


def test_el_acuerdo_marco_no_publicado_sigue_siendo_su_propia_situacion(db_session):
    """Bloque 4: partir en dos no puede mover a los que no tienen ningún
    expediente principal publicado detrás -- son 47 de los 49."""
    _fila_unica(db_session)
    matriz = Expediente(codigo_expediente="2.18/04703.0019", estado=EstadoExpediente.sin_publicar)
    pedido = Expediente(
        codigo_expediente="6.20/28510.0018", codigo_matriz="2.18/04703.0019",
        nombre_proyecto="Pedido nº 1 acuerdo marco de EPIs. Lote 3. Pantalones.",
        estado=EstadoExpediente.pendiente_revision, descargado_en=_AHORA, extraido_en=_AHORA,
        error="la matriz 2.18/04703.0019 no tiene ningún lote registrado (estado: sin_publicar)",
    )
    db_session.add_all([matriz, pedido])
    db_session.commit()
    _documento_descargado(db_session, pedido.id, "hash-epi")

    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    filas = {f[0]: f for f in libro["Conciliación"].iter_rows(min_row=2, values_only=True)}

    assert filas["6.20/28510.0018"][COLUMNAS_CONCILIACION.index("Situación")] == PRECIOS_EN_ACUERDO_MARCO


def test_el_documento_de_adjudicacion_manda_sobre_un_boletin_mas_viejo(db_session):
    """Bloque 6. `6.25/28510.0221`: el último boletín que lo lista es el de
    07/2026, con "Pendiente de adjudicación"; su Resolución de Adjudicación
    está descargada de la Plataforma y leída. La columna decía el dato viejo."""
    _fila_unica(db_session)
    expediente = db_session.execute(
        select(Expediente).where(Expediente.codigo_expediente == "6.26/28510.0016")
    ).scalar_one()
    db_session.add(SindicacionExpediente(
        codigo_expediente="6.26/28510.0016", expediente_id=expediente.id,
        actualizado_en=_AHORA, estado_pcsp="EV", periodo_zip="202607",
    ))
    adjudicacion = Documento(
        tipo_documento=TipoDocumento.resolucion_adjudicacion, hash="hash-adjudicacion",
        ruta_almacenamiento="hash-adjudicacion.pdf",
    )
    db_session.add(adjudicacion)
    db_session.commit()
    db_session.add(DocumentoExpediente(
        documento_id=adjudicacion.id, expediente_id=expediente.id,
        nombre_archivo="ADJUDICACION_1.pdf",
    ))
    db_session.commit()

    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    fila = next(libro["Conciliación"].iter_rows(min_row=2, values_only=True))
    celda = fila[COLUMNAS_CONCILIACION.index("Estado que consta publicado en la Plataforma")]

    assert celda.startswith("Adjudicada")
    assert "07/2026" in celda
    assert "Pendiente de adjudicación" in celda


def test_la_columna_de_estado_nunca_baja_de_etapa(db_session):
    """Bloque 6: solo se sustituye cuando el documento prueba una etapa
    POSTERIOR. "Anulada" no está en la escalera y no se deshace nunca con un
    documento anterior a ella."""
    _fila_unica(db_session)
    expediente = db_session.execute(
        select(Expediente).where(Expediente.codigo_expediente == "6.26/28510.0016")
    ).scalar_one()
    db_session.add(SindicacionExpediente(
        codigo_expediente="6.26/28510.0016", expediente_id=expediente.id,
        actualizado_en=_AHORA, estado_pcsp="ANUL", periodo_zip="202609",
    ))
    adjudicacion = Documento(
        tipo_documento=TipoDocumento.resolucion_adjudicacion, hash="hash-adj-anulada",
        ruta_almacenamiento="hash-adj-anulada.pdf",
    )
    db_session.add(adjudicacion)
    db_session.commit()
    db_session.add(DocumentoExpediente(
        documento_id=adjudicacion.id, expediente_id=expediente.id,
        nombre_archivo="ADJUDICACION_1.pdf",
    ))
    db_session.commit()

    libro = openpyxl.load_workbook(io.BytesIO(generar_excel_catalogo(db_session)))
    fila = next(libro["Conciliación"].iter_rows(min_row=2, values_only=True))

    assert fila[COLUMNAS_CONCILIACION.index(
        "Estado que consta publicado en la Plataforma"
    )] == "Anulada"
