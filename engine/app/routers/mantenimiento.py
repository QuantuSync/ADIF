from typing import Optional

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Usuario, get_current_user
from app.db import get_db
from app.mantenimiento.ciclo import TIPO_TRABAJO
from app.queue import encolar_trabajo
from app.schemas import TrabajoOut

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
    bloque 1: descubrir, descargar lo que falte, extraer lo que falte). El
    botón manual de la web (bloque 3) llama a esta misma ruta."""
    payload = {
        "forzar": peticion.forzar,
        "forzar_expedientes": peticion.forzar_expedientes,
        "sindicacion_desactivada": peticion.sindicacion_desactivada,
        "sindicacion_periodo": peticion.sindicacion_periodo,
    }
    trabajo = encolar_trabajo(db, tipo=TIPO_TRABAJO, payload=payload)
    return trabajo
