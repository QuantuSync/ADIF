"""Exportación del catálogo a Excel (CONTEXTO.md, encargo de esta sesión, punto
4, y sección 9.8: "El Excel es una vista generada, no la fuente. [...] Se
regenera a demanda"). Un solo catálogo acumulativo para todos los
expedientes, con las once columnas y el orden exactos de `Ejemplo/Output/`
— es el formato que el cliente ya espera recibir — más precio adjudicado y
baja de lote (encargo de una sesión anterior, punto 3) y, al final de todo,
unidad de medida (aviso del cliente, sesión 2026-09-07: sin ella, una
Cantidad de 2000 o un Precio unitario de 0,142 no significan nada por sí
solos). Las tres añadidas siempre después de las once originales, nunca
alterando su orden ni sus posiciones -- **excepto "Comentarios"**, que el
cliente pidió mover al final de todas (bloque 1, segunda tanda de cambios
tras revisar el catálogo, sesión 2026-09-09): es la única de las once que
rellena una persona a mano, no el documento.

El marcador entre paréntesis ("(no consta)", "(no aplica)") es una
convención de la interfaz web (`app/ui.tsx`, `DatoVacio`) para que una
persona lea la pantalla sin ambigüedad. **No viaja a la celda** (encargo de
esta sesión, punto 1): en una columna numérica (Cantidad, Precio unitario,
Precio adjudicado, Baja del lote) un marcador de texto convierte la columna
entera en texto mixto y rompe sumar/filtrar/ordenar en Excel. En las
columnas de texto (Matrícula, Código del material, Lote, Unidad de medida)
se aplica el mismo criterio único por consistencia y porque es el que trae
el Excel que ya maneja el cliente: celda vacía, sin ninguna variante. El
motivo sí viaja, en su propia columna de texto ("Motivo de las celdas
vacías", sesión 2026-09-14): el mismo criterio de tres motivos de la web,
decidido en `app.celdas_vacias`, para que una cantidad vacía porque el
documento da una distinta para cada lote no se lea igual que una que el
documento no trae.

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
from decimal import Decimal
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment
from sqlalchemy.orm import Session

from app.catalogo import MOTIVO_MAPEO_INCOHERENTE
from app.catalogo_consulta import consultar_catalogo
from app.celdas_vacias import ETIQUETA_MOTIVO, PENDIENTE, celdas_vacias
from app.models import LineaCatalogo


def _celda_matricula(linea: LineaCatalogo) -> str | None:
    return linea.matricula or None


def _celda_texto(valor: str | None) -> str | None:
    return valor or None


def _celda_texto_o_espacio(valor: str | None) -> str:
    """Bloque 2, segunda tanda de cambios del cliente tras revisar el
    catálogo (sesión 2026-09-09): una celda de texto vacía del todo deja
    que Excel desborde encima el texto de la celda anterior de la misma
    fila -- un único espacio ocupa la celda sin desbordamiento, y se sigue
    leyendo como "vacío" al mirar la pantalla. **Solo en columnas de
    texto**: en una columna numérica (`_celda_numero`, justo debajo) un
    espacio la convertiría en texto mixto y rompería sumar/filtrar/ordenar
    -- el mismo motivo, en sentido contrario, por el que el marcador
    "(no consta)" tampoco viaja al Excel (ver docstring del módulo)."""
    return valor if valor else " "


def _celda_numero(valor) -> object:
    return float(valor) if valor is not None else None


# Campo de `app.celdas_vacias` -> su columna en esta hoja.
_COLUMNA_DE_CAMPO = {
    "matricula": "Matrícula del material",
    "codigo_material": "Código del material",
    "cantidad": "Cantidad",
    "precio_unitario": "Precio unitario",
    "lote": "Lote",
    "precio_adjudicado": "Precio adjudicado",
    "baja_lote": "Baja del lote",
    "unidad_medida": "Unidad de medida",
}


def _texto_celdas_vacias(linea: LineaCatalogo, identificador_lote: Optional[str]) -> Optional[str]:
    """"Cantidad: pendiente (el documento da una cantidad distinta para cada
    lote...); Matrícula del material: no consta" -- `None` si la fila no
    tiene ninguna celda de datos vacía."""
    partes = [
        f"{_COLUMNA_DE_CAMPO[c.campo]}: {ETIQUETA_MOTIVO[c.motivo]}" + (f" ({c.detalle})" if c.detalle else "")
        for c in celdas_vacias(linea, identificador_lote)
    ]
    return "; ".join(partes) or None


# Leyenda de la columna "Motivo de las celdas vacías" en la hoja Resumen: los
# mismos tres motivos de la web, en lenguaje llano.
_LEYENDA_MOTIVOS = (
    ("No consta", "El documento de origen no trae ese dato para esta línea."),
    (
        "No aplica",
        "El dato no corresponde a este tipo de línea: una partida alzada es una reserva presupuestaria, no un "
        "artículo de almacén, y no lleva matrícula, código de material ni unidad propios.",
    ),
    (
        "Pendiente",
        "El dato depende de otro que todavía falta. En Cantidad o Precio unitario: el documento trae un valor "
        "distinto para cada lote bajo el mismo código de precio y aún no se sabe cuál es el de este lote -- se "
        "deja vacío en vez de mostrar el de otro lote. En Precio adjudicado: falta la baja del lote o el precio "
        "unitario del que se calcula.",
    ),
)


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
    # Bloque 1, sesión de comparación documento-vs-listado interno: el
    # número de expediente y el objeto/título tal como los declara el propio
    # documento de la Plataforma, siempre rellenos con independencia de si
    # el expediente cruzó con el Excel de códigos de ADIF -- a diferencia de
    # "Código de expediente"/"Código interno" (arriba, gated por
    # `expediente.codigos_cruzados`), para que el cliente pueda comparar lo
    # que dice el documento contra lo que dice su listado interno y detectar
    # errores de cualquiera de las dos fuentes. Añadidas al final, sin
    # desplazar ninguna columna existente -- "Comentarios" se queda última.
    "Nº de expediente (documento)",
    "Objeto del contrato (documento)",
    # Sesión 2026-09-14 (continuación), encargo del cliente: por qué está
    # vacía cada celda de datos de la fila, con los tres motivos de la web
    # (no aplica / no consta / pendiente, `app.celdas_vacias`). Las celdas
    # siguen vacías -- un marcador de texto rompería las columnas numéricas
    # (ver docstring del módulo) --, el motivo va aquí. Justo antes de
    # "Comentarios", que se queda la última.
    "Motivo de las celdas vacías",
    # Segunda tanda de cambios del cliente tras revisar el catálogo (bloque
    # 1, sesión 2026-09-09): la única de las once columnas originales que el
    # cliente pidió mover -- de la novena posición al final de todas,
    # después de las cuatro añadidas más tarde. Es la única columna que
    # rellena una persona a mano (CONTEXTO.md sección 7: "Comentarios |
    # Humano"), así que al final es donde menos estorba a las columnas que
    # sí vienen del documento.
    "Comentarios",
]

# Columnas numéricas (1-indexadas, en el orden de COLUMNAS de arriba) a las
# que aplicar un formato de celda explícito -- sin esto openpyxl las deja en
# "General" y Excel puede mostrarlas alineadas a la izquierda como si fueran
# texto pese a llevar ya un valor numérico real (punto 1 de esta sesión:
# "Asegúrate además de que los importes se exportan como número").
_FORMATO_CANTIDAD_ENTERO = "#,##0"
_FORMATO_IMPORTE = "#,##0.00"
_FORMATO_PORCENTAJE = "0.00%"
_COLUMNA_CANTIDAD = COLUMNAS.index("Cantidad") + 1
_COLUMNAS_IMPORTE = (COLUMNAS.index("Precio unitario") + 1, COLUMNAS.index("Precio adjudicado") + 1)
_COLUMNA_PORCENTAJE = COLUMNAS.index("Baja del lote") + 1


def _formato_cantidad(valor: Optional[Decimal]) -> str:
    """Máscara de celda sin decimales ni punto de sobra (bloque 2, revisión
    del cliente: la columna Cantidad mostraba `20.000.`, un punto colgando
    tras un valor entero). Una máscara con `#` opcionales tras el punto
    (`#,##0.###`) depende de que el lector de Excel colapse el separador
    decimal entero cuando no hay ninguna cifra que mostrar -- no todos lo
    hacen igual. Más seguro: contar los decimales significativos reales de
    `valor` (hasta 3, la precisión de `lineas_catalogo.cantidad`) y construir
    una máscara con exactamente esos ceros fijos; si no hay ninguno, la
    máscara no lleva punto decimal en absoluto, así que no hay nada que
    colapsar mal en ningún lector."""
    if valor is None:
        return _FORMATO_CANTIDAD_ENTERO
    exponente = valor.normalize().as_tuple().exponent
    decimales = max(0, min(-exponente, 3)) if isinstance(exponente, int) else 0
    if decimales == 0:
        return _FORMATO_CANTIDAD_ENTERO
    return f"#,##0.{'0' * decimales}"

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
        "tabla separada de la anterior",
        "tabla tras páginas sin tabla, sin título de lote",
        "Esta tabla aparece varias páginas después de la anterior y no lleva título de lote propio, así que "
        "no se puede dar por hecho que continúa el lote de la tabla anterior (suele ser un cuadro común a "
        "todos los lotes: criterios técnicos, precios para la partida alzada...).",
        "Que alguien mire el documento y decida si pertenece a un lote concreto o es común a todos.",
    ),
    (
        "no está entre los lotes declarados",
        "la tabla declara un lote no registrado en el expediente",
        "La tabla menciona un número de lote que no coincide con ninguno de los lotes ya confirmados de "
        "ese expediente (puede ser una errata del documento, o un lote real que todavía falta registrar).",
        "Que alguien compare con el documento y corrija el número de lote, o lo dé de alta si falta.",
    ),
    (
        MOTIVO_MAPEO_INCOHERENTE,
        "cuadro de precios sin cabecera, columnas mal identificadas",
        "Esta tabla no traía cabecera propia (una página de continuación, normalmente) y el sistema no "
        "pudo identificar con confianza qué columna es cada dato -- para no inventar valores, se ha "
        "descartado del Excel entero, aunque siga guardada en la base de datos.",
        "Que alguien abra el documento original en esa página y complete o corrija la fila a mano.",
    ),
)
_EXPLICACION_OTRO_MOTIVO = (
    "El sistema detectó una ambigüedad de un tipo que no encaja en los motivos anteriores."
)
_RESOLUCION_OTRO_MOTIVO = "Revisión manual del documento correspondiente."
_EXPLICACION_SIN_MOTIVO = "No se guardó una explicación concreta para esta fila."
_RESOLUCION_SIN_MOTIVO = "Revisión manual del documento correspondiente."

# Bloque de medición del hallazgo de sesión (6.22/28510.0033/0057/0058, ANEJO
# de criterios técnicos): parte de las líneas pendientes no son un hueco real
# -- son la copia exacta (misma matrícula, descripción y precio) de un
# material que otro documento del mismo expediente ya declaró con su lote,
# típico de un anejo de referencia que repite el mismo cuadro sin volver a
# indicar el lote. Se cuentan aparte, nunca se funden ni se les asigna lote
# aquí (CONTEXTO.md sección 12 y el caso del balasto: comparar contenido
# entre filas para decidir un lote es precisamente el riesgo ya descartado) --
# esto es solo una categoría más legible en el Resumen, para separar "hueco
# real" de "ruido sin pérdida de información".
_CATEGORIA_DUPLICADO_SIN_PERDIDA = "duplicado de material ya incluido"
_EXPLICACION_DUPLICADO_SIN_PERDIDA = (
    "Este material (misma matrícula, descripción y precio) ya aparece en la hoja \"Materiales\" con su "
    "lote asignado, procedente de otro documento del mismo expediente -- esta copia es una repetición "
    "exacta, no un material distinto ni un hueco real."
)
_RESOLUCION_DUPLICADO_SIN_PERDIDA = "Ninguna: el material y su precio ya están en el catálogo entregado."


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
_EXPLICACIONES_MOTIVO[_CATEGORIA_DUPLICADO_SIN_PERDIDA] = (
    _EXPLICACION_DUPLICADO_SIN_PERDIDA, _RESOLUCION_DUPLICADO_SIN_PERDIDA
)

# CONTEXTO.md sección 6/7: de dónde sale "Código del material", explicado
# para que una celda vacía no parezca un defecto del entregable. Sesión
# 2026-09-14 (revisión del cliente): la nota decía "vacía en la mayoría de
# las filas", ya falso (el vocabulario y la vía de modelo la rellenan en
# torno a dos tercios del catálogo), y no contaba la columna REPUESTO del
# propio documento, que ahora manda cuando existe.
_NOTA_CODIGO_MATERIAL = (
    "La columna \"Código del material\" se toma de la columna de tipo de pieza del propio cuadro de "
    "precios cuando el documento la trae (\"REPUESTO\": Semicambio, Aguja, Cruzamiento...). Si no la trae, "
    "se deriva de la primera palabra de la descripción cuando el sistema la reconoce con seguridad (por "
    "ejemplo BRIDA, PLACA, JUNTA, TRAVIESA). Una celda vacía significa que no se ha reconocido ninguna "
    "de las dos -- no es un fallo de extracción ni un dato perdido: la descripción completa del material "
    "sí está siempre en la columna \"Descripción del material\"."
)


def _escribir_resumen(
    libro: Workbook,
    incluidas: int,
    excluidas_por_categoria: Counter[str],
    incluir_pendientes_sin_lote: bool,
    con_valor_de_otro_lote: int = 0,
) -> None:
    hoja = libro.create_sheet("Resumen")
    hoja.append(["Concepto", "Valor"])
    hoja.append(["Líneas en este catálogo", incluidas])
    total_excluidas = sum(excluidas_por_categoria.values())
    hoja.append(["Líneas pendientes de revisión (no incluidas arriba)", total_excluidas])
    hoja.append([
        "Líneas del catálogo con Cantidad o Precio unitario pendiente (el documento da un valor distinto "
        "para cada lote)",
        con_valor_de_otro_lote,
    ])
    hoja.append([])
    if incluir_pendientes_sin_lote:
        hoja.append(["Exportado con las líneas pendientes de revisión incluidas en \"Materiales\".", None])
    elif total_excluidas:
        hoja.append(["Por qué hay líneas pendientes de revisión", None])
        if excluidas_por_categoria.get(_CATEGORIA_DUPLICADO_SIN_PERDIDA):
            hoja.append([
                "La mayoría son materiales de los que no se sabe con seguridad a qué lote pertenecen, así "
                "que se han dejado fuera de la hoja \"Materiales\" para no mostrar el mismo material varias "
                "veces sin poder distinguir una repetición real de un error de lectura del documento. Otra "
                "parte, señalada aparte más abajo (\"duplicado de material ya incluido\"), no es un hueco "
                "real: es la misma matrícula, descripción y precio que ya aparece en \"Materiales\" desde "
                "otro documento del mismo expediente, así que ese material concreto no falta en el catálogo "
                "entregado. Ninguna de las dos se ha perdido -- ambas siguen guardadas.",
                None,
            ])
        else:
            hoja.append([
                "Son materiales de los que no se sabe con seguridad a qué lote pertenecen, así que se han "
                "dejado fuera de la hoja \"Materiales\" para no mostrar el mismo material varias veces sin "
                "poder distinguir una repetición real de un error de lectura del documento. Siguen "
                "guardados, no se han perdido.",
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
    hoja.append([
        "Columna \"Motivo de las celdas vacías\": por qué está vacía cada celda de datos de la fila. Las "
        "celdas se dejan vacías (una marca de texto impediría sumar u ordenar las columnas de números); el "
        "motivo va en esta columna, con uno de estos tres valores:",
        None,
    ])
    for motivo, explicacion in _LEYENDA_MOTIVOS:
        hoja.append([f"{motivo}: {explicacion}", None])
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
    con_valor_de_otro_lote = 0
    excluidas_por_categoria: Counter[str] = Counter()

    # Bloque de medición del hallazgo de sesión (ver comentario de
    # `_CATEGORIA_DUPLICADO_SIN_PERDIDA` más arriba): antes de decidir qué
    # línea excluida es un hueco real, hace falta conocer TODAS las que sí
    # se van a incluir -- de ahí las dos pasadas. Se bufferea la página
    # completa en memoria (unas pocas decenas de miles de filas, ligero)
    # en vez de hacer una segunda vuelta a la base de datos: paginar dos
    # veces duplicaría el tiempo de exportación sin necesidad.
    todas_las_filas: list[tuple[LineaCatalogo, object, object]] = []
    claves_incluidas: set[tuple[int, str, str, Optional[Decimal]]] = set()

    pagina = 1
    while True:
        # CONTEXTO.md bloque 2: una línea descartada en la cola de revisión no
        # sale en el Excel que se entrega al cliente, aunque siga en base de
        # datos con su motivo.
        resultado = consultar_catalogo(db, pagina=pagina, tamano_pagina=_TAMANO_LOTE, excluir_descartadas=True)
        for linea, lote, expediente, _documento, _nombre_archivo in resultado.filas:
            todas_las_filas.append((linea, lote, expediente))
            # Bloque 2 (auditoría 6.20/28510.0042/0046/0047): a diferencia de
            # una huérfana sin lote, aquí SÍ hay lote conocido -- se excluye
            # siempre, sin que `incluir_pendientes_sin_lote` la reincluya,
            # porque el problema no es "falta asignar lote" sino "no se
            # confía en cómo se leyeron las columnas de esta tabla" (ver
            # `MOTIVO_MAPEO_INCOHERENTE`).
            mapeo_incoherente = bool(linea.motivo_revision) and MOTIVO_MAPEO_INCOHERENTE in linea.motivo_revision
            se_incluye = not ((lote is None and not incluir_pendientes_sin_lote) or mapeo_incoherente)
            if se_incluye and linea.matricula is not None:
                claves_incluidas.add(
                    (expediente.id, linea.matricula, linea.descripcion, linea.precio_unitario)
                )
        if pagina * _TAMANO_LOTE >= resultado.total:
            break
        pagina += 1

    for linea, lote, expediente in todas_las_filas:
        mapeo_incoherente = bool(linea.motivo_revision) and MOTIVO_MAPEO_INCOHERENTE in linea.motivo_revision
        if (lote is None and not incluir_pendientes_sin_lote) or mapeo_incoherente:
            # Encargo de esta sesión (hallazgo real, `6.22/28510.0033`/`0057`/
            # `0058`: un anejo de "criterios técnicos" repite íntegro el mismo
            # cuadro de precios que ya trae, con lote asignado, otro
            # documento del expediente): antes de contar esta línea bajo su
            # motivo técnico, comprobar si es una copia exacta -- misma
            # matrícula, descripción y precio -- de un material que YA va a
            # salir en "Materiales". Nunca se funde ni se le asigna lote
            # aquí (CONTEXTO.md sección 12: comparar contenido entre filas
            # para decidir un lote es el riesgo ya descartado con el
            # balasto) -- esto es solo una categoría más honesta en el
            # Resumen, "hueco real" vs "ruido sin pérdida de información".
            clave = (expediente.id, linea.matricula, linea.descripcion, linea.precio_unitario)
            if linea.matricula is not None and clave in claves_incluidas:
                excluidas_por_categoria[_CATEGORIA_DUPLICADO_SIN_PERDIDA] += 1
            else:
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
            _celda_texto_o_espacio(expediente.codigo_interno if cruzado else None),
            _celda_texto_o_espacio(expediente.codigo_expediente if cruzado else None),
            _celda_texto_o_espacio(expediente.codigo_matriz),
            _celda_texto_o_espacio(expediente.nombre_proyecto),
            _celda_texto_o_espacio(_celda_matricula(linea)),
            _celda_texto_o_espacio(linea.descripcion),
            _celda_texto_o_espacio(_celda_texto(linea.codigo_material)),
            _celda_numero(linea.cantidad),
            _celda_numero(linea.precio_unitario),
            _celda_texto_o_espacio(lote.identificador_lote if lote else None),
            _celda_numero(linea.precio_adjudicado),
            _celda_numero(linea.baja_lote),
            _celda_texto_o_espacio(linea.unidad_medida),
            _celda_texto_o_espacio(expediente.estado_contrato_sap),
            # Siempre el dato del documento, nunca gated por `cruzado`
            # (ver comentario de `COLUMNAS` arriba) -- `codigo_expediente`
            # no es nullable (CONTEXTO.md sección 20: se corrige en el
            # sitio con el "Número de Expediente" propio del Anuncio
            # PCSP en cuanto se lee, `app.extraccion.identidad_expediente`).
            _celda_texto_o_espacio(expediente.codigo_expediente),
            _celda_texto_o_espacio(expediente.nombre_proyecto),
            _celda_texto_o_espacio(_texto_celdas_vacias(linea, lote.identificador_lote if lote else None)),
            _celda_texto_o_espacio(linea.comentarios),
        ])
        if any(
            c.motivo == PENDIENTE and c.campo in ("cantidad", "precio_unitario")
            for c in celdas_vacias(linea, lote.identificador_lote if lote else None)
        ):
            con_valor_de_otro_lote += 1
        hoja.cell(row=fila, column=_COLUMNA_CANTIDAD).number_format = _formato_cantidad(linea.cantidad)
        for columna in _COLUMNAS_IMPORTE:
            hoja.cell(row=fila, column=columna).number_format = _FORMATO_IMPORTE
        hoja.cell(row=fila, column=_COLUMNA_PORCENTAJE).number_format = _FORMATO_PORCENTAJE

    _escribir_resumen(
        libro, incluidas, excluidas_por_categoria, incluir_pendientes_sin_lote, con_valor_de_otro_lote
    )

    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()
