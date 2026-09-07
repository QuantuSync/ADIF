from typing import Optional

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Usuario, get_current_user
from app.config import settings
from app.db import get_db
from app.extraccion.descubrimiento_matriz import TIPO_TRABAJO as TIPO_TRABAJO_DESCUBRIMIENTO_PEDIDOS
from app.extraccion.estado_sap import cargar_estado_sap
from app.mantenimiento.ciclo import TIPO_TRABAJO
from app.mantenimiento.copia_seguridad import TIPO_TRABAJO as TIPO_TRABAJO_COPIA
from app.mantenimiento.programacion import (
    DISPARADO_POR_MANUAL,
    obtener_estado,
    obtener_estado_copia,
    obtener_estado_descubrimiento_pedidos,
)
from app.models import TrabajoCola
from app.queue import encolar_trabajo
from app.schemas import EstadoMantenimientoOut, EstadoSapCargaOut, TrabajoOut
from app.sindicacion.descubrimiento import TIPO_TRABAJO as TIPO_TRABAJO_SINDICACION_BACKFILL

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
    """Encola el ciclo completo de mantenimiento (CONTEXTO.md sección 23,
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
    """CONTEXTO.md, bloque 3 punto 3: cuándo fue la última ejecución, qué
    encontró (`ultima_ejecucion.resultado`), si hay una en curso ahora
    mismo, y cuándo tocaría la próxima programada."""
    return obtener_estado(db)


@router.get("/mantenimiento/historial", response_model=list[TrabajoOut])
def historial_mantenimiento(
    limite: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """CONTEXTO.md, bloque 3 punto 4: registro histórico, más reciente
    primero — para responder "por qué apareció este expediente" o "por qué
    no se actualizó aquel" sin tener que ir a la base de datos a mano. Es
    la propia `trabajos_cola` (CONTEXTO.md sección 10: consultable con SQL),
    no una tabla nueva que duplique la misma información."""
    return db.execute(
        select(TrabajoCola).where(TrabajoCola.tipo == TIPO_TRABAJO).order_by(TrabajoCola.created_at.desc()).limit(limite)
    ).scalars().all()


@router.post("/mantenimiento/copias/ejecutar", response_model=TrabajoOut)
def lanzar_copia_seguridad(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Copias de seguridad automáticas (sesión 2026-09-06): botón manual,
    mismo trabajo (`copia_seguridad`) que lanza solo la ejecución
    programada (`app.mantenimiento.programacion`), útil para forzar una
    copia antes de una operación delicada sin esperar al intervalo
    configurado."""
    trabajo = encolar_trabajo(
        db, tipo=TIPO_TRABAJO_COPIA, payload={"disparado_por": DISPARADO_POR_MANUAL}
    )
    return trabajo


@router.get("/mantenimiento/copias/estado", response_model=EstadoMantenimientoOut)
def estado_copia_seguridad(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Igual que `GET /mantenimiento/estado`, para las copias de seguridad
    automáticas: cuándo fue la última, qué encontró, y cuándo tocaría la
    próxima."""
    return obtener_estado_copia(db)


@router.get("/mantenimiento/copias/historial", response_model=list[TrabajoOut])
def historial_copia_seguridad(
    limite: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Igual que `GET /mantenimiento/historial`, filtrado por
    `copia_seguridad` -- misma `trabajos_cola`, sin tabla nueva."""
    return db.execute(
        select(TrabajoCola)
        .where(TrabajoCola.tipo == TIPO_TRABAJO_COPIA)
        .order_by(TrabajoCola.created_at.desc())
        .limit(limite)
    ).scalars().all()


class SindicacionBackfillPeticion(BaseModel):
    # Hallazgo real (sesión 2026-09-07, caso 6.26/28510.0014): el ciclo
    # normal solo revisa el mes en curso -- este es el botón manual para
    # barrer varios meses pasados de una vez, sin el coste de
    # descargar/extraer que llevaría el ciclo completo. `periodos` manda si
    # se da; si no, `meses` (los últimos N, mes en curso incluido).
    periodos: Optional[list[str]] = None
    meses: int = 12


@router.post("/mantenimiento/sindicacion/backfill", response_model=TrabajoOut)
def lanzar_backfill_sindicacion(
    peticion: SindicacionBackfillPeticion = Body(default_factory=SindicacionBackfillPeticion),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Barrido de descubrimiento por sindicación sobre varios periodos
    pasados (`app.sindicacion.descubrimiento.descubrir_backfill`) -- cierra
    el hueco real de que nada, hasta esta sesión, comprobaba un mes que no
    fuera el actual."""
    payload = {"periodos": peticion.periodos, "meses": peticion.meses}
    trabajo = encolar_trabajo(db, tipo=TIPO_TRABAJO_SINDICACION_BACKFILL, payload=payload)
    return trabajo


@router.get("/mantenimiento/sindicacion/historial", response_model=list[TrabajoOut])
def historial_backfill_sindicacion(
    limite: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Igual que `GET /mantenimiento/historial`, filtrado por
    `sindicacion_backfill`."""
    return db.execute(
        select(TrabajoCola)
        .where(TrabajoCola.tipo == TIPO_TRABAJO_SINDICACION_BACKFILL)
        .order_by(TrabajoCola.created_at.desc())
        .limit(limite)
    ).scalars().all()


class DescubrimientoPedidosPeticion(BaseModel):
    # Sin dar, recorre todas las matrices ya conocidas (botón general de
    # `/mantenimiento`); con él, acota a una sola (botón de su propia ficha
    # en `/expedientes`).
    matriz_expediente_id: Optional[int] = None


@router.post("/mantenimiento/descubrimiento-pedidos/ejecutar", response_model=TrabajoOut)
def lanzar_descubrimiento_pedidos(
    peticion: DescubrimientoPedidosPeticion = Body(default_factory=DescubrimientoPedidosPeticion),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Descubrimiento inverso matriz -> pedidos (sesión de descubrimiento
    inverso): botón manual, mismo trabajo que lanza solo la ejecución
    programada semanal."""
    payload = {"matriz_expediente_id": peticion.matriz_expediente_id, "disparado_por": DISPARADO_POR_MANUAL}
    trabajo = encolar_trabajo(db, tipo=TIPO_TRABAJO_DESCUBRIMIENTO_PEDIDOS, payload=payload)
    return trabajo


@router.get("/mantenimiento/descubrimiento-pedidos/estado", response_model=EstadoMantenimientoOut)
def estado_descubrimiento_pedidos(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Igual que `GET /mantenimiento/estado`, para el descubrimiento inverso
    matriz -> pedidos: cuándo fue la última ejecución, qué encontró, y cuándo
    tocaría la próxima."""
    return obtener_estado_descubrimiento_pedidos(db)


@router.get("/mantenimiento/descubrimiento-pedidos/historial", response_model=list[TrabajoOut])
def historial_descubrimiento_pedidos(
    limite: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Igual que `GET /mantenimiento/historial`, filtrado por
    `descubrimiento_pedidos`."""
    return db.execute(
        select(TrabajoCola)
        .where(TrabajoCola.tipo == TIPO_TRABAJO_DESCUBRIMIENTO_PEDIDOS)
        .order_by(TrabajoCola.created_at.desc())
        .limit(limite)
    ).scalars().all()


@router.post("/mantenimiento/estado-sap/cargar", response_model=EstadoSapCargaOut)
def cargar_estado_contrato_sap(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Bloque 1, sesión del Excel de ejecución SAP (2026-09-07): recarga
    `estado_contrato_sap` desde `ESTADO_SAP_PATH` (`app.extraccion.estado_sap`)
    -- fuente de entrada permanente, igual que el Excel de códigos, no una
    carga puntual. Repetible: se puede llamar tantas veces como haga falta
    (cada exportación nueva de ADIF se vuelve a montar en la misma ruta) sin
    duplicar nada, por `codigo_expediente` exacto. Síncrono a propósito, sin
    pasar por la cola: es una lectura local de un fichero de unos cientos de
    filas, sin red ni PDFs de por medio -- del mismo orden de coste que
    `POST /expedientes`, no del ciclo de mantenimiento."""
    return cargar_estado_sap(db, settings.estado_sap_path)
