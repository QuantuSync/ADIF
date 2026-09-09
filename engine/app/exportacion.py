"""Exportación del catálogo a Excel (CONTEXTO.md, encargo de esta sesión, punto
4, y sección 9.8: "El Excel es una vista generada, no la fuente. [...] Se
regenera a demanda"). Un solo catálogo acumulativo para todos los
expedientes, con las once columnas y el orden exactos de `Ejemplo/Output/`
— es el formato que el cliente ya espera recibir — más precio adjudicado y
baja de lote (encargo de una sesión anterior, punto 3) y, al final de todo,
unidad de medida (aviso del cliente, sesión 2026-09-07: sin ella, una
Cantidad de 2000 o un Precio unitario de 0,142 no significan nada por sí
solos). Las tres añadidas siempre después de las once originales, nunca
alterando su orden ni sus posiciones.

El marcador entre paréntesis ("(no consta)", "(no aplica)") es una
convención de la interfaz web (`app/ui.tsx`, `DatoVacio`) para que una
persona lea la pantalla sin ambigüedad. **No viaja al Excel** (encargo de
esta sesión, punto 1): en una columna numérica (Cantidad, Precio unitario,
Precio adjudicado, Baja del lote) un marcador de texto convierte la columna
entera en texto mixto y rompe sumar/filtrar/ordenar en Excel. En las
columnas de texto (Matrícula, Código del material, Lote, Unidad de medida)
se aplica el mismo criterio único por consistencia y porque es el que trae
el Excel que ya maneja el cliente: celda vacía, sin ninguna variante. El
motivo por el que falta (partida alzada, cruce sin confirmar, tabla
ambigua, cuadro de precios sin columna de unidad) ya vive en
`motivo_revision`/la cola de revisión, trazable desde ahí — no se
inventa aquí un texto nuevo para la casilla.

Líneas huérfanas (`lote_id IS NULL`, tabla que no se pudo asociar a un
lote sin ambigüedad, `app.extraccion.lote_tabla`) sin ningún equivalente
ya resuelto en un lote conocido del mismo expediente: por defecto **no
salen en este Excel** (encargo de esta sesión) — mostrarían el mismo
material 2-6 veces sin que el cliente pueda distinguir una repetición real
de una casualidad de la extracción, y siguen genuinamente pendientes de
que una persona les asigne lote (docs/decisiones.md sección 31). Quedan en
la cola de revisión interna, nunca se pierden. `incluir_pendientes_sin_lote`
lo vuelve a activar sin tocar código, para cuando el cliente prefiera
verlas todas. Se excluyan o no, la hoja "Resumen" siempre dice cuántas
hay y por qué motivo agrupado — nunca desaparecen en silencio."""
from __future__ import annotations

import io
from collections import Counter

from openpyxl import Workbook
from openpyxl.styles import Alignment
from sqlalchemy.orm import Session

from app.catalogo_consulta import consultar_catalogo
from app.models import LineaCatalogo


def _celda_matricula(linea: LineaCatalogo) -> str | None:
    return linea.matricula or None


def _celda_texto(valor: str | None) -> str | None:
    return valor or None


def _celda_numero(valor) -> object:
    return float(valor) if valor is not None else None


COLUMNAS = [
    "Código interno",
    "Código de expediente",
    "Código matriz",
    "Título expediente",
    "Matrícula del material",
    "Descripción del material",
    "Código del material",
    "Cantidad",
    "Precio unitario",
    "Lote",
    "Comentarios",
    "Precio adjudicado",
    "Baja del lote",
    # Aviso del cliente (sesión 2026-09-07): sin la unidad, una Cantidad de
    # 2000 o un Precio unitario de 0,142 no significan nada por sí solos
    # (pueden ser metros de cable o toneladas de balasto, o un precio por
    # tonelada-kilómetro). Al final, después de las dos columnas ya añadidas
    # en una sesión anterior -- no altera el orden ni las posiciones de las
    # once columnas originales del formato del cliente.
    "Unidad de medida",
    # Bloque 1, sesión del Excel de ejecución SAP (2026-09-07): estado del
    # CONTRATO frente a ADIF ("En ejecución", ...), distinto del estado de
    # PROCESAMIENTO de este sistema que ya decide si la fila sale en este
    # Excel. Al final de todo, cuarta columna añadida -- mismo criterio que
    # las tres anteriores.
    "Estado del contrato (SAP)",
]

# Columnas numéricas (1-indexadas, en el orden de COLUMNAS de arriba) a las
# que aplicar un formato de celda explícito -- sin esto openpyxl las deja en
# "General" y Excel puede mostrarlas alineadas a la izquierda como si fueran
# texto pese a llevar ya un valor numérico real (punto 1 de esta sesión:
# "Asegúrate además de que los importes se exportan como número").
_FORMATO_CANTIDAD = "#,##0.###"
_FORMATO_IMPORTE = "#,##0.00"
_FORMATO_PORCENTAJE = "0.00%"
_COLUMNA_CANTIDAD = COLUMNAS.index("Cantidad") + 1
_COLUMNAS_IMPORTE = (COLUMNAS.index("Precio unitario") + 1, COLUMNAS.index("Precio adjudicado") + 1)
_COLUMNA_PORCENTAJE = COLUMNAS.index("Baja del lote") + 1

# Tamaño de página de la consulta al generar: bastante grande para pocas
# vueltas a la base de datos, pequeño para no cargar el catálogo entero en
# memoria de golpe si crece mucho (CONTEXTO.md sección 1: catálogo acumulativo
# para todos los expedientes).
_TAMANO_LOTE = 500

# Categorías de `app.extraccion.lote_tabla.ResultadoAsociacionLote.motivo_ambiguo`
# (docstring de ese módulo): agrupa el texto libre -- que lleva números de
# página/lote concretos, distinto en cada fila -- en un puñado de motivos
# legibles para el resumen. `_OTRO_MOTIVO` cubre cualquier redacción nueva
# que aparezca en el futuro sin que el resumen deje de sumar bien.
#
# Cada categoría lleva, además de la etiqueta técnica interna (la que ya usa
# `motivo_revision`, necesaria para que el `marcador in motivo` de
# `_categoria_motivo` siga casando), dos frases en lenguaje llano para quien
# lea el Excel en ADIF sin conocer el funcionamiento interno del sistema:
# qué ha pasado, y qué haría falta para resolverlo. (Encargo de esta sesión,
# punto 4: "nadie en ADIF" debe poder entenderlo sin traducir jerga.)
_OTRO_MOTIVO = "otro_motivo_ambiguedad"
_SIN_MOTIVO = "sin_motivo_registrado"
_CATEGORIAS_MOTIVO = (
    (
        "banda vacía",
        "banda vacía: posible continuación de tabla partida entre páginas",
        "Esta tabla de precios parece continuar de una página a la siguiente del documento, y el sistema "
        "no ha podido confirmar a qué lote pertenece la parte que sigue.",
        "Que alguien abra el documento original y compruebe a qué lote corresponde esa parte de la tabla.",
    ),
    (
        "varias cabeceras de lote",
        "varias cabeceras de lote en la misma franja",
        "En esa parte del documento se mencionan varios lotes a la vez, y el sistema no puede saber con "
        "seguridad a cuál de ellos pertenecen estos materiales.",
        "Que alguien mire el documento y decida a qué lote hay que asignar esas filas.",
    ),
    (
        "ninguna cabecera LOTE",
        "ninguna cabecera de lote reconocible en la franja",
        "El documento no indica en ningún sitio cercano a qué lote pertenece esta tabla de precios.",
        "Que alguien revise el documento y asigne el lote a mano.",
    ),
    (
        "no está entre los lotes declarados",
        "la tabla declara un lote no registrado en el expediente",
        "La tabla menciona un número de lote que no coincide con ninguno de los lotes ya confirmados de "
        "ese expediente (puede ser una errata del documento, o un lote real que todavía falta registrar).",
        "Que alguien compare con el documento y corrija el número de lote, o lo dé de alta si falta.",
    ),
)
_EXPLICACION_OTRO_MOTIVO = (
    "El sistema detectó una ambigüedad de un tipo que no encaja en los motivos anteriores."
)
_RESOLUCION_OTRO_MOTIVO = "Revisión manual del documento correspondiente."
_EXPLICACION_SIN_MOTIVO = "No se guardó una explicación concreta para esta fila."
_RESOLUCION_SIN_MOTIVO = "Revisión manual del documento correspondiente."


def _categoria_motivo(motivo: str | None) -> str:
    if not motivo:
        return _SIN_MOTIVO
    for marcador, categoria, _explicacion, _resolucion in _CATEGORIAS_MOTIVO:
        if marcador in motivo:
            return categoria
    return _OTRO_MOTIVO


# Mapa categoría técnica -> (explicación llana, qué haría falta para resolverlo).
_EXPLICACIONES_MOTIVO = {
    categoria: (explicacion, resolucion) for _marcador, categoria, explicacion, resolucion in _CATEGORIAS_MOTIVO
}
_EXPLICACIONES_MOTIVO[_OTRO_MOTIVO] = (_EXPLICACION_OTRO_MOTIVO, _RESOLUCION_OTRO_MOTIVO)
_EXPLICACIONES_MOTIVO[_SIN_MOTIVO] = (_EXPLICACION_SIN_MOTIVO, _RESOLUCION_SIN_MOTIVO)

# CONTEXTO.md sección 6/7: "Código del material" solo se rellena cuando el
# sustantivo principal de la descripción casa contra un vocabulario todavía
# pequeño (BRIDA, PLACA, JUNTA...); ampliarlo con el modelo cuando no casa
# nada queda fuera de esta sesión (sin ningún caso real sin casar en el
# corpus de prueba). El resultado es una columna vacía en la mayoría de las
# filas *por diseño*, no un fallo de extracción -- se explica aquí para que
# no parezca un defecto del entregable.
_NOTA_CODIGO_MATERIAL = (
    "La columna \"Código del material\" solo se rellena cuando el sistema reconoce con seguridad la "
    "primera palabra de la descripción (por ejemplo BRIDA, PLACA, JUNTA, GUANTE, TRAVIESA). Hoy reconoce "
    "una lista corta de palabras, así que queda vacía en la mayoría de las filas -- no es un fallo de "
    "extracción ni un dato perdido: la descripción completa del material sí está siempre en la columna "
    "\"Descripción del material\". Ampliar la lista de palabras reconocidas es un trabajo pendiente, no "
    "una corrección urgente."
)


def _escribir_resumen(
    libro: Workbook, incluidas: int, excluidas_por_categoria: Counter[str], incluir_pendientes_sin_lote: bool
) -> None:
    hoja = libro.create_sheet("Resumen")
    hoja.append(["Concepto", "Valor"])
    hoja.append(["Líneas en este catálogo", incluidas])
    total_excluidas = sum(excluidas_por_categoria.values())
    hoja.append(["Líneas pendientes de revisión (no incluidas arriba)", total_excluidas])
    hoja.append([])
    if incluir_pendientes_sin_lote:
        hoja.append(["Exportado con las líneas pendientes de revisión incluidas en \"Materiales\".", None])
    elif total_excluidas:
        hoja.append(["Por qué hay líneas pendientes de revisión", None])
        hoja.append([
            "Son materiales de los que no se sabe con seguridad a qué lote pertenecen, así que se han "
            "dejado fuera de la hoja \"Materiales\" para no mostrar el mismo material varias veces sin "
            "poder distinguir una repetición real de un error de lectura del documento. Siguen guardados, "
            "no se han perdido.",
            None,
        ])
        hoja.append([])
        hoja.append(["Qué ha pasado", "Líneas", "Qué haría falta para resolverlo"])
        for categoria, cantidad in sorted(excluidas_por_categoria.items(), key=lambda kv: -kv[1]):
            explicacion, resolucion = _EXPLICACIONES_MOTIVO.get(
                categoria, (_EXPLICACION_OTRO_MOTIVO, _RESOLUCION_OTRO_MOTIVO)
            )
            hoja.append([explicacion, cantidad, resolucion])
    hoja.append([])
    hoja.append(["Nota sobre la columna \"Código del material\"", None])
    hoja.append([_NOTA_CODIGO_MATERIAL, None])
    for fila in hoja.iter_rows():
        for celda in fila:
            if isinstance(celda.value, str) and len(celda.value) > 60:
                celda.alignment = Alignment(wrap_text=True, vertical="top")
    hoja.column_dimensions["A"].width = 90
    hoja.column_dimensions["B"].width = 12
    hoja.column_dimensions["C"].width = 60


def generar_excel_catalogo(db: Session, incluir_pendientes_sin_lote: bool = False) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Materiales"
    hoja.append(COLUMNAS)

    incluidas = 0
    excluidas_por_categoria: Counter[str] = Counter()

    pagina = 1
    while True:
        # CONTEXTO.md bloque 2: una línea descartada en la cola de revisión no
        # sale en el Excel que se entrega al cliente, aunque siga en base de
        # datos con su motivo.
        resultado = consultar_catalogo(db, pagina=pagina, tamano_pagina=_TAMANO_LOTE, excluir_descartadas=True)
        for linea, lote, expediente, _documento, _nombre_archivo in resultado.filas:
            if lote is None and not incluir_pendientes_sin_lote:
                excluidas_por_categoria[_categoria_motivo(linea.motivo_revision)] += 1
                continue
            incluidas += 1
            # "El sistema nunca inventa una matriz. Si no cruza, se deja
            # vacío" (CONTEXTO.md sección 7): código interno y código de
            # proyecto solo se rellenan cuando el cruce con el Excel de
            # códigos confirmó la fila.
            cruzado = bool(expediente.codigos_cruzados)
            fila = hoja.max_row + 1
            hoja.append([
                expediente.codigo_interno if cruzado else None,
                expediente.codigo_expediente if cruzado else None,
                expediente.codigo_matriz,
                expediente.nombre_proyecto,
                _celda_matricula(linea),
                linea.descripcion,
                _celda_texto(linea.codigo_material),
                _celda_numero(linea.cantidad),
                _celda_numero(linea.precio_unitario),
                _celda_texto(lote.identificador_lote if lote else None),
                linea.comentarios,
                _celda_numero(linea.precio_adjudicado),
                _celda_numero(linea.baja_lote),
                _celda_texto(linea.unidad_medida),
                _celda_texto(expediente.estado_contrato_sap),
            ])
            hoja.cell(row=fila, column=_COLUMNA_CANTIDAD).number_format = _FORMATO_CANTIDAD
            for columna in _COLUMNAS_IMPORTE:
                hoja.cell(row=fila, column=columna).number_format = _FORMATO_IMPORTE
            hoja.cell(row=fila, column=_COLUMNA_PORCENTAJE).number_format = _FORMATO_PORCENTAJE
        if pagina * _TAMANO_LOTE >= resultado.total:
            break
        pagina += 1

    _escribir_resumen(libro, incluidas, excluidas_por_categoria, incluir_pendientes_sin_lote)

    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()
