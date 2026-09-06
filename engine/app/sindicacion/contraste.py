"""Bloque 2, punto 4 (CONTEXTO.md sección 24): "Guárdalos como fuente
independiente y úsalos para contrastar con lo que extraiga el motor de los
PDFs." Dos fuentes que se verifican entre sí, no una que sustituye a la
otra — pero no con la misma autoridad (CONTEXTO.md sección 26): esta función
solo detecta y describe el desajuste, nunca decide mandar nada a revisión —
eso es responsabilidad de quien la llama
(`app.worker._contrastar_con_sindicacion`), y desde la sección 26 nunca lo
hace."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Expediente, SindicacionExpediente

# 1% relativo o 1 € absoluto, lo que sea mayor: suficiente para no disparar
# por ruido de redondeo entre dos fuentes independientes (una en euros
# "sin impuestos" con hasta 4 decimales, sección 8; la otra igual, pero
# calculada en otro sistema), nunca para esconder una discrepancia real.
_TOLERANCIA_RELATIVA = Decimal("0.01")
_TOLERANCIA_MINIMA = Decimal("1")


def _no_cuadra(motor: Optional[Decimal], sindicacion: Optional[Decimal]) -> bool:
    if motor is None or sindicacion is None:
        return False
    tolerancia = max(_TOLERANCIA_MINIMA, abs(sindicacion) * _TOLERANCIA_RELATIVA)
    return abs(motor - sindicacion) > tolerancia


def contrastar_expediente(db: Session, expediente: Expediente) -> Optional[str]:
    """Compara `Expediente.importe_licitacion`/`importe_adjudicacion` (lo
    que extrajo la cascada de los PDFs, siempre "sin impuestos" — CONTEXTO.md
    sección 4) contra la instantánea de sindicación más reciente del mismo
    expediente (`app.sindicacion.descubrimiento`). Devuelve `None` si no
    hay nada que contrastar (sin fila de sindicación, o sin importe
    extraído todavía) o si los dos cuadran dentro de tolerancia; si no, un
    motivo de revisión con los dos valores, para que quien revise vea la
    discrepancia sin tener que ir a buscarla."""
    fila = db.execute(
        select(SindicacionExpediente).where(
            SindicacionExpediente.codigo_expediente == expediente.codigo_expediente
        )
    ).scalar_one_or_none()
    if fila is None:
        return None

    motivos: list[str] = []
    if _no_cuadra(expediente.importe_licitacion, fila.importe_licitacion_sin_impuestos):
        motivos.append(
            f"importe de licitación no cuadra con sindicación: motor={expediente.importe_licitacion} € / "
            f"sindicación={fila.importe_licitacion_sin_impuestos} € (periodo {fila.periodo_zip})"
        )
    if _no_cuadra(expediente.importe_adjudicacion, fila.importe_adjudicacion_sin_impuestos):
        motivos.append(
            f"importe de adjudicación no cuadra con sindicación: motor={expediente.importe_adjudicacion} € / "
            f"sindicación={fila.importe_adjudicacion_sin_impuestos} € (periodo {fila.periodo_zip})"
        )
    return "; ".join(motivos) if motivos else None
