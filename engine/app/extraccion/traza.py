"""Escritura de `trazas_origen` sin duplicar (sesión 2026-09-17, bloque 4,
`docs/sesion-2026-09-17-escaneados-codigo-material.md`).

Cada extracción volvía a añadir la traza de cada importe, adjudicatario y
baja, aunque fuera idéntica a la de la pasada anterior: 35.777 trazas para
unas 2.000 distintas (`importe_licitacion` de expediente, 8.360 para 374),
contra el invariante 9 de CONTEXTO.md. Una traza idéntica (misma entidad,
campo, documento, página, fragmento y valor) sustituye a la anterior en vez
de sumarse: se borra la vieja y se inserta la nueva, así la más reciente de
cada campo sigue siendo la de `id` mayor (lo que leen `herencia_matriz` y la
web). Una traza con otro valor u otro documento se conserva: es historia, no
un duplicado.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import TrazaOrigen


def registrar_traza(
    db: Session,
    *,
    entidad_tipo: str,
    entidad_id: int,
    campo: str,
    documento_id: int,
    pagina: Optional[int],
    fragmento: Optional[str],
    valor_extraido: Optional[str],
) -> None:
    db.flush()  # una traza igual añadida antes en esta misma pasada también cuenta
    db.execute(
        delete(TrazaOrigen)
        .where(
            TrazaOrigen.entidad_tipo == entidad_tipo,
            TrazaOrigen.entidad_id == entidad_id,
            TrazaOrigen.campo == campo,
            TrazaOrigen.documento_id == documento_id,
            TrazaOrigen.pagina.is_not_distinct_from(pagina),
            TrazaOrigen.fragmento.is_not_distinct_from(fragmento),
            TrazaOrigen.valor_extraido.is_not_distinct_from(valor_extraido),
        )
        .execution_options(synchronize_session=False)
    )
    db.add(
        TrazaOrigen(
            entidad_tipo=entidad_tipo,
            entidad_id=entidad_id,
            campo=campo,
            documento_id=documento_id,
            pagina=pagina,
            fragmento=fragmento,
            valor_extraido=valor_extraido,
        )
    )
