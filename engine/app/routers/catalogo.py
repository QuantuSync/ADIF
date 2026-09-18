from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.auth import Usuario, get_current_user
from app.catalogo_consulta import ORDENES_VALIDOS, consultar_catalogo, fila_a_dict
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
    orden: str = Query(default="completitud", pattern="^(" + "|".join(ORDENES_VALIDOS) + ")$"),
    pagina: int = Query(default=1, ge=1),
    tamano_pagina: int = Query(default=50, ge=1, le=_TAMANO_PAGINA_MAX),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """CONTEXTO.md, encargo de esta sesión, punto 1: catálogo con filtros por
    expediente, lote y material, y búsqueda por matrícula a través de todos
    los expedientes (sin filtro de `expediente`, `matricula` ya cruza todo
    el catálogo).

    `orden` (encargo de la sesión 2026-09-07, `app.catalogo_consulta` para
    la justificación completa): "completitud" por defecto -- la primera
    pantalla sin filtrar, la que ve el cliente, ya no aterriza siempre en
    los mismos expedientes con las tablas de origen más escasas solo por
    venir primero en orden alfabético. "alfabetico" se deja disponible
    como antes."""
    resultado = consultar_catalogo(
        db, expediente=expediente, lote=lote, matricula=matricula, q=q,
        pagina=pagina, tamano_pagina=tamano_pagina, orden=orden,
    )
    # Backfill perezoso del cruce con el Excel de códigos (docstring de
    # `asegurar_cruce_codigos`), solo sobre los expedientes de esta página.
    expedientes_pagina = {expediente for _l, _lo, expediente, _d, _n in resultado.filas}
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
    """CONTEXTO.md, encargo de esta sesión, punto 4: un solo catálogo
    acumulativo generado desde la base de datos a demanda, nunca la fuente
    de los datos (CONTEXTO.md sección 9.8)."""
    # Backfill perezoso del cruce antes de generar el entregable: los que
    # nunca se intentaron, y (sesión 2026-09-18, bloque 2) los que cruzaron
    # antes de que existiera `cruce_fila_propia` -- sin eso no se sabe si su
    # "Código interno" es el suyo o el de otro expediente de su familia.
    # `asegurar_cruce_codigos` lo rehace una vez cada uno; en la siguiente
    # exportación esta consulta ya no los devuelve.
    sin_cruzar = db.execute(
        select(Expediente).where(
            or_(
                Expediente.codigos_cruzados.is_(None),
                and_(Expediente.codigos_cruzados.is_(True), Expediente.cruce_fila_propia.is_(None)),
            )
        )
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
