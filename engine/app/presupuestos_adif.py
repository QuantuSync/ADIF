"""Hoja "Presupuestos ADIF" del Excel: el presupuesto que ADIF publica de cada
expediente contra el que la app lee de los documentos publicados.

Bloque 2 del encargo de la sesión 2026-09-19 (sexta parte). **La columna de
presupuesto todavía no está en el listado que ADIF nos envía** (se comprobó
columna a columna: el fichero del 18/09/2026 trae solo título, expediente,
fecha de creación y estado, CONTEXTO.md sección 7). Lo que hay montado aquí es
la salida ya probada, para que meter el listado ampliado sea dejarlo en
`Ejemplo/Input` y ejecutar un comando (`docs/entradas-pendientes-del-cliente.md`).

**Qué compara, y qué no.** `Expediente.presupuesto_licitacion_adif` es lo que
dice el listado de ADIF; `Expediente.importe_licitacion` es lo que el sistema
leyó de un documento publicado, con su traza (documento y página). No se
mezclan nunca ni uno pisa al otro -- exactamente por lo mismo que "Estado
según ADIF" y "Estado que consta publicado en la Plataforma" son dos columnas
distintas (CONTEXTO.md sección 7): un volcado del SAP de ADIF y lo que publica
la Plataforma son dos hechos, y juntarlos dejaría cada cifra sin procedencia.

**El orden de la hoja es el que pidió el cliente**: primero las
coincidencias, después las diferencias **de mayor a menor**, y al final los
expedientes sin importe. Cada bloque va con su etiqueta en la columna
"Resultado", así que la hoja se puede filtrar por ella sin depender del orden.

**La hoja solo se escribe si hay algo que comparar.** Sin ningún presupuesto
cargado (que es el estado de hoy), no se añade al Excel: una hoja vacía en el
entregable haría pensar que falta un dato que nadie ha mandado todavía.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Expediente

NOMBRE_HOJA = "Presupuestos ADIF"

COINCIDE = "Coincide"
DIFIERE = "Difiere"
SIN_IMPORTE_LEIDO = "Sin importe leído de los documentos"
SIN_PRESUPUESTO_ADIF = "Sin presupuesto en el listado de ADIF"

COLUMNAS = (
    "Código de expediente",
    "Título expediente",
    "Presupuesto de licitación según ADIF",
    "Importe de licitación leído de los documentos",
    "Diferencia (ADIF − documentos)",
    "Diferencia relativa",
    "Resultado",
)

# Dos importes en euros con céntimos: se comparan al céntimo, sin tolerancia.
# Es el mismo criterio que el resto del sistema usa con el dinero del
# documento (CONTEXTO.md sección 8, `Decimal` nunca `float`).
_CENTIMO = Decimal("0.01")


@dataclass(frozen=True)
class FilaPresupuestoAdif:
    codigo_expediente: str
    titulo: Optional[str]
    presupuesto_adif: Optional[Decimal]
    importe_documentos: Optional[Decimal]
    diferencia: Optional[Decimal]
    diferencia_relativa: Optional[Decimal]
    resultado: str


def _cuantizar(valor: Optional[Decimal]) -> Optional[Decimal]:
    return None if valor is None else Decimal(valor).quantize(_CENTIMO)


def construir_presupuestos_adif(db: Session) -> list[FilaPresupuestoAdif]:
    """Una fila por expediente que traiga presupuesto en el listado de ADIF.
    Los que no lo traen no salen: la hoja contesta "¿cuadra lo que ADIF dice
    con lo que hemos leído?", y de un expediente sin cifra de ADIF no hay nada
    que contestar."""
    filas: list[FilaPresupuestoAdif] = []
    for expediente in db.execute(
        select(Expediente).where(Expediente.presupuesto_licitacion_adif.isnot(None))
    ).scalars():
        adif = _cuantizar(expediente.presupuesto_licitacion_adif)
        leido = _cuantizar(expediente.importe_licitacion)
        if adif is None:
            resultado, diferencia, relativa = SIN_PRESUPUESTO_ADIF, None, None
        elif leido is None:
            resultado, diferencia, relativa = SIN_IMPORTE_LEIDO, None, None
        else:
            diferencia = adif - leido
            relativa = (diferencia / adif) if adif else None
            resultado = COINCIDE if diferencia == 0 else DIFIERE
        filas.append(
            FilaPresupuestoAdif(
                codigo_expediente=expediente.codigo_expediente,
                titulo=expediente.nombre_proyecto,
                presupuesto_adif=adif,
                importe_documentos=leido,
                diferencia=diferencia,
                diferencia_relativa=relativa,
                resultado=resultado,
            )
        )
    return ordenar(filas)


_ORDEN_BLOQUE = {COINCIDE: 0, DIFIERE: 1, SIN_IMPORTE_LEIDO: 2, SIN_PRESUPUESTO_ADIF: 3}


def ordenar(filas: list[FilaPresupuestoAdif]) -> list[FilaPresupuestoAdif]:
    """Coincidencias, diferencias de mayor a menor (por valor absoluto: una
    diferencia de −900.000 € importa tanto como una de +900.000 €), y al final
    los expedientes sin importe. Dentro de cada bloque, por código, para que
    dos exportaciones seguidas den exactamente el mismo fichero."""
    return sorted(
        filas,
        key=lambda f: (
            _ORDEN_BLOQUE.get(f.resultado, 9),
            -abs(f.diferencia) if f.diferencia is not None else Decimal("0"),
            f.codigo_expediente,
        ),
    )
