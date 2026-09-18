"""Auditoría automática del catálogo (BLOQUE 1, sesión 2026-09-08): un tipo
de trabajo más de la cola (CONTEXTO.md sección 10, "no un script suelto"),
encolado automáticamente al terminar cada ciclo de mantenimiento
(`app.mantenimiento.ciclo.ejecutar_ciclo_mantenimiento`) -- nunca un
segundo proceso, nunca en segundo plano fuera de la cola.

Encargo explícito de esta sesión: **esta auditoría no corrige nada por su
cuenta, solo detecta y avisa.** Cada comprobación es de solo lectura sobre
el estado actual de la base de datos; lo que encuentre va al informe
(`trabajos_cola.resultado`, igual que cualquier otro trabajo), nunca a un
UPDATE.

Los defectos reales que motivan cada comprobación de aquí abajo ya
aparecieron alguna vez en el corpus, siempre encontrados a mano (CONTEXTO.md
sección 16): colisión de hash entre expedientes hermanos, firma de cabecera
vacía compartida entre tablas de estructura distinta, líneas sin
expediente/descripción/lote, precios a cero, duplicados por clave inestable.
El objetivo de este módulo es que la próxima vez que aparezca algo de esta
familia (u otra parecida) lo señale un informe, no una revisión manual.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.extraccion.firma_cabecera import calcular_firma_cabecera
from app.models import (
    DocumentoExpediente,
    EstadoRevisionLinea,
    Expediente,
    EstadoTrabajo,
    LineaCatalogo,
    Lote,
    MapeoCabeceraCache,
    TrabajoCola,
)

TIPO_TRABAJO = "auditoria_catalogo"

# Cuántos códigos de expediente se listan por hallazgo -- suficiente para
# empezar a mirar sin volcar centenares de códigos en un JSON que nadie va a
# leer entero; `total_afectados` siempre lleva la cifra real, aunque la
# lista se recorte.
_LIMITE_EXPEDIENTES = 25

# Columnas del catálogo cuyo relleno se sigue columna a columna entre
# ejecuciones. `matricula` y `codigo_material` quedan fuera a propósito: su
# vacío alto es un hallazgo ya documentado y esperado (CONTEXTO.md secciones
# 2 y 6 -- matrícula falta en ~1/3 de las filas por diseño, código de
# material depende de un vocabulario controlado todavía en crecimiento), no
# una regresión que esta auditoría deba señalar cada vez que corre.
_COLUMNAS_SEGUIDAS = ["codigo_precio", "cantidad", "precio_unitario", "unidad_medida", "lote_id"]

# Aviso si el vacío de una columna seguida crece más de esto (puntos
# porcentuales) respecto a la ejecución anterior -- un salto real de
# cobertura entre dos corpus casi idénticos, no ruido de redondeo.
_UMBRAL_CRECIMIENTO_VACIO_PUNTOS = 5.0

# Un precio unitario a más de 50x o menos de 1/50 de la mediana de su propio
# expediente es la misma vara de medir que ya usó la sesión de verificación
# del Excel (2026-09-06, bloque 3: precio máximo 1.020.000 € frente a
# mínimo 0,142 €, los dos legítimos -- partida alzada de imprevistos y
# precio por tonelada-kilómetro de transporte). Aviso, no error: el corpus
# real ya tiene heterogeneidad legítima de magnitud dentro de un mismo
# expediente.
_RATIO_PRECIO_ATIPICO = 50
# Con menos de esto, la mediana del expediente es demasiado poco fiable
# para juzgar una línea contra ella (un expediente de 1-2 líneas no tiene
# "mediana" en ningún sentido útil).
_MINIMO_LINEAS_PARA_MEDIANA = 3

# Cantidad con forma de año (CONTEXTO.md sección 16, hallazgo de la sesión
# 2026-09-07): entero sin decimales dentro de este rango. La cascada ya
# descarta esto al extraer (`_construir_campos`); esta comprobación es la
# red de seguridad para lo que se guardó antes del arreglo o para una
# regresión futura.
_ANIO_MIN = 1900
_ANIO_MAX = 2100

# Baja de lote: 0% es real y verificado (CONTEXTO.md, sesión 2026-09-06
# bloque 3 -- "baja económica del 0,00 %..." declarada en texto), así que
# nunca se marca por sí sola. Negativa o >=100% no tiene lectura posible.
# Por encima de este umbral (muy por encima del máximo real medido en el
# corpus, 47,87%) es un aviso para confirmar, no un error.
_BAJA_MAXIMA_PLAUSIBLE = Decimal("0.90")


@dataclass
class Hallazgo:
    categoria: str
    gravedad: str  # "error" | "aviso"
    mensaje: str
    expedientes: list[str] = field(default_factory=list)
    total_afectados: Optional[int] = None
    detalle: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "categoria": self.categoria,
            "gravedad": self.gravedad,
            "mensaje": self.mensaje,
            "expedientes": self.expedientes,
            "total_afectados": self.total_afectados,
            "detalle": self.detalle,
        }


def _limitar_expedientes(codigos) -> tuple[list[str], int]:
    ordenados = sorted(set(codigos))
    return ordenados[:_LIMITE_EXPEDIENTES], len(ordenados)


@dataclass
class _LineaAuditable:
    id: int
    codigo_expediente: str
    lote_id: Optional[int]
    matricula: Optional[str]
    descripcion: str
    codigo_precio: Optional[str]
    cantidad: Optional[Decimal]
    precio_unitario: Optional[Decimal]
    unidad_medida: Optional[str]


def _cargar_lineas(db: Session) -> list[_LineaAuditable]:
    """Una sola lectura de las columnas que hacen falta para las
    comprobaciones que razonan fila a fila (precios, cantidades, vacíos por
    columna) -- evita una consulta separada por comprobación sobre las
    mismas ~10.000 filas. Excluye descartadas: una línea que el cliente ya
    sacó del catálogo con un motivo (`LineaCatalogoDescartar`) no debe
    seguir generando avisos de auditoría."""
    filas = db.execute(
        select(
            LineaCatalogo.id,
            Expediente.codigo_expediente,
            LineaCatalogo.lote_id,
            LineaCatalogo.matricula,
            LineaCatalogo.descripcion,
            LineaCatalogo.codigo_precio,
            LineaCatalogo.cantidad,
            LineaCatalogo.precio_unitario,
            LineaCatalogo.unidad_medida,
        )
        .join(Expediente, Expediente.id == LineaCatalogo.expediente_id)
        .where(LineaCatalogo.estado_revision != EstadoRevisionLinea.descartado)
    ).all()
    return [
        _LineaAuditable(
            id=f.id,
            codigo_expediente=f.codigo_expediente,
            lote_id=f.lote_id,
            matricula=f.matricula,
            descripcion=f.descripcion or "",
            codigo_precio=f.codigo_precio,
            cantidad=f.cantidad,
            precio_unitario=f.precio_unitario,
            unidad_medida=f.unidad_medida,
        )
        for f in filas
    ]


MENSAJE_DUPLICADAS_CODIGOS_DISTINTOS = "el propio documento repite el material con códigos de precio distintos"


def _check_duplicadas_exactas(db: Session) -> list[Hallazgo]:
    """"Líneas duplicadas exactas dentro del mismo expediente y lote":
    mismo lote, misma matrícula (o su ausencia), misma descripción, misma
    cantidad y mismo precio unitario en más de una fila -- el mismo patrón
    real que el duplicado reportado en `6.23/28510.0051` (P-0058/P-0059
    antes del arreglo de esta sesión, ver `app.catalogo._dividir_fila_multiple`).

    **El `codigo_precio` decide la gravedad** (decisión del cliente, sesión
    2026-09-18). Es la clave de la línea dentro del documento (CONTEXTO.md
    sección 2: "Código de precio [...] Esta sí es clave"), así que dos filas
    por lo demás idénticas significan cosas distintas según lo que traigan
    ahí:

    - **Mismo código de precio, o sin código**: la misma línea del documento
      contada dos veces. Es un error de extracción -- no hay forma de que el
      documento declare dos veces la misma línea bajo la misma clave.
    - **Códigos de precio distintos**: el propio documento lista el material
      dos veces, con dos claves propias (el mismo apartado repetido en dos
      secciones del cuadro). Es legítimo: aviso, para que alguien lo confirme,
      nunca error. Verificado contra los documentos reales de `0051`/`0060` y
      `4.25/28510.0132` en la sesión 2026-09-16 (noche) -- son los 11 grupos
      que esta comprobación venía marcando como error desde entonces.

    En los dos casos la auditoría solo mira y avisa: no funde ni borra nunca
    ninguna línea (docstring del módulo)."""
    filas = db.execute(
        select(
            Expediente.codigo_expediente,
            func.count(LineaCatalogo.id).label("n"),
            func.count(func.distinct(LineaCatalogo.codigo_precio)).label("codigos_distintos"),
            func.count(LineaCatalogo.id)
            .filter(LineaCatalogo.codigo_precio.is_(None))
            .label("sin_codigo"),
        )
        .join(Expediente, Expediente.id == LineaCatalogo.expediente_id)
        .where(
            LineaCatalogo.lote_id.isnot(None),
            LineaCatalogo.estado_revision != EstadoRevisionLinea.descartado,
        )
        .group_by(
            Expediente.codigo_expediente,
            LineaCatalogo.lote_id,
            LineaCatalogo.matricula,
            LineaCatalogo.descripcion,
            LineaCatalogo.cantidad,
            LineaCatalogo.precio_unitario,
        )
        .having(func.count(LineaCatalogo.id) > 1)
    ).all()
    if not filas:
        return []

    # Un grupo es legítimo solo si TODAS sus filas traen código de precio y
    # todos son distintos entre sí. Basta una sin código, o dos que repitan
    # código, para que el grupo sea un error de extracción.
    legitimos = [f for f in filas if f.sin_codigo == 0 and f.codigos_distintos == f.n]
    defectuosos = [f for f in filas if not (f.sin_codigo == 0 and f.codigos_distintos == f.n)]

    hallazgos: list[Hallazgo] = []
    if defectuosos:
        expedientes, total_expedientes = _limitar_expedientes(f.codigo_expediente for f in defectuosos)
        total_lineas = sum(f.n for f in defectuosos)
        hallazgos.append(
            Hallazgo(
                categoria="lineas_duplicadas_exactas",
                gravedad="error",
                mensaje=(
                    f"{len(defectuosos)} grupo(s) de líneas duplicadas exactas (misma matrícula, descripción, "
                    f"cantidad y precio, dentro del mismo expediente y lote) con el mismo código de precio o "
                    f"sin código -- {total_lineas} línea(s) en total."
                ),
                expedientes=expedientes,
                total_afectados=total_expedientes,
                detalle={"grupos": len(defectuosos), "lineas": total_lineas},
            )
        )
    if legitimos:
        expedientes, total_expedientes = _limitar_expedientes(f.codigo_expediente for f in legitimos)
        total_lineas = sum(f.n for f in legitimos)
        hallazgos.append(
            Hallazgo(
                categoria="lineas_duplicadas_codigo_precio_distinto",
                gravedad="aviso",
                mensaje=(
                    f"{len(legitimos)} grupo(s) de líneas con la misma matrícula, descripción, cantidad y "
                    f"precio dentro del mismo expediente y lote, pero con códigos de precio distintos: "
                    f"{MENSAJE_DUPLICADAS_CODIGOS_DISTINTOS} -- {total_lineas} línea(s) en total."
                ),
                expedientes=expedientes,
                total_afectados=total_expedientes,
                detalle={"grupos": len(legitimos), "lineas": total_lineas},
            )
        )
    return hallazgos


def _check_campos_esenciales(lineas: list[_LineaAuditable]) -> list[Hallazgo]:
    """"Líneas sin expediente, sin descripción o sin lote". Sin expediente
    no puede ocurrir hoy (`LineaCatalogo.expediente_id` es `NOT NULL` con
    clave foránea) -- se deja la comprobación igual, barata, como red de
    seguridad si esa restricción cambiara algún día sin que nadie avise
    aquí. Sin lote es el caso de huérfana (`lote_id IS NULL`), legítimo por
    diseño (CONTEXTO.md, encargo "líneas huérfanas", sección 9.3) -- se
    informa siempre con la cifra real, nunca como error por sí solo."""
    hallazgos: list[Hallazgo] = []

    sin_descripcion = [l for l in lineas if not l.descripcion.strip()]
    if sin_descripcion:
        expedientes, total = _limitar_expedientes(l.codigo_expediente for l in sin_descripcion)
        hallazgos.append(
            Hallazgo(
                categoria="sin_descripcion",
                gravedad="error",
                mensaje=(
                    f"{len(sin_descripcion)} línea(s) sin descripción -- no deberían existir: "
                    "`construir_linea_catalogo` tiene una comprobación permanente que las descarta "
                    "al extraer (CONTEXTO.md, sesión 2026-09-06 bloque 2)."
                ),
                expedientes=expedientes,
                total_afectados=total,
            )
        )

    sin_lote = [l for l in lineas if l.lote_id is None]
    if sin_lote:
        expedientes, total = _limitar_expedientes(l.codigo_expediente for l in sin_lote)
        hallazgos.append(
            Hallazgo(
                categoria="sin_lote",
                gravedad="aviso",
                mensaje=(
                    f"{len(sin_lote)} línea(s) huérfana(s) sin lote asignado -- estado esperado del "
                    "sistema (van a la cola de revisión, CONTEXTO.md sección 9.3), no un error por sí "
                    "solo. Informativo: vigilar si la cifra crece de forma anómala entre ejecuciones."
                ),
                expedientes=expedientes,
                total_afectados=total,
            )
        )

    return hallazgos


def _check_precios(lineas: list[_LineaAuditable]) -> list[Hallazgo]:
    """"Precios a cero, negativos o desproporcionados frente a la mediana de
    su expediente"."""
    hallazgos: list[Hallazgo] = []

    cero_o_negativo = [l for l in lineas if l.precio_unitario is not None and l.precio_unitario <= 0]
    if cero_o_negativo:
        expedientes, total = _limitar_expedientes(l.codigo_expediente for l in cero_o_negativo)
        hallazgos.append(
            Hallazgo(
                categoria="precio_cero_o_negativo",
                gravedad="error",
                mensaje=f"{len(cero_o_negativo)} línea(s) con precio unitario a cero o negativo.",
                expedientes=expedientes,
                total_afectados=total,
            )
        )

    por_expediente: dict[str, list[Decimal]] = {}
    for l in lineas:
        if l.precio_unitario is not None and l.precio_unitario > 0:
            por_expediente.setdefault(l.codigo_expediente, []).append(l.precio_unitario)

    atipicas: list[str] = []
    for l in lineas:
        if l.precio_unitario is None or l.precio_unitario <= 0:
            continue
        precios = por_expediente.get(l.codigo_expediente) or []
        if len(precios) < _MINIMO_LINEAS_PARA_MEDIANA:
            continue
        mediana = statistics.median(precios)
        if mediana <= 0:
            continue
        ratio = l.precio_unitario / mediana
        if ratio > _RATIO_PRECIO_ATIPICO or ratio < Decimal(1) / _RATIO_PRECIO_ATIPICO:
            atipicas.append(l.codigo_expediente)
    if atipicas:
        expedientes, total = _limitar_expedientes(atipicas)
        hallazgos.append(
            Hallazgo(
                categoria="precio_desproporcionado",
                gravedad="aviso",
                mensaje=(
                    f"{len(atipicas)} línea(s) con precio unitario a más de {_RATIO_PRECIO_ATIPICO}x o "
                    f"menos de 1/{_RATIO_PRECIO_ATIPICO}x la mediana de su propio expediente -- puede "
                    "ser legítimo (partida alzada, precio por unidad de medida distinta dentro del "
                    "mismo lote, CONTEXTO.md sesión 2026-09-06 bloque 3), confirmar caso a caso."
                ),
                expedientes=expedientes,
                total_afectados=total,
            )
        )

    return hallazgos


def _check_cantidades(lineas: list[_LineaAuditable]) -> list[Hallazgo]:
    """"Cantidades implausibles": red de seguridad global para el mismo
    defecto que `_construir_campos` ya descarta al extraer (CONTEXTO.md
    sección 16, sesión 2026-09-07: cantidad con forma de año) -- por si
    queda alguna fila guardada antes del arreglo, o una regresión futura."""
    hallazgos: list[Hallazgo] = []

    negativas = [l for l in lineas if l.cantidad is not None and l.cantidad < 0]
    if negativas:
        expedientes, total = _limitar_expedientes(l.codigo_expediente for l in negativas)
        hallazgos.append(
            Hallazgo(
                categoria="cantidad_negativa",
                gravedad="error",
                mensaje=f"{len(negativas)} línea(s) con cantidad negativa.",
                expedientes=expedientes,
                total_afectados=total,
            )
        )

    forma_anio = [
        l
        for l in lineas
        if l.cantidad is not None
        and l.cantidad == l.cantidad.to_integral_value()
        and _ANIO_MIN <= l.cantidad <= _ANIO_MAX
    ]
    if forma_anio:
        expedientes, total = _limitar_expedientes(l.codigo_expediente for l in forma_anio)
        hallazgos.append(
            Hallazgo(
                categoria="cantidad_forma_anio",
                gravedad="aviso",
                mensaje=(
                    f"{len(forma_anio)} línea(s) con cantidad entera entre {_ANIO_MIN} y {_ANIO_MAX} "
                    "(forma de año) -- señal del defecto de mapeo de columna descrito en CONTEXTO.md "
                    "sección 16 (sesión 2026-09-07), aunque puede ser una 'CANTIDAD DE REFERENCIA' real "
                    "y ambigua del propio documento."
                ),
                expedientes=expedientes,
                total_afectados=total,
            )
        )

    return hallazgos


def _check_bajas(db: Session) -> list[Hallazgo]:
    """"Bajas fuera de un rango razonable"."""
    hallazgos: list[Hallazgo] = []
    filas = db.execute(
        select(Expediente.codigo_expediente, Lote.baja_lote)
        .join(Expediente, Expediente.id == Lote.expediente_id)
        .where(Lote.baja_lote.isnot(None))
    ).all()

    implausibles = [f for f in filas if f.baja_lote < 0 or f.baja_lote >= 1]
    if implausibles:
        expedientes, total = _limitar_expedientes(f.codigo_expediente for f in implausibles)
        hallazgos.append(
            Hallazgo(
                categoria="baja_implausible",
                gravedad="error",
                mensaje=(
                    f"{len(implausibles)} lote(s) con baja negativa o >=100% -- no tiene lectura "
                    "posible como porcentaje de rebaja."
                ),
                expedientes=expedientes,
                total_afectados=total,
            )
        )

    altas = [f for f in filas if 0 <= f.baja_lote < 1 and f.baja_lote > _BAJA_MAXIMA_PLAUSIBLE]
    if altas:
        expedientes, total = _limitar_expedientes(f.codigo_expediente for f in altas)
        hallazgos.append(
            Hallazgo(
                categoria="baja_muy_alta",
                gravedad="aviso",
                mensaje=(
                    f"{len(altas)} lote(s) con baja por encima de {_BAJA_MAXIMA_PLAUSIBLE * 100}% -- muy "
                    "por encima del máximo real visto en el corpus (47,87%, CONTEXTO.md sección 16), "
                    "confirmar contra el documento de origen."
                ),
                expedientes=expedientes,
                total_afectados=total,
            )
        )

    return hallazgos


def _check_importe_licitacion_sospechoso(db: Session) -> list[Hallazgo]:
    """Encargo explícito del cliente, sesión de medición del alcance
    "Nº Lote: NNN" (2026-09-08, docs/sesion-2026-09-08-auditoria-automatica.md):
    "si el importe de licitación de un lote coincide con el de otro lote del
    mismo expediente, o con el presupuesto global, es sospechoso". Hallazgo
    real que motiva esto: un "Anuncio de adjudicación" que agrupa varios
    lotes en un solo PDF (marcador "Nº Lote: NNN", distinto del "LOTE N"
    narrativo que ya cubre `app.extraccion.lotes`) puede compartirse entre
    varios expedientes hermanos -- la extracción de etiqueta fija de un solo
    lote (`app.extraccion.campos_pcsp`) coge la primera coincidencia de
    "Presupuesto base de licitación" del documento entero, que es la
    cabecera GLOBAL de toda la licitación, no la del lote de ESE expediente.
    Medido contra el corpus real: 22 expedientes confirmados, 374 líneas de
    catálogo con `precio_adjudicado` derivado de la baja resultante.

    Dos señales, ambas de solo lectura sobre `lotes`/`documento_expedientes`,
    sin volver a abrir ningún PDF (por eso puede correr en cada auditoría sin
    coste de red ni de E/S de disco):

    1. **Mismo documento de origen, mismo `importe_licitacion`, expedientes
       DISTINTOS** -- la señal real que sí se verificó contra el corpus.
       Dos lotes de licitaciones distintas raramente comparten presupuesto
       exacto por casualidad; si además comparten el documento del que salió
       ese importe, es la firma exacta de este defecto.
    2. **Dos lotes del MISMO expediente con idéntico `importe_licitacion`**
       -- la forma literal del encargo ("otro lote del mismo expediente"):
       no verificada contra ningún caso real todavía (el corpus actual no
       tiene expedientes con 2+ filas de `lotes`), pero barata de comprobar
       y cubre el caso si aparece.

    Aviso, no error: existe el caso legítimo de dos lotes con presupuestos
    iguales por coincidencia real (verificado en otro contexto,
    `docs/descubrimiento-inverso-matriz-pedidos.md`: un precio de referencia
    puede repetirse legítimamente) -- aquí igual, nunca se descarta ni se
    corrige solo, se señala para que un humano lo confirme contra el
    documento."""
    hallazgos: list[Hallazgo] = []

    filas = db.execute(
        select(
            DocumentoExpediente.documento_id, Expediente.id, Expediente.codigo_expediente, Lote.importe_licitacion,
            Lote.codigo_expediente_lote,
        )
        .join(Expediente, Expediente.id == DocumentoExpediente.expediente_id)
        .join(Lote, Lote.expediente_id == Expediente.id)
        .where(Lote.importe_licitacion.isnot(None))
    ).all()

    # Sesión 2026-09-15: un lote con su propio código de expediente es el
    # MISMO lote en todos los expedientes que lo guardan (el principal y el
    # propio lote, `6.22/28510.0033`/`0058`) -- que compartan su importe es lo
    # correcto, no el presupuesto global repartido. Con el importe que ahora
    # completa el Contrato de cada lote, esa coincidencia legítima pasó de 31
    # a 275 grupos y tapaba la señal. Es sospechoso cuando el mismo importe
    # del mismo documento está en lotes que no son el mismo.
    grupos: dict[tuple, dict[int, str]] = {}
    lotes_del_grupo: dict[tuple, set] = {}
    for documento_id, expediente_id, codigo, importe, codigo_lote in filas:
        grupos.setdefault((documento_id, importe), {})[expediente_id] = codigo
        # Un lote sin código no se puede identificar con ningún otro.
        lotes_del_grupo.setdefault((documento_id, importe), set()).add(codigo_lote or ("sin código", expediente_id))

    codigos_cruzados: set[str] = set()
    grupos_sospechosos = 0
    for clave, miembros in grupos.items():
        if len(miembros) > 1 and len(lotes_del_grupo[clave]) > 1:
            grupos_sospechosos += 1
            codigos_cruzados.update(miembros.values())

    if codigos_cruzados:
        expedientes, total = _limitar_expedientes(codigos_cruzados)
        hallazgos.append(
            Hallazgo(
                categoria="importe_licitacion_compartido_entre_expedientes",
                gravedad="aviso",
                mensaje=(
                    f"{grupos_sospechosos} grupo(s) de expedientes distintos que comparten el mismo "
                    "documento de origen Y el mismo importe de licitación -- señal de que ese importe es "
                    "el presupuesto global de la licitación, no el del lote de cada expediente (defecto "
                    "verificado en la sesión 2026-09-08, ver docs/sesion-2026-09-08-auditoria-automatica.md)."
                ),
                expedientes=expedientes,
                total_afectados=total,
                detalle={"grupos": grupos_sospechosos},
            )
        )

    # Independiente de la consulta de arriba: un expediente con 2+ lotes
    # propios de importe idéntico no depende de tener ningún documento
    # vinculado vía `documento_expedientes` -- se comprueba directo sobre
    # `lotes`/`expedientes`.
    filas_lotes = db.execute(
        select(Lote.expediente_id, Expediente.codigo_expediente, Lote.importe_licitacion)
        .join(Expediente, Expediente.id == Lote.expediente_id)
        .where(Lote.importe_licitacion.isnot(None))
    ).all()
    por_expediente: dict[int, list] = {}
    codigo_por_expediente: dict[int, str] = {}
    for expediente_id, codigo, importe in filas_lotes:
        por_expediente.setdefault(expediente_id, []).append(importe)
        codigo_por_expediente[expediente_id] = codigo

    duplicado_interno = [
        codigo_por_expediente[expediente_id]
        for expediente_id, importes in por_expediente.items()
        if len(importes) > 1 and len(set(importes)) < len(importes)
    ]
    if duplicado_interno:
        expedientes, total = _limitar_expedientes(duplicado_interno)
        hallazgos.append(
            Hallazgo(
                categoria="importe_licitacion_repetido_en_el_mismo_expediente",
                gravedad="aviso",
                mensaje=(
                    f"{total} expediente(s) con dos o más lotes propios que comparten idéntico importe "
                    "de licitación -- confirmar que no es el presupuesto global repetido en cada lote."
                ),
                expedientes=expedientes,
                total_afectados=total,
            )
        )

    return hallazgos


def _check_firma_cabecera(db: Session) -> list[Hallazgo]:
    """"Firmas de cabecera compartidas por tablas de estructura distinta".
    Dos comprobaciones sobre `cache_mapeo_cabecera` (CONTEXTO.md sección 6):

    1. Regresión del arreglo de la sesión de verificación del Excel de 6.599
       líneas (2026-09-08): una cabecera cacheada sin ninguna celda con
       texto real (`calcular_firma_cabecera([])` la trataba igual que
       cualquier otra, así que el mapeo de la PRIMERA tabla así del corpus
       se reaplicaba a ciegas a todas las siguientes, de estructura
       distinta) nunca debería volver a guardarse -- si aparece, es que la
       comprobación de `app.extraccion.mapeo_cabecera.mapear_cabecera` que
       lo evita se rompió.
    2. La firma guardada tiene que ser reproducible: si recalcular
       `calcular_firma_cabecera` sobre la propia cabecera guardada da un
       hash distinto al de la columna `firma`, la caché está corrupta o el
       algoritmo cambió sin recalcularla -- cualquiera de las dos deja
       mapeos de cabeceras nunca vistas sin poder confirmarse contra su
       propio origen."""
    hallazgos: list[Hallazgo] = []
    filas = db.execute(select(MapeoCabeceraCache.id, MapeoCabeceraCache.firma, MapeoCabeceraCache.cabecera)).all()

    vacias = [f.id for f in filas if not any((c or "").strip() for c in (f.cabecera or []))]
    if vacias:
        hallazgos.append(
            Hallazgo(
                categoria="firma_cabecera_vacia",
                gravedad="error",
                mensaje=(
                    f"{len(vacias)} entrada(s) en la caché de mapeo de cabecera sin ninguna celda con "
                    "texto real -- regresión del defecto corregido en la sesión 2026-09-08 (firma "
                    "vacía compartida entre tablas de estructura distinta)."
                ),
                detalle={"cache_ids": vacias[:_LIMITE_EXPEDIENTES]},
                total_afectados=len(vacias),
            )
        )

    corruptas = [f.id for f in filas if calcular_firma_cabecera(f.cabecera or []) != f.firma]
    if corruptas:
        hallazgos.append(
            Hallazgo(
                categoria="firma_cabecera_no_reproducible",
                gravedad="error",
                mensaje=(
                    f"{len(corruptas)} entrada(s) en la caché de mapeo de cabecera cuya firma guardada "
                    "no coincide con recalcularla sobre su propia cabecera -- caché corrupta, o el "
                    "algoritmo de firma cambió sin recalcular las entradas existentes."
                ),
                detalle={"cache_ids": corruptas[:_LIMITE_EXPEDIENTES]},
                total_afectados=len(corruptas),
            )
        )

    return hallazgos


def _snapshot_expedientes(db: Session) -> dict[str, dict]:
    filas = db.execute(
        select(
            Expediente.codigo_expediente,
            Expediente.huella_documentos,
            func.count(LineaCatalogo.id),
        )
        .outerjoin(
            LineaCatalogo,
            (LineaCatalogo.expediente_id == Expediente.id)
            & (LineaCatalogo.estado_revision != EstadoRevisionLinea.descartado),
        )
        .group_by(Expediente.codigo_expediente, Expediente.huella_documentos)
    ).all()
    return {f[0]: {"lineas": f[2], "huella_documentos": f[1]} for f in filas}


def _movimiento_de_extracciones(
    db: Session, codigos: list[str], desde, hasta
) -> dict[str, tuple[int, int]]:
    """`{codigo: (lineas_podadas, lineas_creadas)}` sumadas sobre todos los
    trabajos `extraer_expediente` completados de cada expediente entre dos
    ejecuciones de esta auditoría (`desde` exclusive, `hasta` inclusive --
    los propios `created_at` de la auditoría anterior y de la actual). Varias
    extracciones del mismo expediente pueden haber corrido entre dos
    auditorías (reintentos, un ciclo con varias pasadas): se suman todas, no
    solo la última.

    Las dos cifras salen del resumen de `app.extraccion.orquestador`:
    `lineas_podadas` son las que borró `podar_lineas_obsoletas_de_documento`
    (Bloque 4 de la sesión del maestro de materiales, 2026-09-10) y
    `lineas_creadas` las que la misma pasada dio de alta. Hasta la sesión
    2026-09-18 solo se leía la primera, y eso dejaba sin atribuir el caso de
    `6.23/28510.0105` (ver `_check_crecimiento_sin_cambios`)."""
    if not codigos:
        return {}
    filas = db.execute(
        select(Expediente.codigo_expediente, TrabajoCola.resultado)
        .join(TrabajoCola, TrabajoCola.expediente_id == Expediente.id)
        .where(
            Expediente.codigo_expediente.in_(codigos),
            TrabajoCola.tipo == "extraer_expediente",
            TrabajoCola.estado == EstadoTrabajo.completado,
            TrabajoCola.created_at > desde,
            TrabajoCola.created_at <= hasta,
        )
    ).all()
    movimiento: dict[str, tuple[int, int]] = {}
    for codigo, resultado in filas:
        podadas = (resultado or {}).get("lineas_podadas") or 0
        creadas = (resultado or {}).get("lineas_creadas") or 0
        antes = movimiento.get(codigo, (0, 0))
        movimiento[codigo] = (antes[0] + podadas, antes[1] + creadas)
    return movimiento


def _check_crecimiento_sin_cambios(
    db: Session, snapshot_anterior: Optional[dict], creado_en_anterior, creado_en_actual
) -> list[Hallazgo]:
    """"Expedientes cuyo número de líneas cambia sin que hayan cambiado sus
    documentos". El propio `app.mantenimiento.frescura.detectar_crecimiento_
    sin_cambios` ya vigila esto EXPEDIENTE A EXPEDIENTE en el momento de
    reprocesarlo (mismo origen que motivó esta comprobación: ~4.500 líneas
    de sobra en siete expedientes, sesión de auditoría 2026-09-05) -- esta
    auditoría hace la misma comparación pero A NIVEL DE CORPUS, entre la
    foto de la ejecución anterior de la propia auditoría
    (`snapshot_expedientes`, guardado en el resultado de cada ejecución) y
    la de ahora: mismo `huella_documentos`, número de líneas distinto. Sin
    ejecución anterior que comparar (primera vez que corre esta auditoría),
    no hay nada que decir todavía.

    Bloque 4, sesión 2026-09-11 (hallazgo real del reproceso completo de la
    sesión anterior: 15 expedientes marcados "error" que en realidad eran
    `podar_lineas_obsoletas_de_documento`, Bloque 4 de la sesión del maestro
    de materiales, limpiando 832 líneas de residuo genuino por primera vez).
    Una BAJADA de recuento no es automáticamente sospechosa: si la suma de
    `lineas_podadas` de las extracciones de ese expediente entre las dos
    auditorías explica exactamente la diferencia, es poda funcionando como
    se diseñó -- aviso informativo, no error. Una SUBIDA nunca la explica la
    poda (que solo borra) -- sigue siendo error siempre. Una bajada que la
    poda no explica del todo (poda insuficiente, o ninguna poda registrada)
    también sigue siendo error: solo se degrada lo que de verdad cuadra.

    Bloque 4, sesión 2026-09-18: **la poda no es el único camino por el que
    una reextracción baja el recuento sin que cambien los documentos.** Caso
    real que este bloque arregla, `6.23/28510.0105`: la sesión anterior
    enseñó a la cascada a tratar las filas de resumen de presupuesto ("Suma",
    "IVA (21%)", "Presupuesto de Ejecución Material") como pie de tabla en
    vez de como línea de catálogo (`app.catalogo._es_concepto_de_presupuesto`),
    y ese expediente perdió su única fila de ese tipo. La quitó el FILTRO DE
    EXTRACCIÓN, no el podador, así que `lineas_podadas` no la cuenta -- y
    salía como `error` un cambio perfectamente explicado. La regla anterior
    comparaba `lineas_podadas` contra la diferencia neta, que solo cuadra
    cuando la pasada no creó ninguna línea; aquí la pasada podó 32 y creó 31
    (quitar una fila corre el `orden_aparicion` de todas las siguientes, y
    con él su clave), neto -1.

    La atribución correcta es el balance completo de las extracciones del
    intervalo: `podadas - creadas`. Cuando cuadra exactamente con la bajada,
    el recuento cambió por lo que hicieron esas extracciones y no por otra
    cosa -- aviso explicado, no error. Sigue siendo error una bajada que ese
    balance no explica (nadie reextrajo, o la cuenta no sale) y **cualquier
    subida**, que es el síntoma que motivó la comprobación."""
    if not snapshot_anterior:
        return []
    actual = _snapshot_expedientes(db)
    afectados = []
    for codigo, ahora in actual.items():
        antes = snapshot_anterior.get(codigo)
        if antes is None:
            continue
        huella_antes = antes.get("huella_documentos")
        huella_ahora = ahora.get("huella_documentos")
        if huella_antes is None or huella_ahora is None or huella_antes != huella_ahora:
            continue
        diferencia = ahora.get("lineas") - antes.get("lineas")
        if diferencia != 0:
            afectados.append((codigo, diferencia))
    if not afectados:
        return []

    decrecientes = [codigo for codigo, diferencia in afectados if diferencia < 0]
    movimiento = (
        _movimiento_de_extracciones(db, decrecientes, creado_en_anterior, creado_en_actual)
        if creado_en_anterior is not None
        else {}
    )

    sin_explicar = []
    explicados_por_poda = []
    explicados_por_reextraccion = []
    for codigo, diferencia in afectados:
        podadas, creadas = movimiento.get(codigo, (0, 0))
        if diferencia >= 0:
            # Una subida nunca la explica ni la poda ni el filtro: los dos
            # solo quitan líneas.
            sin_explicar.append(codigo)
        elif creadas == 0 and podadas == -diferencia:
            explicados_por_poda.append(codigo)
        elif podadas - creadas == -diferencia and (podadas or creadas):
            explicados_por_reextraccion.append(codigo)
        else:
            sin_explicar.append(codigo)

    hallazgos: list[Hallazgo] = []
    if explicados_por_poda:
        expedientes, total = _limitar_expedientes(explicados_por_poda)
        hallazgos.append(
            Hallazgo(
                categoria="lineas_bajan_explicado_por_poda",
                gravedad="aviso",
                mensaje=(
                    f"{total} expediente(s) cuyo número de líneas bajó respecto a la ejecución anterior "
                    "de esta auditoría sin cambiar su huella de documentos, explicado exactamente por "
                    "`lineas_podadas` de sus extracciones en ese intervalo -- poda de huérfanas obsoletas "
                    "funcionando como se diseñó (CONTEXTO.md, sesión del maestro de materiales, bloque 4), "
                    "no una duplicación."
                ),
                expedientes=expedientes,
                total_afectados=total,
            )
        )
    if explicados_por_reextraccion:
        expedientes, total = _limitar_expedientes(explicados_por_reextraccion)
        hallazgos.append(
            Hallazgo(
                categoria="lineas_bajan_explicado_por_reextraccion",
                gravedad="aviso",
                mensaje=(
                    f"{total} expediente(s) cuyo número de líneas bajó respecto a la ejecución anterior "
                    "de esta auditoría sin cambiar su huella de documentos, explicado exactamente por el "
                    "balance de sus reextracciones en ese intervalo (`lineas_podadas` menos "
                    "`lineas_creadas`) -- los mismos documentos dan menos líneas porque cambió una regla "
                    "de la cascada de extracción, no porque se haya perdido nada. Caso típico: las filas "
                    "de resumen de presupuesto (\"Suma\", \"IVA (21%)\") pasaron a leerse como pie de "
                    "tabla en vez de como material (CONTEXTO.md, sesión 2026-09-17)."
                ),
                expedientes=expedientes,
                total_afectados=total,
            )
        )
    if sin_explicar:
        expedientes, total = _limitar_expedientes(sin_explicar)
        hallazgos.append(
            Hallazgo(
                categoria="lineas_cambian_sin_cambiar_documentos",
                gravedad="error",
                mensaje=(
                    f"{total} expediente(s) cuyo número de líneas de catálogo cambió respecto a la "
                    "ejecución anterior de esta auditoría sin que cambiara su huella de documentos, y sin "
                    "que sus reextracciones de ese intervalo expliquen la diferencia (una subida siempre "
                    "es sospechosa; una bajada solo se descarta si `lineas_podadas`, o el balance "
                    "`lineas_podadas` menos `lineas_creadas`, la explica exactamente) "
                    "-- mismo síntoma que motivó la comprobación de integridad de "
                    "`app.mantenimiento.frescura.detectar_crecimiento_sin_cambios` (auditoría 2026-09-05)."
                ),
                expedientes=expedientes,
                total_afectados=total,
            )
        )
    return hallazgos


def _check_vacios_por_columna(
    lineas: list[_LineaAuditable], resultado_anterior: Optional[dict]
) -> tuple[dict[str, float], list[Hallazgo]]:
    """"Campos vacíos por encima de un umbral por columna, comparado con la
    ejecución anterior"."""
    total = len(lineas)
    actuales: dict[str, float] = {}
    if total:
        for columna in _COLUMNAS_SEGUIDAS:
            vacias = sum(1 for l in lineas if getattr(l, columna) is None)
            actuales[columna] = round(100.0 * vacias / total, 2)
    else:
        actuales = {columna: 0.0 for columna in _COLUMNAS_SEGUIDAS}

    hallazgos: list[Hallazgo] = []
    anteriores = (resultado_anterior or {}).get("vacios_por_columna") or {}
    for columna, pct_actual in actuales.items():
        pct_antes = anteriores.get(columna)
        if pct_antes is None:
            continue
        crecimiento = pct_actual - pct_antes
        if crecimiento > _UMBRAL_CRECIMIENTO_VACIO_PUNTOS:
            hallazgos.append(
                Hallazgo(
                    categoria="columna_vacia_crecio",
                    gravedad="aviso",
                    mensaje=(
                        f"columna '{columna}': {pct_actual}% de líneas vacías, frente a {pct_antes}% en "
                        f"la ejecución anterior (+{round(crecimiento, 2)} puntos)."
                    ),
                    detalle={"columna": columna, "pct_actual": pct_actual, "pct_anterior": pct_antes},
                )
            )
    return actuales, hallazgos


@dataclass
class ResumenAuditoria:
    total_lineas: int
    total_expedientes: int
    hallazgos: list[Hallazgo]
    comparado_con_ejecucion_anterior: Optional[int]

    def to_dict(self) -> dict:
        return {
            "total_lineas": self.total_lineas,
            "total_expedientes": self.total_expedientes,
            "total_hallazgos": len(self.hallazgos),
            "total_errores": sum(1 for h in self.hallazgos if h.gravedad == "error"),
            "total_avisos": sum(1 for h in self.hallazgos if h.gravedad == "aviso"),
            "hallazgos": [h.to_dict() for h in self.hallazgos],
            "comparado_con_ejecucion_anterior": self.comparado_con_ejecucion_anterior,
        }


def _ultima_ejecucion_completada(db: Session, antes_de) -> Optional[TrabajoCola]:
    return db.execute(
        select(TrabajoCola)
        .where(
            TrabajoCola.tipo == TIPO_TRABAJO,
            TrabajoCola.estado == EstadoTrabajo.completado,
            TrabajoCola.created_at < antes_de,
        )
        .order_by(TrabajoCola.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def ejecutar_auditoria(db: Session, trabajo: TrabajoCola) -> dict:
    """Manejador de la cola (`app.queue.ejecutar_trabajo`): corre todas las
    comprobaciones de solo lectura y devuelve el informe completo -- nunca
    escribe en `expedientes`/`lotes`/`lineas_catalogo`. Se encola
    automáticamente al final de cada ciclo de mantenimiento
    (`app.mantenimiento.ciclo`) y también se puede lanzar a mano
    (`POST /mantenimiento/auditoria/ejecutar`)."""
    anterior = _ultima_ejecucion_completada(db, antes_de=trabajo.created_at)
    resultado_anterior = anterior.resultado if anterior is not None else None
    snapshot_anterior = (resultado_anterior or {}).get("snapshot_expedientes")

    lineas = _cargar_lineas(db)

    hallazgos: list[Hallazgo] = []
    hallazgos += _check_duplicadas_exactas(db)
    hallazgos += _check_campos_esenciales(lineas)
    hallazgos += _check_precios(lineas)
    hallazgos += _check_cantidades(lineas)
    hallazgos += _check_bajas(db)
    hallazgos += _check_importe_licitacion_sospechoso(db)
    hallazgos += _check_firma_cabecera(db)
    hallazgos += _check_crecimiento_sin_cambios(
        db,
        snapshot_anterior,
        creado_en_anterior=anterior.created_at if anterior is not None else None,
        creado_en_actual=trabajo.created_at,
    )
    vacios_por_columna, hallazgos_vacios = _check_vacios_por_columna(lineas, resultado_anterior)
    hallazgos += hallazgos_vacios

    total_expedientes = db.execute(select(func.count(Expediente.id))).scalar_one()
    resumen = ResumenAuditoria(
        total_lineas=len(lineas),
        total_expedientes=total_expedientes,
        hallazgos=hallazgos,
        comparado_con_ejecucion_anterior=anterior.id if anterior is not None else None,
    )
    resultado = resumen.to_dict()
    resultado["vacios_por_columna"] = vacios_por_columna
    resultado["snapshot_expedientes"] = _snapshot_expedientes(db)
    return resultado
