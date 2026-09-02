"""Detección del caso de precios unitarios (CLAUDE.md sección 4 y 12).

Cuando el pliego fija un presupuesto techo y el licitador solo oferta una
baja porcentual, importe de licitación e importe de adjudicación llegan
iguales al Anuncio PCSP — no porque no haya habido rebaja, sino porque el
"precio" que se adjudica es la baja, no un importe distinto. La fórmula
ingenua `1 - adjudicado/licitación` da 0 % ahí, y devolver ese 0 % es el
error que este módulo existe para no cometer (ejemplo real, CLAUDE.md sección
4: expediente 6.24/28510.0088, 1.000.000 € en ambos importes, baja real
0,50 %).

Fuera de ese caso, la baja se puede seguir derivando de los importes; si
además hay una baja declarada en texto, las dos deben cuadrar (sección 12) o
el expediente va a la cola de revisión — no se corrige solo.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

# Medio punto porcentual. Los importes en los documentos reales vienen
# redondeados a 2 decimales de euro; en un contrato de varios cientos de
# miles de euros eso ya mueve la baja calculada varias milésimas sin que
# signifique una discrepancia real.
TOLERANCIA_BAJA_POR_DEFECTO = Decimal("0.005")


@dataclass(frozen=True)
class BajaEfectiva:
    baja: Optional[Decimal]  # fracción; None solo si hace falta revisión y no hay nada que ofrecer
    caso_precios_unitarios: bool
    requiere_revision: bool
    motivo: str


def calcular_baja_efectiva(
    importe_licitacion: Decimal,
    importe_adjudicacion: Decimal,
    baja_declarada: Optional[Decimal] = None,
    tolerancia: Decimal = TOLERANCIA_BAJA_POR_DEFECTO,
) -> BajaEfectiva:
    if importe_licitacion == 0:
        raise ValueError("importe_licitacion no puede ser 0 (dato de origen incoherente, no un caso a manejar aquí)")

    importes_coinciden = importe_licitacion == importe_adjudicacion

    if importes_coinciden:
        if baja_declarada is not None:
            return BajaEfectiva(
                baja=baja_declarada,
                caso_precios_unitarios=True,
                requiere_revision=False,
                motivo="precios unitarios: licitación y adjudicación coinciden; la baja es la declarada en el texto, no 1 - adjudicado/licitación",
            )
        return BajaEfectiva(
            baja=None,
            caso_precios_unitarios=True,
            requiere_revision=True,
            motivo="licitación y adjudicación coinciden (posible caso de precios unitarios) pero no se encontró baja declarada en ningún documento",
        )

    baja_por_importes = 1 - (importe_adjudicacion / importe_licitacion)

    if baja_declarada is not None and abs(baja_declarada - baja_por_importes) > tolerancia:
        return BajaEfectiva(
            baja=baja_declarada,
            caso_precios_unitarios=False,
            requiere_revision=True,
            motivo=(
                f"la baja declarada ({baja_declarada:.4%}) no cuadra con la baja que resulta de los importes "
                f"({baja_por_importes:.4%}); posible error de transcripción o de cruce de documentos"
            ),
        )

    return BajaEfectiva(
        baja=baja_declarada if baja_declarada is not None else baja_por_importes,
        caso_precios_unitarios=False,
        requiere_revision=False,
        motivo="baja derivada de los importes de licitación y adjudicación",
    )
