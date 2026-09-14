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
