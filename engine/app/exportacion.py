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
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalogo import (
    MOTIVO_IMPORTE_SIN_PRECIO_NI_CONFIRMACION,
    MOTIVO_MAPEO_INCOHERENTE,
    MOTIVO_MATRICULA_8_FUERA_DEL_MAESTRO,
    MOTIVO_MATRICULA_FUERA_DEL_MAESTRO,
    extraer_texto_otra_cantidad,
)
from app.presupuestos_adif import (
    COLUMNAS as COLUMNAS_PRESUPUESTOS,
    NOMBRE_HOJA as NOMBRE_HOJA_PRESUPUESTOS,
    construir_presupuestos_adif,
)
from app.catalogo_consulta import consultar_catalogo, filtros_del_entregable
from app.contraste_presupuestos import (
    COLUMNAS as COLUMNAS_CONTRASTE,
    MOTIVOS_FUERA as MOTIVOS_FUERA_CONTRASTE,
    NOMBRE_HOJA as NOMBRE_HOJA_CONTRASTE,
    RESULTADOS as RESULTADOS_CONTRASTE,
    SIGNIFICADO as SIGNIFICADO_CONTRASTE,
    Contraste,
    construir_contraste,
)
from app.celdas_vacias import ETIQUETA_MOTIVO, PENDIENTE, celdas_vacias
from app.conciliacion import (
    COLUMNAS_CONCILIACION,
    EN_EJECUCION_SIN_FECHA,
    RegistroPublicado,
    SITUACIONES,
    comprobar_cuadre,
    construir_conciliacion,
    describir_registro_publicado,
)
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
    # Columnas del expediente (sesión 2026-09-18, bloque 2): hasta hoy una
    # celda vacía en cualquiera de estas cuatro no tenía motivo en ninguna
    # parte del entregable.
    "codigo_interno": "Código interno",
    "codigo_matriz": "Código matriz",
    # Un solo motivo para las dos columnas que salen del mismo campo.
    "titulo_expediente": "Título expediente y Objeto del contrato (documento)",
    "estado_contrato_sap": "Estado del contrato (SAP)",
    # Columnas de la línea.
    "codigo_precio": "Código de precio",
    "matricula": "Matrícula del material",
    "codigo_material": "Código del material",
    "cantidad": "Cantidad",
    "precio_unitario": "Precio unitario",
    "lote": "Lote",
    "precio_adjudicado": "Precio adjudicado",
    "baja_lote": "Baja del lote",
    "unidad_medida": "Unidad de medida",
}


TEXTO_UNIDAD_DEL_MAESTRO = (
    "Unidad de medida: del maestro de materiales de ADIF (el documento no la publica)"
)


def _texto_celdas_vacias(
    linea: LineaCatalogo, identificador_lote: Optional[str], expediente=None, modelo_precio=None
) -> Optional[str]:
    """"Cantidad: pendiente (el documento da una cantidad distinta para cada
    lote...); Matrícula del material: no consta" -- `None` si la fila no
    tiene ninguna celda vacía."""
    partes = [
        f"{_COLUMNA_DE_CAMPO[c.campo]}: {ETIQUETA_MOTIVO[c.motivo]}" + (f" ({c.detalle})" if c.detalle else "")
        for c in celdas_vacias(linea, identificador_lote, expediente, modelo_precio)
    ]
    # Sesión 2026-09-21 (tercera parte), encargo del cliente: la Cantidad de un
    # cuadro que solo trae «cantidad mínima por pedido» y «pedido inicial» no
    # está vacía, pero la fila tiene que decir cuál de las dos es y qué trae la
    # otra, para que nadie la tome por la cantidad total. Es la única columna
    # de motivos de la fila, así que va aquí (`app.catalogo.
    # texto_otra_cantidad`).
    otra_cantidad = extraer_texto_otra_cantidad(linea.motivo_revision)
    if otra_cantidad:
        partes.append(otra_cantidad)
    # Sesión 2026-09-22, encargo del cliente: la Unidad de medida que no sale
    # del documento sino del maestro de materiales de ADIF tampoco está vacía,
    # pero la fila tiene que decirlo.
    if linea.unidad_medida_completada_desde_maestro and linea.unidad_medida:
        partes.append(TEXTO_UNIDAD_DEL_MAESTRO)
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

# "Comentarios" está vacía en todas las filas por diseño y siempre por el mismo
# motivo (CONTEXTO.md sección 7: "Comentarios | Humano"). Repetirlo fila a fila
# en "Motivo de las celdas vacías" añadiría la misma frase a las ~18.000 filas
# y taparía los motivos que sí cambian de una fila a otra, que es justo lo que
# esa columna existe para destacar -- va aquí, una vez.
_NOTA_COMENTARIOS = (
    "La columna \"Comentarios\" está vacía en todas las filas a propósito: es la única que no rellena el "
    "sistema, está para que escriba en ella quien revise el catálogo. Por eso no lleva motivo fila a fila."
)

# Bloque 3, sesión 2026-09-18 (encargo del cliente): la nota doble sobre por
# qué un mismo material puede verse más de una vez. Son dos motivos distintos
# y los dos son legítimos -- verificados contra los documentos reales en la
# sesión 2026-09-16 (noche) para los 11 grupos que la auditoría venía marcando
# como error. Ninguna línea se funde ni se borra nunca por esto.
_NOTAS_MATERIAL_REPETIDO = (
    "Entre expedientes distintos: varios expedientes de una misma licitación pueden compartir el mismo "
    "cuadro de precios, así que el mismo material aparece una vez por cada uno de esos expedientes. No es "
    "una repetición por error: cada fila es la de su expediente.",
    "Dentro de un mismo expediente: el pliego puede listar el mismo material dos veces con dos códigos de "
    "precio distintos (por ejemplo, la misma pieza en dos apartados del cuadro). Las dos filas son las que "
    "trae el documento y se conservan tal cual; no se junta ni se elimina ninguna.",
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
    # objeto/título tal como lo declara el propio documento de la Plataforma.
    #
    # **"Nº de expediente (documento)" se quitó el 2026-09-18 (bloque 1,
    # decisión del cliente).** Existía porque "Código de expediente" solo se
    # rellenaba cuando el expediente cruzaba con el Excel de códigos, y hacía
    # falta una columna que trajera el número siempre. Desde que esa puerta
    # desapareció (bloque 1 de la sesión anterior, mismo fichero) las dos
    # columnas salían del mismo `expediente.codigo_expediente` y coincidían
    # en las 18.239 filas, sin una sola discrepancia: eran literalmente la
    # misma columna dos veces. Se queda "Código de expediente", que es el
    # nombre por el que el cliente filtra.
    "Objeto del contrato (documento)",
    # Sesión 2026-09-19 (segunda parte, decisión del cliente): la clave real
    # del catálogo (`expediente + lote + código de precio`, CONTEXTO.md
    # sección 7), que hasta hoy solo vivía dentro del sistema. Es lo único
    # que lleva una fila del Excel a su renglón del PDF, y se comprobó antes
    # de añadirla que **no se repite ni una sola vez** dentro de un mismo
    # expediente y lote: es un identificador de verdad, no un número
    # decorativo. Las 10.417 filas que la dejan vacía no son un hueco de
    # extracción sino cuadros que no numeran sus renglones, y eso lo dice la
    # columna "Motivo de las celdas vacías" (`app.celdas_vacias`).
    #
    # Va aquí, la última de las columnas que rellena el sistema, **sin mover
    # ninguna de las anteriores**: detrás quedan las dos que ya tenían su
    # sitio reservado al final por decisiones anteriores del cliente --
    # "Motivo de las celdas vacías" (sesión 2026-09-14, "justo antes de
    # Comentarios") y "Comentarios" (sesión 2026-09-09, "al final de todas",
    # la única que rellena una persona a mano).
    "Código de precio",
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
# Sesión 2026-09-14 (tercera parte): las líneas del anejo de criterios
# técnicos del conjunto de los lotes no esperan ninguna revisión -- el
# documento dice que son de todos los lotes. Se cuentan en su propia fila
# del Resumen, fuera de "pendientes de revisión".
_CATEGORIA_CRITERIOS = "anejo de criterios técnicos, común a todos los lotes"
_CATEGORIAS_MOTIVO = (
    # Sesión 2026-09-21 (tercera parte), bloque 2: el anejo que trae los
    # cuadros de todos los lotes, repartido por sus rótulos cuando el
    # expediente sabe qué lote es (`orquestador._quedarse_con_el_lote_propio`).
    (
        "este expediente es su lote",
        "cuadro de otro lote de la licitación, en un anejo común a todos los lotes",
        "El documento trae los cuadros de precios de todos los lotes de la licitación, cada uno con su "
        "rótulo «LOTE N», y este expediente es solo uno de esos lotes (lo dice el anuncio de la Plataforma). "
        "Estas filas son del cuadro de otro lote: no son de este expediente.",
        "Nada, si el expediente de ese otro lote está en el catálogo (allí salen). Si no lo está, habría que "
        "darlo de alta para que su material salga en «Materiales».",
    ),
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
        "anejo de criterios técnicos, que el documento declara del conjunto",
        _CATEGORIA_CRITERIOS,
        "Es la lista de materiales de la licitación entera (\"materiales a suministrar en el expediente ... "
        "N lotes\"): reúne los de todos los lotes con su propia numeración, y el propio documento dice que no "
        "coincide con el cuadro de precios. Cada material ya figura con su precio en el lote que lo compra.",
        "Nada, salvo que se quiera consultar la lista completa en el documento original.",
    ),
    (
        "otro lote de la licitación cuyo expediente no está en el catálogo",
        "tabla de otro lote, cuyo expediente no está en el catálogo",
        "La tabla es de otro lote de la misma licitación (otro contrato), cuyo expediente no está en el "
        "catálogo. No es de este expediente, así que no se muestra en él, pero se conserva.",
        "Nada en este expediente; si se incorpora el del otro lote, esas líneas saldrán allí.",
    ),
    (
        "última mención de lote antes de ella es",
        "tabla sin título de lote, detrás de la sección de otro lote",
        "La tabla no lleva título de lote, pero lo último que el documento dice antes de ella es de otro "
        "lote, así que no se atribuye al lote de este expediente.",
        "Que alguien mire el documento y confirme de qué lote es.",
    ),
    (
        # Bloque 6, sesión 2026-09-19. Va ANTES que "no está entre los lotes
        # declarados": las dos redacciones comparten esa frase y
        # `_categoria_motivo` se queda con el primer marcador que casa. Es el
        # motivo de la inmensa mayoría de las 2.752 líneas que el encargo
        # daba por "deberían tener lote" -- medido tabla a tabla, son las
        # páginas de continuación del cuadro de un lote hermano.
        "continuación del cuadro del LOTE",
        "continuación del cuadro de otro lote de la licitación",
        "La tabla no lleva título de lote propio porque es la página siguiente del cuadro de un lote "
        "hermano de la misma licitación. El material no es de este expediente: sale, con su lote, en el "
        "expediente de ese otro lote y en el principal de la licitación.",
        "Nada: la fila está donde le corresponde, en el expediente del lote que la compra.",
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
    (
        MOTIVO_IMPORTE_SIN_PRECIO_NI_CONFIRMACION,
        "cuadro sin precio unitario: solo publica el importe de cada renglón",
        "El cuadro de precios de este documento no publica ningún precio unitario -- su única columna de "
        "dinero es el IMPORTE de cada renglón, que es cantidad x precio --, y el precio que saldría de "
        "dividir ese importe entre la cantidad no queda demostrado: con él, la suma del lote no cuadra ni "
        "con un total declarado en el documento ni con el presupuesto de licitación publicado de ese lote. "
        "Publicarlo tal cual pondría el importe de un renglón entero en la columna de precio unitario.",
        "Que alguien abra el cuadro original y confirme el precio unitario de cada artículo, o que ADIF "
        "facilite el desglose.",
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
# Bloque 2, sesión 2026-09-19 (decisión del cliente, acotada). El único caso
# en que el Precio unitario de una fila NO es el número impreso en su celda
# del cuadro. Tiene que verse, igual que se ven las líneas de reconocimiento
# óptico: aquí el recuento, y en cada línea su motivo de revisión y la marca
# "[precio recalculado desde el importe del documento]" delante del fragmento
# que la ancla.
_ETIQUETA_PRECIO_DESDE_IMPORTE = (
    "Líneas cuyo Precio unitario se ha recalculado desde la columna de importes del propio documento "
    "(el precio impreso no cuadra con su renglón y el corregido cierra además el total del lote al céntimo)"
)
_NOTA_PRECIO_DESDE_IMPORTE = (
    "Esas líneas llevan un precio que NO es el que imprime su celda del cuadro: el documento imprime un "
    "precio que no cuadra con su propio renglón (cantidad × precio ≠ importe) y sí cuadra al dividir el "
    "importe entre la cantidad. Solo se reescribe cuando se cumplen las dos condiciones a la vez: que esa "
    "división sea exacta, y que con el precio corregido el lote sume exactamente uno de los totales que el "
    "propio documento declara al pie de su cuadro. Si falta cualquiera de las dos, la línea se deja tal cual "
    "y va a revisión. Cada línea corregida queda marcada y explicada en la cola de revisión."
)

# Bloque 1, decisión 5 del cliente (sesión 2026-09-19, sexta parte).
_ETIQUETA_DESCRIPCION_DESDE_REFERENCIA = (
    "Líneas cuya Descripción del material es la referencia que el documento imprime para el artículo "
    "(su cuadro de precios no publica ninguna otra columna de texto)"
)
_NOTA_DESCRIPCION_DESDE_REFERENCIA = (
    "En esas líneas, la columna \"Descripción del material\" no es una designación en prosa sino la "
    "referencia de fabricante que el documento imprime para el artículo (\"SFT01-2388L-PH-6920\", "
    "\"WCMX-04 02 08-R53\"): son cuadros de precios de insertos y herramienta de mecanizado cuya única "
    "columna de texto es esa. No falta ninguna descripción: el documento no publica otra. Cada línea queda "
    "marcada y explicada en la cola de revisión."
)

# Bloques 1 y 2, sesión 2026-09-19 (séptima parte, decisión del cliente): la
# matrícula que el documento imprime y el maestro de materiales de ADIF no
# recoge se queda literal, y la fila lleva su motivo. El motivo por línea vive
# en la cola de revisión; aquí va el recuento, para que quien abra el Excel
# sepa cuántas filas son y por qué, sin tener que entrar en la web.
_ETIQUETA_MATRICULA_8_FUERA_DEL_MAESTRO = (
    "Líneas cuya Matrícula del material tiene el formato antiguo de 8 dígitos y no figura en el maestro "
    "actual de ADIF"
)
_ETIQUETA_MATRICULA_FUERA_DEL_MAESTRO = (
    "Líneas cuya Matrícula del material (9 dígitos) no figura en el maestro de materiales de ADIF"
)
_NOTA_MATRICULAS_FUERA_DEL_MAESTRO = (
    "Esas matrículas son las que imprime el documento publicado, comprobadas contra su imagen, y se "
    "entregan literales: no se completan ni se corrigen para que casen con el maestro, porque el parecido "
    "no demuestra nada (\"64571017\" casa a la vez con una palomilla y con unas antenas). Las de 8 dígitos "
    "son el formato antiguo de ADIF, de pliegos de 2016-2018. Las de 9 son del formato de hoy, y lo que "
    "falta es su fila en el maestro: ese listado está incompleto artículo a artículo dentro de familias que "
    "sí conoce -- un pliego llega a comprar 28 referencias correlativas de las que el maestro trae 5. El "
    "día que ADIF envíe un maestro más completo, estas filas dejan de contarse aquí solas."
)

_NOTA_PRESUPUESTOS_ADIF = (
    "Esta hoja compara dos cifras que NO se mezclan nunca: el presupuesto de licitación que ADIF publica en "
    "su listado de estados, y el importe de licitación que este sistema leyó de un documento publicado en la "
    "Plataforma, con su documento y su página. Primero las coincidencias, después las diferencias de mayor a "
    "menor, y al final los expedientes de los que no se pudo leer ningún importe de los documentos. Una "
    "diferencia no dice cuál de las dos cifras está mal: dice que hay que mirar ese expediente."
)

_NOTA_CODIGO_MATERIAL = (
    "La columna \"Código del material\" se toma de la columna de tipo de pieza del propio cuadro de "
    "precios cuando el documento la trae (\"REPUESTO\": Semicambio, Aguja, Cruzamiento...). Si no la trae, "
    "se deriva de la primera palabra de la descripción cuando el sistema la reconoce con seguridad (por "
    "ejemplo BRIDA, PLACA, JUNTA, TRAVIESA). Una celda vacía significa que no se ha reconocido ninguna "
    "de las dos -- no es un fallo de extracción ni un dato perdido: la descripción completa del material "
    "sí está siempre en la columna \"Descripción del material\"."
)


# Bloque 5, sesión 2026-09-18 (encargo del cliente). Lo que la hoja
# "Conciliación" contesta, dicho una vez en el Resumen: por qué existe, qué
# lista es, y las dos cosas que en ella se quedan en blanco por falta de
# origen, no por falta de lectura.
_NOTA_CONCILIACION = (
    "La hoja \"Conciliación\" lleva una fila por cada expediente del departamento que consta publicado en "
    "la Plataforma -- bajo su propio número o dentro de la ficha del expediente principal de su "
    "licitación, cuando es uno de sus lotes --, aporte líneas al catálogo o no, con cuántos documentos se le descargaron, cuántos se "
    "leyeron con reconocimiento óptico, cuántas líneas aporta y, cuando no aporta ninguna, por qué. Sirve "
    "para comprobar que no falta nada por leer sin tener que suponerlo: la suma de su columna de líneas es "
    "exactamente el número de filas de la hoja \"Materiales\"."
)
_NOTA_CONCILIACION_HUECOS = (
    "En esa hoja, \"Órgano de contratación\" solo se rellena para los expedientes que ha listado la "
    "sindicación mensual, que es la vía que trae ese dato. Los que se conocen solo por la búsqueda directa "
    "en el buscador de la Plataforma salen con esa celda explicada: el buscador devuelve el número de "
    "expediente, no su ficha."
)
# Bloque 6, sesión 2026-09-18 (quinta parte): la columna de estado ya no sale
# solo de la sindicación, y el cliente ya tiene esa columna delante -- el
# cambio tiene que estar escrito en el propio Excel, no solo en el registro de
# la sesión.
_NOTA_ESTADO_PUBLICADO = (
    "La columna \"Estado que consta publicado en la Plataforma\" sale del boletín mensual de sindicación "
    "y, cuando el sistema ya tiene descargado de la Plataforma un documento que prueba una etapa "
    "posterior (la Resolución de Adjudicación, o el Contrato/Anuncio de formalización), de ese documento: "
    "un boletín refleja el evento del mes en que se publicó, no lo que sigue vigente, así que quedarse "
    "con él sería quedarse con el dato más viejo de los dos. Cuando manda el documento, la celda lo dice "
    "y dice también lo que decía el último boletín. Nunca al revés: la columna solo avanza de etapa, "
    "jamás retrocede, y una \"Anulada\" del boletín no la deshace ningún documento. El último estado al "
    "que puede llegar esta columna es \"Resuelta\": sin acceso a SAP no hay nada publicado de lo que leer "
    "un estado posterior del contrato, y esos los indica ADIF (decisión de ADIF del 18/09/2026)."
)
# Bloque 3, sesión 2026-09-18 (continuación). La columna "Estado según ADIF"
# es de OTRA fuente, y eso tiene que estar dicho en el Excel, no solo sabido:
# quien lo abra tiene que poder distinguir de un vistazo qué columna viene de
# la Plataforma y cuál nos la ha dado ADIF.
_NOTA_ESTADO_ADIF = (
    "La columna \"Estado según ADIF\" de esa hoja NO sale de la Plataforma: es el estado de contratación "
    "que ADIF nos envió el 18/09/2026 en un listado de 358 expedientes del departamento, sacado por ellos "
    "de una transacción de SAP y facilitado con su autorización expresa. Se escribe tal cual viene en su "
    "listado, sin traducir. La columna de al lado, \"Estado que consta publicado en la Plataforma\", es "
    "otra cosa y de otra fuente: el estado del anuncio en la Plataforma. Las dos se dejan separadas a "
    "propósito. Ese listado no interviene en ningún momento en decidir si un expediente consta publicado "
    "o no -- eso lo decide solo la Plataforma."
)


# Bloque 2, sesión 2026-09-21: la columna "En ejecución según ADIF" de
# "Conciliación" sale de una tercera fuente, y hay que decir cuál.
_PROCEDENCIA_EN_EJECUCION = {
    "expedientes_en_ejecucion_adif_20260921.csv": (
        "compartido por ADIF en el grupo de trabajo el 18/09/2026 y reenviado ordenado el 21/09/2026"
    ),
}


def _nota_en_ejecucion_adif(registro: RegistroPublicado) -> str:
    if not registro.listado_en_ejecucion_adif:
        return (
            "La columna \"En ejecución según ADIF\" de esa hoja está vacía: todavía no se ha cargado "
            "ningún listado de expedientes en ejecución de ADIF."
        )
    procedencia = _PROCEDENCIA_EN_EJECUCION.get(registro.listado_en_ejecucion_adif)
    return (
        "La columna \"En ejecución según ADIF\" de esa hoja NO sale de la Plataforma: es la fecha de firma "
        "del acta de inicio que da el listado interno de ADIF de sus expedientes en ejecución ("
        f"{registro.listado_en_ejecucion_adif}"
        + (f", {procedencia}" if procedencia else "")
        + f"). La llevan {registro.en_ejecucion_adif_en_la_hoja} expedientes de la hoja; \""
        f"{EN_EJECUCION_SIN_FECHA}\" quiere decir que el listado lo incluye pero deja la fecha en blanco, "
        "y la celda vacía, que el expediente no figura en él. Está separada de las dos columnas de estado "
        "a propósito, y, como el listado de estados, no interviene en ningún momento en decidir si un "
        "expediente consta publicado ni en su Situación: eso lo decide solo la Plataforma."
    )


def _escribir_conciliacion(libro: Workbook, filas: list) -> None:
    hoja = libro.create_sheet("Conciliación")
    hoja.append(COLUMNAS_CONCILIACION)
    for fila in filas:
        hoja.append([
            _celda_texto_o_espacio(fila.codigo_expediente),
            _celda_texto_o_espacio(fila.titulo),
            _celda_texto_o_espacio(fila.organo_contratacion),
            _celda_texto_o_espacio(fila.estado_plataforma),
            _celda_texto_o_espacio(fila.estado_adif),
            fila.documentos_descargados,
            fila.documentos_reconocimiento_optico,
            fila.lineas_en_catalogo,
            _celda_texto_o_espacio(fila.baja),
            _celda_texto_o_espacio(fila.situacion),
            _celda_texto_o_espacio(fila.motivo),
            _celda_texto_o_espacio(fila.en_ejecucion_adif),
        ])
    for columna, ancho in zip("ABCDEFGHIJKL", (22, 55, 32, 30, 24, 12, 14, 12, 55, 30, 80, 22)):
        hoja.column_dimensions[columna].width = ancho
    for fila_hoja in hoja.iter_rows(min_row=2):
        for celda in fila_hoja:
            if isinstance(celda.value, str) and len(celda.value) > 60:
                celda.alignment = Alignment(wrap_text=True, vertical="top")


# Bloque 2, sesión 2026-09-19 (sexta parte): el contraste del presupuesto que
# ADIF publica contra el que el sistema lee de los documentos. Ver
# `app.presupuestos_adif` -- y, en particular, por qué la hoja no se escribe
# cuando no hay ningún presupuesto cargado.
def _escribir_presupuestos_adif(libro: Workbook, filas: list) -> None:
    if not filas:
        return
    hoja = libro.create_sheet(NOMBRE_HOJA_PRESUPUESTOS)
    hoja.append(list(COLUMNAS_PRESUPUESTOS))
    for fila in filas:
        hoja.append([
            _celda_texto_o_espacio(fila.codigo_expediente),
            _celda_texto_o_espacio(fila.titulo),
            _celda_numero(fila.presupuesto_adif),
            _celda_numero(fila.importe_documentos),
            _celda_numero(fila.diferencia),
            _celda_numero(fila.diferencia_relativa),
            _celda_texto_o_espacio(fila.resultado),
        ])
    for columna, ancho in zip("ABCDEFG", (22, 55, 30, 34, 26, 18, 34)):
        hoja.column_dimensions[columna].width = ancho
    for indice in range(2, hoja.max_row + 1):
        for columna in (3, 4, 5):
            hoja.cell(row=indice, column=columna).number_format = _FORMATO_IMPORTE
        hoja.cell(row=indice, column=6).number_format = _FORMATO_PORCENTAJE
    hoja.append([])
    hoja.append([_NOTA_PRESUPUESTOS_ADIF, None])


# Bloque 1, sesión 2026-09-21: la suma de cantidad × precio de cada lote
# contra su presupuesto publicado. Ver `app.contraste_presupuestos`, en
# particular contra qué cifra se compara y cómo se sabe qué cifra es.
_NOTA_CONTRASTE = (
    "Una fila por lote con filas en \"Materiales\" y un presupuesto de licitación publicado para ese "
    "lote. La suma es la de cantidad × precio unitario de sus filas de \"Materiales\", exactamente "
    "las mismas. Se compara con la cifra equivalente: los precios de un cuadro son sin IVA, así que "
    "con la base de licitación sin IVA; y si la suma multiplicada por 1,15 da esa base a un céntimo, "
    "el cuadro está a precios de ejecución material y se compara con la ejecución material. Qué cifra "
    "es cada presupuesto lo dice la etiqueta con la que se publicó; si la etiqueta no lo dice, la fila "
    "lo avisa en vez de suponerlo. Una partida alzada sin cantidad cuenta una vez: es cantidad 1 por "
    "definición. Esta hoja es una comprobación: no cambia ningún dato del catálogo."
)


def _escribir_contraste(libro: Workbook, contraste: Contraste) -> None:
    hoja = libro.create_sheet(NOMBRE_HOJA_CONTRASTE)
    hoja.append(list(COLUMNAS_CONTRASTE))
    for fila in contraste.filas:
        hoja.append([
            _celda_texto_o_espacio(fila.codigo_expediente),
            _celda_texto_o_espacio(fila.lote),
            _celda_numero(fila.presupuesto_publicado),
            _celda_texto_o_espacio(fila.tipo_cifra),
            _celda_numero(fila.cifra_comparada),
            _celda_texto_o_espacio(fila.documento),
            fila.pagina,
            _celda_numero(fila.suma_lineas),
            _celda_numero(fila.diferencia),
            _celda_numero(fila.diferencia_relativa),
            fila.lineas,
            fila.lineas_sin_cantidad,
            _celda_texto_o_espacio(fila.resultado),
            _celda_texto_o_espacio(fila.explicacion),
        ])
    for columna, ancho in zip("ABCDEFGHIJKLMN", (20, 8, 18, 40, 18, 30, 8, 20, 16, 12, 8, 10, 30, 90)):
        hoja.column_dimensions[columna].width = ancho
    for indice in range(2, hoja.max_row + 1):
        for columna in (3, 5, 8, 9):
            hoja.cell(row=indice, column=columna).number_format = _FORMATO_IMPORTE
        hoja.cell(row=indice, column=10).number_format = "0.0000%"
        for columna in (4, 14):
            celda = hoja.cell(row=indice, column=columna)
            celda.alignment = Alignment(wrap_text=True, vertical="top")
    hoja.append([])
    hoja.append([_NOTA_CONTRASTE, None])
    hoja.append([])
    hoja.append(["Resultado", "Lotes", "Qué significa"])
    por_resultado = contraste.por_resultado()
    for resultado in RESULTADOS_CONTRASTE:
        hoja.append([resultado, por_resultado[resultado], SIGNIFICADO_CONTRASTE[resultado]])
    hoja.append(["Total de lotes contrastados", len(contraste.filas), None])
    hoja.append([])
    hoja.append(["Lotes con filas en \"Materiales\" que no entran en el contraste, y por qué", "Lotes", None])
    por_motivo = contraste.por_motivo_fuera()
    for motivo in MOTIVOS_FUERA_CONTRASTE:
        hoja.append([motivo, por_motivo[motivo], None])
    hoja.append(["Total de lotes que no entran", len(contraste.fuera), None])


def _escribir_bloque_conciliacion(hoja, filas: list, registro: RegistroPublicado) -> None:
    """El recuento por Situación y, como pidió el cliente, **de qué fecha es
    el registro de lo publicado y qué cubre**, escrito en el propio Excel
    "para que nadie tenga que suponerlo"."""
    hoja.append([])
    hoja.append(["Conciliación con lo publicado en la Plataforma", None])
    hoja.append([_NOTA_CONCILIACION, None])
    hoja.append([_NOTA_CONCILIACION_HUECOS, None])
    hoja.append([_NOTA_ESTADO_ADIF, None])
    hoja.append([_NOTA_ESTADO_PUBLICADO, None])
    hoja.append([_nota_en_ejecucion_adif(registro), None])
    hoja.append([])
    hoja.append(["De qué fecha es el registro de lo publicado y qué cubre", None])
    departamentos = ", ".join(registro.departamentos) or "(sin departamento configurado)"
    hoja.append([f"Departamento(s) que cubre esta lista: {departamentos}. Entra todo expediente cuyo "
                 "código contenga esos dígitos, de cualquier año, en cualquier estado y de cualquier tipo "
                 "de procedimiento.", None])
    if registro.periodos_sindicacion:
        primero = _periodo_legible(registro.periodos_sindicacion[0])
        ultimo = _periodo_legible(registro.periodos_sindicacion[-1])
        hoja.append([
            f"Sindicación mensual de la Plataforma: leídos {len(registro.periodos_sindicacion)} "
            f"boletín(es) mensual(es), de {primero} a {ultimo}."
            + (
                f" El dato más reciente que traen es del {registro.sindicacion_actualizado_hasta:%d/%m/%Y}."
                if registro.sindicacion_actualizado_hasta
                else ""
            ),
            None,
        ])
    else:
        hoja.append(["Sindicación mensual de la Plataforma: todavía no se ha leído ningún boletín.", None])
    if registro.busqueda_ejecutada_en:
        fragmentos = ", ".join(registro.busqueda_fragmentos) or "(los departamentos de arriba)"
        encontrados = (
            f" Devolvió {registro.busqueda_codigos_encontrados} expediente(s)."
            if registro.busqueda_codigos_encontrados is not None
            else ""
        )
        hoja.append([
            f"Búsqueda directa en el buscador de la Plataforma: última ejecución el "
            f"{registro.busqueda_ejecutada_en:%d/%m/%Y a las %H:%M} (UTC), buscando \"{fragmentos}\" en el "
            f"campo \"Nº de expediente\".{encontrados}",
            None,
        ])
    else:
        hoja.append(["Búsqueda directa en el buscador de la Plataforma: sin ninguna ejecución registrada.",
                     None])
    hoja.append([
        f"Expedientes que constan publicados y salen en \"Conciliación\": {registro.expedientes_publicados}. "
        f"Además, {registro.expedientes_no_publicados} expediente(s) que se buscaron uno a uno y la "
        "Plataforma confirmó que no publica: no salen en la hoja, porque no hay nada que leer de ellos.",
        None,
    ])
    if registro.expedientes_en_ficha_de_otro:
        # Bloque 3, sesión 2026-09-18 (quinta parte): antes de este cambio
        # estos caían en la frase de arriba, contados como "la Plataforma
        # confirmó que no publica". Es falso: lo que no publica es su ficha.
        hoja.append([
            f"De los que la Plataforma no devuelve al buscarlos por su número, "
            f"{registro.expedientes_en_ficha_de_otro} SÍ están publicados: son lotes de otra licitación "
            "y sus documentos se publican dentro de la ficha del expediente principal, no bajo su propio "
            "número. Esos sí salen en la hoja, con la situación \"Publicado dentro de la ficha de otro "
            "expediente\" y el número de quién los publica.",
            None,
        ])
    hoja.append([])
    hoja.append(["Situación", "Expedientes", None])
    recuento = Counter(fila.situacion for fila in filas)
    for situacion in SITUACIONES:
        hoja.append([situacion, recuento.get(situacion, 0), None])
    hoja.append(["Total", sum(recuento.values()), None])
    hoja.append([
        "Líneas que suman entre todos (tiene que ser el número de filas de \"Materiales\")",
        sum(fila.lineas_en_catalogo for fila in filas),
        None,
    ])


def _periodo_legible(periodo: str) -> str:
    if len(periodo) == 6 and periodo.isdigit():
        return f"{periodo[4:]}/{periodo[:4]}"
    return periodo


def _escribir_resumen(
    libro: Workbook,
    incluidas: int,
    excluidas_por_categoria: Counter[str],
    incluir_pendientes_sin_lote: bool,
    con_valor_de_otro_lote: int = 0,
    del_anejo_de_criterios: int = 0,
    precios_corregidos_desde_importe: int = 0,
    descripciones_desde_referencia: int = 0,
    matriculas_8_fuera_del_maestro: int = 0,
    matriculas_fuera_del_maestro: int = 0,
    filas_conciliacion: Optional[list] = None,
    registro_publicado: Optional[RegistroPublicado] = None,
) -> None:
    hoja = libro.create_sheet("Resumen")
    hoja.append(["Concepto", "Valor"])
    hoja.append(["Líneas en este catálogo", incluidas])
    total_excluidas = sum(excluidas_por_categoria.values())
    hoja.append(["Líneas pendientes de revisión (no incluidas arriba)", total_excluidas])
    hoja.append([
        "Líneas del anejo de criterios técnicos, común a todos los lotes (no incluidas arriba: es la lista de "
        "materiales de la licitación entera, con su propia numeración; los de cada lote figuran con su precio "
        "en el cuadro de ese lote)",
        del_anejo_de_criterios,
    ])
    hoja.append([
        "Líneas del catálogo con Cantidad o Precio unitario pendiente (el documento da un valor distinto "
        "para cada lote)",
        con_valor_de_otro_lote,
    ])
    # Bloque 2, sesión 2026-09-19 (decisión del cliente): la fila corregida
    # tiene que verse, igual que las de reconocimiento óptico. Se cuenta
    # aquí, y cada línea lleva además su motivo y la marca en el fragmento.
    hoja.append([_ETIQUETA_PRECIO_DESDE_IMPORTE, precios_corregidos_desde_importe])
    hoja.append([_ETIQUETA_DESCRIPCION_DESDE_REFERENCIA, descripciones_desde_referencia])
    hoja.append([_ETIQUETA_MATRICULA_8_FUERA_DEL_MAESTRO, matriculas_8_fuera_del_maestro])
    hoja.append([_ETIQUETA_MATRICULA_FUERA_DEL_MAESTRO, matriculas_fuera_del_maestro])
    hoja.append([])
    if matriculas_8_fuera_del_maestro or matriculas_fuera_del_maestro:
        hoja.append([_NOTA_MATRICULAS_FUERA_DEL_MAESTRO, None])
        hoja.append([])
    if precios_corregidos_desde_importe:
        hoja.append([_NOTA_PRECIO_DESDE_IMPORTE, None])
        hoja.append([])
    if descripciones_desde_referencia:
        hoja.append([_NOTA_DESCRIPCION_DESDE_REFERENCIA, None])
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
        "Columna \"Motivo de las celdas vacías\": por qué está vacía cada celda de la fila. Las "
        "celdas se dejan vacías (una marca de texto impediría sumar u ordenar las columnas de números); el "
        "motivo va en esta columna, con uno de estos tres valores:",
        None,
    ])
    for motivo, explicacion in _LEYENDA_MOTIVOS:
        hoja.append([f"{motivo}: {explicacion}", None])
    hoja.append([_NOTA_COMENTARIOS, None])
    hoja.append([])
    hoja.append(["Nota sobre la columna \"Código del material\"", None])
    hoja.append([_NOTA_CODIGO_MATERIAL, None])
    hoja.append([])
    hoja.append(["Nota sobre los materiales que aparecen repetidos", None])
    for nota in _NOTAS_MATERIAL_REPETIDO:
        hoja.append([nota, None])
    if filas_conciliacion is not None and registro_publicado is not None:
        _escribir_bloque_conciliacion(hoja, filas_conciliacion, registro_publicado)
    for fila in hoja.iter_rows():
        for celda in fila:
            if isinstance(celda.value, str) and len(celda.value) > 60:
                celda.alignment = Alignment(wrap_text=True, vertical="top")
    hoja.column_dimensions["A"].width = 90
    hoja.column_dimensions["B"].width = 12
    hoja.column_dimensions["C"].width = 60


# Bloque 5, sesión 2026-09-19 (quinta parte): la decisión de "esta línea sale
# en Materiales" vive en UN sitio. La vista de Conciliación de la web necesita
# el mismo recuento por expediente que escribe el Excel -- si las dos cifras
# pudieran discrepar, la vista dejaría de servir para lo único que existe
# (docstring de `app.conciliacion`), y duplicar el criterio es exactamente
# como empiezan a discrepar.
# Los motivos que sacan una línea del entregable entero, no solo la marcan.
# Los dos dicen lo mismo: el documento no publica el dato y lo que se
# escribiría en su celda sería un número inventado.
_MOTIVOS_FUERA_DEL_ENTREGABLE = (
    MOTIVO_MAPEO_INCOHERENTE,
    # Bloque 1, decisión 1 del cliente (sesión 2026-09-19, sexta parte): el
    # cuadro cuya única columna de dinero es el IMPORTE del renglón, cuando la
    # suma del lote no confirma el precio que saldría de la división.
    MOTIVO_IMPORTE_SIN_PRECIO_NI_CONFIRMACION,
)


def _sale_en_materiales(
    motivo_revision: Optional[str], tiene_lote: bool, incluir_pendientes_sin_lote: bool
) -> bool:
    fuera = bool(motivo_revision) and any(m in motivo_revision for m in _MOTIVOS_FUERA_DEL_ENTREGABLE)
    return not ((not tiene_lote and not incluir_pendientes_sin_lote) or fuera)


def linea_sale_en_materiales(linea, lote, incluir_pendientes_sin_lote: bool = False) -> bool:
    return _sale_en_materiales(linea.motivo_revision, lote is not None, incluir_pendientes_sin_lote)


def contar_filas_de_materiales(
    db: Session, incluir_pendientes_sin_lote: bool = False
) -> Counter[int]:
    """Las filas que `generar_excel_catalogo` escribiría en "Materiales", por
    `Expediente.id`.

    Mismos filtros que el Excel (`app.catalogo_consulta.filtros_del_entregable`,
    incluidas las dos listas de exclusión) y **el mismo criterio de inclusión**
    (`linea_sale_en_materiales`), pero en una sola consulta de tres columnas:
    el Excel necesita cada línea entera y la pagina de 500 en 500 con cuatro
    joins y su orden de completitud -- para contar no hace falta nada de eso,
    y la vista de Conciliación de la web no puede tardar minutos."""
    conteo: Counter[int] = Counter()
    for expediente_id, lote_id, motivo in db.execute(
        filtros_del_entregable(
            select(
                LineaCatalogo.expediente_id, LineaCatalogo.lote_id, LineaCatalogo.motivo_revision
            )
        )
    ):
        if _sale_en_materiales(motivo, lote_id is not None, incluir_pendientes_sin_lote):
            conteo[expediente_id] += 1
    return conteo


def generar_excel_catalogo(db: Session, incluir_pendientes_sin_lote: bool = False) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Materiales"
    hoja.append(COLUMNAS)

    incluidas = 0
    con_valor_de_otro_lote = 0
    del_anejo_de_criterios = 0
    # Bloque 2, sesión 2026-09-19: solo las que de verdad salen en
    # "Materiales" -- una línea corregida que se quede fuera del entregable
    # no tiene por qué contarse en su Resumen.
    precios_corregidos_desde_importe = 0
    descripciones_desde_referencia = 0
    matriculas_8_fuera_del_maestro = 0
    matriculas_fuera_del_maestro = 0
    excluidas_por_categoria: Counter[str] = Counter()
    # Bloque 5, sesión 2026-09-18: las filas que de verdad se escriben en
    # "Materiales", por expediente. La hoja "Conciliación" se construye con
    # este recuento, nunca con una consulta propia -- si las dos cifras
    # pudieran discrepar, la hoja dejaría de servir para lo único que existe
    # (docstring de `app.conciliacion`).
    lineas_por_expediente: Counter[int] = Counter()
    # Bloque 1, sesión 2026-09-21: las mismas filas, por lote, para la hoja
    # "Contraste de presupuestos" -- que sume exactamente lo que se entrega.
    lineas_por_lote: dict[int, list[LineaCatalogo]] = {}

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
            se_incluye = linea_sale_en_materiales(linea, lote, incluir_pendientes_sin_lote)
            if se_incluye and linea.matricula is not None:
                claves_incluidas.add(
                    (expediente.id, linea.matricula, linea.descripcion, linea.precio_unitario)
                )
        if pagina * _TAMANO_LOTE >= resultado.total:
            break
        pagina += 1

    for linea, lote, expediente in todas_las_filas:
        if not linea_sale_en_materiales(linea, lote, incluir_pendientes_sin_lote):
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
            categoria = _categoria_motivo(linea.motivo_revision)
            if categoria == _CATEGORIA_CRITERIOS:
                del_anejo_de_criterios += 1
            elif linea.matricula is not None and clave in claves_incluidas:
                excluidas_por_categoria[_CATEGORIA_DUPLICADO_SIN_PERDIDA] += 1
            else:
                excluidas_por_categoria[categoria] += 1
            continue
        incluidas += 1
        lineas_por_expediente[expediente.id] += 1
        if lote is not None:
            lineas_por_lote.setdefault(lote.id, []).append(linea)
        if linea.precio_corregido_desde_importe:
            precios_corregidos_desde_importe += 1
        if linea.descripcion_desde_referencia:
            descripciones_desde_referencia += 1
        if linea.motivo_revision and MOTIVO_MATRICULA_8_FUERA_DEL_MAESTRO in linea.motivo_revision:
            matriculas_8_fuera_del_maestro += 1
        elif linea.motivo_revision and MOTIVO_MATRICULA_FUERA_DEL_MAESTRO in linea.motivo_revision:
            matriculas_fuera_del_maestro += 1
        # "El sistema nunca inventa una matriz. Si no cruza, se deja
        # vacío" (CONTEXTO.md sección 7): el "Código interno" sí sale del
        # Excel de códigos de ADIF, así que sin cruce no hay nada que
        # escribir.
        cruzado = bool(expediente.codigos_cruzados)
        fila = hoja.max_row + 1
        hoja.append([
            _celda_texto_o_espacio(expediente.codigo_interno if cruzado else None),
            # Sesión 2026-09-18, bloque 1 (decisión del cliente). Esta columna
            # NO sale del Excel de códigos de ADIF: es el `codigo_expediente`
            # propio del sistema, el mismo valor que "Nº de expediente
            # (documento)". Hasta hoy el cruce actuaba de interruptor sobre
            # ella -- sin cruce, la celda salía vacía aunque el número se
            # conociera perfectamente --, y el cliente filtraba por esta
            # columna y concluía que faltaban expedientes que sí están (caso
            # real repetido tres veces: `docs/sesion-2026-09-15-expedientes-
            # 2026-presidencia.md`, `...-unidades-y-cobertura-2026.md`,
            # `...-2026-09-16-descubrimiento-por-busqueda.md`). El número del
            # expediente se rellena siempre que se conozca, venga del cruce o
            # del propio documento. El cruce sigue gobernando en exclusiva
            # las tres columnas que sí dependen de él: "Código interno"
            # (arriba), "Código matriz" y "Estado del contrato (SAP)".
            _celda_texto_o_espacio(expediente.codigo_expediente),
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
            _celda_texto_o_espacio(expediente.nombre_proyecto),
            _celda_texto_o_espacio(_celda_texto(linea.codigo_precio)),
            _celda_texto_o_espacio(
                _texto_celdas_vacias(
                    linea, lote.identificador_lote if lote else None, expediente,
                    lote.modelo_precio if lote else None,
                )
            ),
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

    # Bloque 5, sesión 2026-09-18 (encargo del cliente). `comprobar_cuadre`
    # revienta si la suma no da el número de filas de "Materiales" o si algún
    # expediente se queda sin Situación: nunca se entrega un Excel
    # descuadrado, que es justo la clase de dato que esta hoja existe para
    # descartar.
    filas_conciliacion = construir_conciliacion(db, dict(lineas_por_expediente))
    comprobar_cuadre(filas_conciliacion, incluidas)
    registro = describir_registro_publicado(db, filas_conciliacion)
    _escribir_conciliacion(libro, filas_conciliacion)
    _escribir_contraste(libro, construir_contraste(db, lineas_por_lote))
    _escribir_presupuestos_adif(libro, construir_presupuestos_adif(db))

    _escribir_resumen(
        libro, incluidas, excluidas_por_categoria, incluir_pendientes_sin_lote, con_valor_de_otro_lote,
        del_anejo_de_criterios, precios_corregidos_desde_importe, descripciones_desde_referencia,
        matriculas_8_fuera_del_maestro, matriculas_fuera_del_maestro,
        filas_conciliacion, registro,
    )

    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()
