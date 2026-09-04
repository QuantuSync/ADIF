import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.extraccion.codigo_material import derivar_codigo_material
from app.extraccion.normalizacion import (
    limpiar_codigo_celda,
    limpiar_texto_celda,
    normalizar_guiones,
    parsear_importe_es,
    parsear_numero_es,
)
from app.extraccion.tabla import TablaExtraida
from app.extraccion.texto import normalizar
from app.models import LineaCatalogo

# Sesión de rodaje sobre el corpus completo (2026-09-03): en varias tablas
# reales, una fila que no es una línea de material (un pie de tabla como
# "PRESUPUESTO DE LICITACIÓN", "IVA", "TOTAL CON IVA", o una partida alzada
# sin celda de matrícula propia) desplaza sus columnas y el texto de esa fila
# cae en la columna de matrícula — que es `varchar(9)` y revienta el INSERT
# con cualquier texto más largo. CLAUDE.md sección 2: la matrícula "no es"
# nunca texto, es un código de 9 dígitos; cualquier valor con una letra ya es
# la señal de que esta fila no es lo que el mapeo de cabecera cree que es.
_MATRICULA_VALIDA_RE = re.compile(r"^\d+$")

# Coincidencia exacta (tras normalizar y quitar espacios): estas filas no son
# una línea de material, son el resumen de la tabla — se descartan enteras,
# no se guardan con matrícula vacía ni con ningún otro campo relleno.
_ETIQUETAS_PIE_TABLA = frozenset({
    "presupuestodelicitacion",
    "presupuestodeadjudicacion",
    "baseimponible",
    "totalconiva",
    "totaliva",
    "subtotal",
    "importetotal",
    "iva",
    "total",
})


def _es_pie_de_tabla(texto_normalizado_sin_espacios: str) -> bool:
    return texto_normalizado_sin_espacios in _ETIQUETAS_PIE_TABLA


def _es_partida_alzada(texto_normalizado_sin_espacios: str) -> bool:
    # "Partida alzada a justificar para imprevistos" y variantes: CLAUDE.md
    # sección 2 la define como línea legítima ("sin matrícula ni código de
    # material"), así que el texto no se descarta — se recupera como
    # descripción, nunca como matrícula.
    return texto_normalizado_sin_espacios.startswith("partidaalzada")


# Sesión de los 3 expedientes que seguían en revisión tras el criterio de
# lote laxo del cliente (CLAUDE.md sección 26): un guion suelto en una celda
# de matrícula/cantidad/precio unitario es la misma convención administrativa
# que un hueco en blanco ("no aplica a esta fila"), verificado contra las 39
# filas reales de `6.24/28510.0117` — la propia tabla usa el guion en la
# celda de matrícula Y en la de código de elemento de la misma fila,
# sistemáticamente, nunca solo en una fila suelta. No es un dato ilegible que
# haga falta revisar, es la forma en que el documento dice "vacío" — igual
# que CLAUDE.md sección 2 ya trata la ausencia de matrícula en el ~34% de las
# líneas como algo normal, no un error. Distinto de un valor con identificadores
# de glifo sin decodificar (CID) o de dos valores duplicados que no coinciden:
# esos sí son ilegibles de verdad y siguen yendo a revisión (ver
# `parsear_numero_es`).
def _es_celda_vacia(valor: Optional[str]) -> bool:
    if valor is None:
        return False
    return normalizar_guiones(valor).strip() == "-"


def _acumular_motivo(motivo: Optional[str], nuevo: Optional[str]) -> Optional[str]:
    if not nuevo:
        return motivo
    return f"{motivo}; {nuevo}" if motivo else nuevo


def calcular_clave_linea(codigo_precio, matricula, descripcion, orden_aparicion):
    """Clave no nula para una línea de catálogo dentro de un lote.
    Prioridad: codigo_precio > matricula > hash(descripcion + orden de aparición).
    Los nulos de Postgres no colisionan en un UNIQUE, así que la clave nunca
    puede ser nula si se quiere que el constraint detecte duplicados."""
    if codigo_precio:
        return codigo_precio.strip()
    if matricula:
        return matricula.strip()
    base = f"{descripcion.strip()}|{orden_aparicion}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def construir_linea_catalogo(
    fila: list[Optional[str]],
    mapeo: dict[str, Optional[int]],
    pagina: int,
    documento_origen_id: Optional[int],
    expediente_id: int,
    baja_lote: Optional[Decimal],
    orden_aparicion: int,
) -> Optional[dict]:
    """Etapa 6 (normalización + derivación, CLAUDE.md secciones 4 y 8): una
    fila cruda de tabla + el mapeo de columnas de la etapa 5 -> los campos de
    una `LineaCatalogo`. `precio_adjudicado` se deriva aquí, no se busca en
    ningún documento (CLAUDE.md sección 4: "no existe una tabla de precios
    adjudicados").

    `expediente_id` viaja en la línea desde este punto (encargo de esta
    sesión, punto 3): una línea cuya tabla de origen no se pudo asociar a un
    único lote sin ambigüedad se guarda igualmente, con `lote_id=None` —
    huérfana pero trazable hasta su expediente.

    Devuelve `None` cuando la fila es un pie de tabla (CLAUDE.md sección 2,
    sesión de rodaje 2026-09-03): no es una línea de material, es un resumen
    ("PRESUPUESTO DE LICITACIÓN", "IVA", "TOTAL CON IVA") que el mapeo de
    cabecera no distingue de una fila de datos. Nunca lanza por un valor de
    `cantidad`/`precio_unitario` ilegible (identificadores de glifo sin
    decodificar, celdas con el valor duplicado que no coinciden entre sí):
    ese campo queda en `None` y la línea lleva `motivo_revision` explicando
    por qué, en vez de tirar la tabla entera por una fila."""

    def _valor(campo: str) -> Optional[str]:
        indice = mapeo.get(campo)
        if indice is None or indice >= len(fila):
            return None
        return fila[indice]

    matricula_bruta = _valor("matricula")
    codigo_precio = limpiar_codigo_celda(_valor("codigo_precio"))
    matricula = limpiar_codigo_celda(matricula_bruta)
    descripcion = limpiar_texto_celda(_valor("descripcion")) or ""
    unidad_medida = limpiar_texto_celda(_valor("unidad_medida"))

    motivo_revision: Optional[str] = None

    if matricula is not None and not _MATRICULA_VALIDA_RE.match(matricula):
        clave = normalizar(matricula).replace(" ", "")
        if _es_pie_de_tabla(clave):
            return None
        if _es_celda_vacia(matricula):
            matricula = None
        elif _es_partida_alzada(clave):
            # La celda de matrícula de esta fila no existe de verdad (una
            # partida alzada no tiene, CLAUDE.md sección 2): el texto que
            # debía caer en descripción aterrizó aquí porque a esta fila le
            # falta una columna respecto a las demás de la tabla. Se
            # recupera de la celda cruda (`matricula_bruta`), no de
            # `matricula`, que ya perdió los espacios entre palabras al
            # limpiarse como si fuera un código.
            if not descripcion:
                descripcion = limpiar_texto_celda(matricula_bruta) or matricula
            matricula = None
        else:
            motivo_revision = _acumular_motivo(
                motivo_revision, f"valor de matrícula no reconocible, descartado: {matricula!r}"
            )
            matricula = None

    cantidad_bruta = _valor("cantidad")
    cantidad = None
    if cantidad_bruta and not _es_celda_vacia(cantidad_bruta):
        try:
            cantidad = parsear_numero_es(cantidad_bruta)
        except ValueError as exc:
            motivo_revision = _acumular_motivo(motivo_revision, f"cantidad no interpretable: {exc}")

    precio_bruto = _valor("precio_unitario")
    precio_unitario = None
    if precio_bruto and not _es_celda_vacia(precio_bruto):
        try:
            precio_unitario = parsear_importe_es(precio_bruto)
        except ValueError as exc:
            motivo_revision = _acumular_motivo(motivo_revision, f"precio unitario no interpretable: {exc}")

    precio_adjudicado = None
    if precio_unitario is not None and baja_lote is not None:
        precio_adjudicado = precio_unitario * (Decimal("1") - baja_lote)

    return {
        "clave_linea": calcular_clave_linea(codigo_precio, matricula, descripcion, orden_aparicion),
        "expediente_id": expediente_id,
        "orden_aparicion": orden_aparicion,
        "codigo_precio": codigo_precio,
        "matricula": matricula,
        "descripcion": descripcion,
        "codigo_material": derivar_codigo_material(descripcion),
        "unidad_medida": unidad_medida,
        "cantidad": cantidad,
        "precio_unitario": precio_unitario,
        "baja_lote": baja_lote,
        "precio_adjudicado": precio_adjudicado,
        "documento_origen_id": documento_origen_id,
        "pagina": pagina,
        "fragmento": " | ".join((celda or "").strip() for celda in fila),
        "motivo_revision": motivo_revision,
    }


def construir_lineas_desde_tabla(
    tabla: TablaExtraida,
    mapeo: dict[str, Optional[int]],
    documento_origen_id: Optional[int],
    expediente_id: int,
    baja_lote: Optional[Decimal],
    orden_inicial: int,
) -> list[dict]:
    # Una fila de pie de tabla (CLAUDE.md sección 2, sesión de rodaje
    # 2026-09-03) devuelve None de `construir_linea_catalogo`: se descarta
    # aquí, nunca llega a `guardar_lineas_catalogo`.
    lineas = (
        construir_linea_catalogo(
            fila, mapeo, tabla.pagina, documento_origen_id, expediente_id, baja_lote, orden_inicial + indice
        )
        for indice, fila in enumerate(tabla.filas)
    )
    return [linea for linea in lineas if linea is not None]


@dataclass(frozen=True)
class ResultadoGuardadoCatalogo:
    creadas: int
    actualizadas: int


def _combinar_por_clave(lineas: list[dict]) -> list[dict]:
    """El mismo cuadro de precios puede reaparecer varias veces dentro de un
    único documento (CLAUDE.md sección 3 y docstring de `guardar_lineas_catalogo`),
    así que `lineas` puede traer la misma `clave_linea` repetida antes de tocar
    la base de datos. Doblarlas aquí, en Python, con la misma regla de fusión
    que ya aplica `guardar_lineas_catalogo` fila a fila (un valor `None` nunca
    pisa uno ya conocido) — no depender de que la sesión autoflushee entre
    iteraciones, que `SessionLocal` (app/db.py) desactiva a propósito."""
    combinadas: dict[str, dict] = {}
    for datos in lineas:
        existente = combinadas.get(datos["clave_linea"])
        if existente is None:
            combinadas[datos["clave_linea"]] = dict(datos)
        else:
            for campo, valor in datos.items():
                if valor is not None:
                    existente[campo] = valor
    return list(combinadas.values())


def guardar_lineas_catalogo(
    db: Session, lote_id: Optional[int], lineas: list[dict]
) -> ResultadoGuardadoCatalogo:
    """Escritura por clave, no añadido ciego (CLAUDE.md sección 9.9): una
    línea ya vista para este lote se actualiza, nunca se duplica. La
    actualización solo pisa los campos que la nueva extracción sí trae
    (`None` no borra un valor ya conocido) — necesario porque el mismo
    cuadro de precios puede reaparecer en el documento con menos columnas
    (p.ej. una tabla de "criterios técnicos" que repite código, descripción
    y precio pero no trae cantidad): la segunda pasada no debe borrar la
    cantidad que sí trajo la primera.

    No hace `commit()`: el llamador decide cuándo (CLAUDE.md, sesión de
    rodaje 2026-09-03, punto 3 — antes cada llamada confirmaba por su cuenta,
    así que un documento con varios lotes podía dejar committed las líneas
    de un grupo y fallar en el siguiente, dejando el catálogo con restos de
    un expediente marcado como fallido). `ejecutar_extraccion_expediente`
    hace un único `commit()` por documento tras guardar todos sus grupos: o
    se guarda entero, o el `rollback()` del `except` lo deshace entero.

    `lote_id=None` es el caso huérfano (CLAUDE.md, encargo de esta sesión,
    punto 3): una tabla cuyo lote no se pudo determinar sin ambigüedad. El
    filtro de existencia siempre incluye `expediente_id` además de
    `lote_id`, aunque `lote_id` ya identifique el lote cuando no es None —
    sin él, dos huérfanas del mismo `codigo_precio` ("P-001", frecuente
    entre expedientes distintos) en dos expedientes distintos colisionarían
    entre sí, porque Postgres no deduplica `NULL` en la constraint UNIQUE de
    `lote_id`: aquí la idempotencia de las huérfanas la garantiza este
    filtro explícito, no la constraint de base de datos."""
    creadas = 0
    actualizadas = 0
    for datos in _combinar_por_clave(lineas):
        existente = (
            db.query(LineaCatalogo)
            .filter_by(lote_id=lote_id, expediente_id=datos["expediente_id"], clave_linea=datos["clave_linea"])
            .one_or_none()
        )
        if existente is None:
            db.add(LineaCatalogo(lote_id=lote_id, **datos))
            creadas += 1
        else:
            for campo, valor in datos.items():
                if valor is not None:
                    setattr(existente, campo, valor)
            actualizadas += 1
    return ResultadoGuardadoCatalogo(creadas=creadas, actualizadas=actualizadas)
