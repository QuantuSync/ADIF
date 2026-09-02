import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.extraccion.normalizacion import (
    limpiar_codigo_celda,
    limpiar_texto_celda,
    parsear_importe_es,
    parsear_numero_es,
)
from app.extraccion.tabla import TablaExtraida
from app.models import LineaCatalogo


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
    baja_lote: Optional[Decimal],
    orden_aparicion: int,
) -> dict:
    """Etapa 6 (normalización + derivación, CLAUDE.md secciones 4 y 8): una
    fila cruda de tabla + el mapeo de columnas de la etapa 5 -> los campos de
    una `LineaCatalogo`. `precio_adjudicado` se deriva aquí, no se busca en
    ningún documento (CLAUDE.md sección 4: "no existe una tabla de precios
    adjudicados")."""

    def _valor(campo: str) -> Optional[str]:
        indice = mapeo.get(campo)
        if indice is None or indice >= len(fila):
            return None
        return fila[indice]

    codigo_precio = limpiar_codigo_celda(_valor("codigo_precio"))
    matricula = limpiar_codigo_celda(_valor("matricula"))
    descripcion = limpiar_texto_celda(_valor("descripcion")) or ""
    unidad_medida = limpiar_texto_celda(_valor("unidad_medida"))

    cantidad_bruta = _valor("cantidad")
    cantidad = parsear_numero_es(cantidad_bruta) if cantidad_bruta else None

    precio_bruto = _valor("precio_unitario")
    precio_unitario = parsear_importe_es(precio_bruto) if precio_bruto else None

    precio_adjudicado = None
    if precio_unitario is not None and baja_lote is not None:
        precio_adjudicado = precio_unitario * (Decimal("1") - baja_lote)

    return {
        "clave_linea": calcular_clave_linea(codigo_precio, matricula, descripcion, orden_aparicion),
        "orden_aparicion": orden_aparicion,
        "codigo_precio": codigo_precio,
        "matricula": matricula,
        "descripcion": descripcion,
        "unidad_medida": unidad_medida,
        "cantidad": cantidad,
        "precio_unitario": precio_unitario,
        "baja_lote": baja_lote,
        "precio_adjudicado": precio_adjudicado,
        "documento_origen_id": documento_origen_id,
        "pagina": pagina,
        "fragmento": " | ".join((celda or "").strip() for celda in fila),
    }


def construir_lineas_desde_tabla(
    tabla: TablaExtraida,
    mapeo: dict[str, Optional[int]],
    documento_origen_id: Optional[int],
    baja_lote: Optional[Decimal],
    orden_inicial: int,
) -> list[dict]:
    return [
        construir_linea_catalogo(
            fila, mapeo, tabla.pagina, documento_origen_id, baja_lote, orden_inicial + indice
        )
        for indice, fila in enumerate(tabla.filas)
    ]


@dataclass(frozen=True)
class ResultadoGuardadoCatalogo:
    creadas: int
    actualizadas: int


def guardar_lineas_catalogo(db: Session, lote_id: int, lineas: list[dict]) -> ResultadoGuardadoCatalogo:
    """Escritura por clave, no añadido ciego (CLAUDE.md sección 9.9): una
    línea ya vista para este lote se actualiza, nunca se duplica. La
    actualización solo pisa los campos que la nueva extracción sí trae
    (`None` no borra un valor ya conocido) — necesario porque el mismo
    cuadro de precios puede reaparecer en el documento con menos columnas
    (p.ej. una tabla de "criterios técnicos" que repite código, descripción
    y precio pero no trae cantidad): la segunda pasada no debe borrar la
    cantidad que sí trajo la primera."""
    creadas = 0
    actualizadas = 0
    for datos in lineas:
        existente = (
            db.query(LineaCatalogo)
            .filter_by(lote_id=lote_id, clave_linea=datos["clave_linea"])
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
    db.commit()
    return ResultadoGuardadoCatalogo(creadas=creadas, actualizadas=actualizadas)
