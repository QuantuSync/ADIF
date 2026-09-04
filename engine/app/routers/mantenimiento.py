from typing import Optional

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Usuario, get_current_user
from app.db import get_db
from app.mantenimiento.ciclo import TIPO_TRABAJO
from app.mantenimiento.programacion import DISPARADO_POR_MANUAL, obtener_estado
from app.models import TrabajoCola
from app.queue import encolar_trabajo
from app.schemas import EstadoMantenimientoOut, TrabajoOut

router = APIRouter()


class CicloMantenimientoPeticion(BaseModel):
    # Bloque 1, punto 4: forzar reproceso aunque no haya cambios, tanto de
    # forma global como por expediente concreto — para desarrollo.
    forzar: bool = False
    forzar_expedientes: list[int] = []
    # Bloque 2: desactivar el descubrimiento por sindicación de esta
    # ejecución (nunca la red si no hace falta), o reprocesar un periodo
    # concreto en vez del mes en curso (`AAAAMM`) — backfill manual de un
    # mes anterior, sin esperar a que vuelva a tocarle al ciclo programado.
    sindicacion_desactivada: bool = False
    sindicacion_periodo: Optional[str] = None


@router.post("/mantenimiento/ejecutar", response_model=TrabajoOut)
def lanzar_ciclo_mantenimiento(
    peticion: CicloMantenimientoPeticion = Body(default_factory=CicloMantenimientoPeticion),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Encola el ciclo completo de mantenimiento (CLAUDE.md sección 23,
    bloque 1: descubrir, descargar lo que falte, extraer lo que falte). Es
    el botón manual de la web (bloque 3, punto 3) — el mismo ciclo que
    lanza solo la ejecución programada (`app.mantenimiento.programacion`),
    solo que `disparado_por` queda como "manual" en el histórico."""
    payload = {
        "forzar": peticion.forzar,
        "forzar_expedientes": peticion.forzar_expedientes,
        "sindicacion_desactivada": peticion.sindicacion_desactivada,
        "sindicacion_periodo": peticion.sindicacion_periodo,
        "disparado_por": DISPARADO_POR_MANUAL,
    }
    trabajo = encolar_trabajo(db, tipo=TIPO_TRABAJO, payload=payload)
    return trabajo


@router.get("/mantenimiento/estado", response_model=EstadoMantenimientoOut)
def estado_mantenimiento(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """CLAUDE.md, bloque 3 punto 3: cuándo fue la última ejecución, qué
    encontró (`ultima_ejecucion.resultado`), si hay una en curso ahora
    mismo, y cuándo tocaría la próxima programada."""
    return obtener_estado(db)


@router.get("/mantenimiento/historial", response_model=list[TrabajoOut])
def historial_mantenimiento(
    limite: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """CLAUDE.md, bloque 3 punto 4: registro histórico, más reciente
    primero — para responder "por qué apareció este expediente" o "por qué
    no se actualizó aquel" sin tener que ir a la base de datos a mano. Es
    la propia `trabajos_cola` (CLAUDE.md sección 10: consultable con SQL),
    no una tabla nueva que duplique la misma información."""
    return db.execute(
        select(TrabajoCola).where(TrabajoCola.tipo == TIPO_TRABAJO).order_by(TrabajoCola.created_at.desc()).limit(limite)
    ).scalars().all()
