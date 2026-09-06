from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Usuario, get_current_user
from app.catalogo_consulta import consultar_catalogo, fila_a_dict
from app.db import get_db
from app.exportacion import generar_excel_catalogo
from app.extraccion.cruce_codigos import asegurar_cruce_codigos
from app.models import Expediente
from app.schemas import CatalogoRespuesta

router = APIRouter()

_TAMANO_PAGINA_MAX = 200


@router.get("/catalogo", response_model=CatalogoRespuesta)
def explorar_catalogo(
    expediente: str | None = None,
    lote: str | None = None,
    matricula: str | None = None,
    q: str | None = None,
    pagina: int = Query(default=1, ge=1),
    tamano_pagina: int = Query(default=50, ge=1, le=_TAMANO_PAGINA_MAX),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """CLAUDE.md, encargo de esta sesión, punto 1: catálogo con filtros por
    expediente, lote y material, y búsqueda por matrícula a través de todos
    los expedientes (sin filtro de `expediente`, `matricula` ya cruza todo
    el catálogo)."""
    resultado = consultar_catalogo(
        db, expediente=expediente, lote=lote, matricula=matricula, q=q,
        pagina=pagina, tamano_pagina=tamano_pagina,
    )
    # Backfill perezoso del cruce con el Excel de códigos (docstring de
    # `asegurar_cruce_codigos`), solo sobre los expedientes de esta página.
    expedientes_pagina = {expediente for _l, _lo, expediente, _d in resultado.filas}
    cambios = False
    for exp in expedientes_pagina:
        antes = exp.codigos_cruzados
        asegurar_cruce_codigos(db, exp)
        cambios = cambios or exp.codigos_cruzados != antes
    if cambios:
        db.commit()
    return CatalogoRespuesta(
        total=resultado.total,
        pagina=pagina,
        tamano_pagina=tamano_pagina,
        lineas=[fila_a_dict(*fila) for fila in resultado.filas],
    )


@router.get("/catalogo/exportar.xlsx")
def exportar_catalogo(
    incluir_pendientes: bool = Query(
        default=False,
        description=(
            "Incluye en \"Materiales\" las líneas cuya tabla de origen no se pudo asociar a un "
            "lote sin ambigüedad (huérfanas, docstring de app.exportacion). Por defecto solo van "
            "a la hoja \"Resumen\", agrupadas por motivo."
        ),
    ),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """CLAUDE.md, encargo de esta sesión, punto 4: un solo catálogo
    acumulativo generado desde la base de datos a demanda, nunca la fuente
    de los datos (CLAUDE.md sección 9.8)."""
    sin_cruzar = db.execute(
        select(Expediente).where(Expediente.codigos_cruzados.is_(None))
    ).scalars().all()
    if sin_cruzar:
        for expediente in sin_cruzar:
            asegurar_cruce_codigos(db, expediente)
        db.commit()
    contenido = generar_excel_catalogo(db, incluir_pendientes_sin_lote=incluir_pendientes)
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=catalogo_materiales_adif.xlsx"},
    )
