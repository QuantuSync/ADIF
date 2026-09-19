from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Usuario, get_current_user
from app.config import settings
from app.db import get_db
from app.extraccion.candidatos_matricula import calcular_candidatos
from app.extraccion.descubrimiento_matriz import TIPO_TRABAJO as TIPO_TRABAJO_DESCUBRIMIENTO_PEDIDOS
from app.extraccion.estado_sap import cargar_estado_sap
from app.extraccion.estados_adif import cargar_estados_adif
from app.extraccion.vigentes_remanente import cruzar_vigentes_con_remanente
from app.catalogo_antiguo import comparar_con_catalogo_antiguo, generar_informe_catalogo_antiguo
from app.conciliacion import construir_conciliacion
from app.exportacion import contar_filas_de_materiales
from app.extraccion.maestro_materiales import cargar_maestro_materiales, completar_unidades_desde_maestro
from app.extraccion.ocr_relectura import TIPO_TRABAJO as TIPO_TRABAJO_OCR_RELECTURA
from app.extraccion.sap_desglose import cargar_sap_desglose
from app.ingesta_local import TIPO_TRABAJO as TIPO_TRABAJO_INGESTA_LOCAL
from app.mantenimiento.auditoria import TIPO_TRABAJO as TIPO_TRABAJO_AUDITORIA
from app.mantenimiento.ciclo import TIPO_TRABAJO
from app.mantenimiento.copia_seguridad import TIPO_TRABAJO as TIPO_TRABAJO_COPIA
from app.mantenimiento.programacion import (
    DISPARADO_POR_MANUAL,
    obtener_estado,
    obtener_estado_auditoria,
    obtener_estado_copia,
    obtener_estado_descubrimiento_pedidos,
)
from app.models import Documento, TrabajoCola
from app.queue import encolar_trabajo
from app.schemas import (
    CatalogoAntiguoResumenOut,
    EstadoMantenimientoOut,
    EstadosAdifCargaOut,
    EstadoSapCargaOut,
    MaestroMaterialesCargaOut,
    ResumenCandidatosMatriculaOut,
    MaestroMaterialesCompletarOut,
    SapDesglosecargaOut,
    TrabajoOut,
    VigentesRemanenteCruceOut,
)
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
    # Sesión 2026-09-18, bloque 4: el ciclo lee estas dos del payload desde
    # que existe el descubrimiento por búsqueda (`app.mantenimiento.ciclo`),
    # pero este endpoint nunca las reenviaba -- construye el payload campo a
    # campo, y estas dos faltaban. Efecto real medido: cada reproceso lanzado
    # desde aquí (o desde el botón de la web, que manda `{}`) repetía la
    # búsqueda completa en la Plataforma aunque no hiciera ninguna falta --
    # las dos pasadas de la sesión 2026-09-17 la repitieron para 0
    # expedientes nuevos, a 10 s de espaciado por petición.
    busqueda_desactivada: bool = False
    busqueda_fragmentos: Optional[list[str]] = None


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
        "busqueda_desactivada": peticion.busqueda_desactivada,
        "busqueda_fragmentos": peticion.busqueda_fragmentos,
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


@router.post("/mantenimiento/auditoria/ejecutar", response_model=TrabajoOut)
def lanzar_auditoria_catalogo(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """BLOQUE 1, sesión de auditoría automática (2026-09-08): botón manual
    para lanzar la auditoría sin esperar al final del próximo ciclo de
    mantenimiento -- mismo trabajo (`auditoria_catalogo`) que se encola solo
    al terminar `app.mantenimiento.ciclo.ejecutar_ciclo_mantenimiento`.
    Solo detecta y avisa (`app.mantenimiento.auditoria`): nunca corrige nada
    por su cuenta."""
    trabajo = encolar_trabajo(db, tipo=TIPO_TRABAJO_AUDITORIA, payload={"disparado_por": DISPARADO_POR_MANUAL})
    return trabajo


@router.get("/mantenimiento/auditoria/estado", response_model=EstadoMantenimientoOut)
def estado_auditoria_catalogo(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Igual que `GET /mantenimiento/estado`, para la auditoría automática:
    cuándo fue la última ejecución y qué encontró
    (`ultima_ejecucion.resultado`, la lista completa de hallazgos)."""
    return obtener_estado_auditoria(db)


@router.get("/mantenimiento/auditoria/historial", response_model=list[TrabajoOut])
def historial_auditoria_catalogo(
    limite: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Igual que `GET /mantenimiento/historial`, filtrado por
    `auditoria_catalogo` -- misma `trabajos_cola`, sin tabla nueva."""
    return db.execute(
        select(TrabajoCola)
        .where(TrabajoCola.tipo == TIPO_TRABAJO_AUDITORIA)
        .order_by(TrabajoCola.created_at.desc())
        .limit(limite)
    ).scalars().all()


@router.post("/mantenimiento/ingesta-local/ejecutar", response_model=TrabajoOut)
def lanzar_ingesta_local(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Bloque 6, sesión de comparación documento-vs-listado interno: botón
    manual para recorrer `INGESTA_LOCAL_PATH` (`app.ingesta_local`) --
    expedientes vigentes en el SAP del cliente aportados por una carpeta
    local, en vez de descargados con navegador. Sin programación propia
    (a diferencia del ciclo de mantenimiento): el cliente avisa cuando su
    macro deja ficheros nuevos, no hace falta sondear solo."""
    trabajo = encolar_trabajo(db, tipo=TIPO_TRABAJO_INGESTA_LOCAL)
    return trabajo


@router.get("/mantenimiento/ingesta-local/historial", response_model=list[TrabajoOut])
def historial_ingesta_local(
    limite: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Igual que `GET /mantenimiento/auditoria/historial`: misma
    `trabajos_cola`, sin tabla nueva -- `resultado` de cada fila trae el
    resumen (`ResumenIngestaLocal.to_dict()`: carpetas leídas, expedientes
    nuevos, documentos nuevos, avisos de código discrepante...)."""
    return db.execute(
        select(TrabajoCola)
        .where(TrabajoCola.tipo == TIPO_TRABAJO_INGESTA_LOCAL)
        .order_by(TrabajoCola.created_at.desc())
        .limit(limite)
    ).scalars().all()


class OcrRelecturaPeticion(BaseModel):
    """Bloque 1, sesión 2026-09-19 (quinta parte): páginas concretas de un
    documento escaneado a releer con un modelo mejor que `MODEL_ID`. `modelo`
    es opcional; sin él se usa `OCR_MODELO_RELECTURA`, y sin ninguno de los
    dos el trabajo falla en vez de releer con el modelo de siempre."""

    documento_id: int
    paginas: list[int]
    modelo: Optional[str] = None


@router.post("/mantenimiento/ocr/releer", response_model=TrabajoOut)
def lanzar_relectura_optica(
    peticion: OcrRelecturaPeticion = Body(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Encola la relectura (`app.extraccion.ocr_relectura`). La API no llama
    al modelo nunca -- solo el worker tiene proveedor (CONTEXTO.md sección
    10) --, así que aquí solo se valida que el documento existe y se encola.

    Deliberadamente sin programación propia y sin disparo automático: releer
    con un modelo más caro es una decisión por documento, tomada mirando la
    lectura que hay, no algo que el ciclo deba intentar solo."""
    if not peticion.paginas:
        raise HTTPException(status_code=400, detail="hay que indicar al menos una página")
    documento = db.get(Documento, peticion.documento_id)
    if documento is None:
        raise HTTPException(status_code=404, detail=f"documento_id {peticion.documento_id} no existe")
    payload: dict = {"documento_id": peticion.documento_id, "paginas": peticion.paginas}
    if peticion.modelo:
        payload["modelo"] = peticion.modelo
    return encolar_trabajo(db, tipo=TIPO_TRABAJO_OCR_RELECTURA, payload=payload)


@router.get("/mantenimiento/ocr/historial", response_model=list[TrabajoOut])
def historial_relectura_optica(
    limite: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    return db.execute(
        select(TrabajoCola)
        .where(TrabajoCola.tipo == TIPO_TRABAJO_OCR_RELECTURA)
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


@router.post("/mantenimiento/estados-adif/cargar", response_model=EstadosAdifCargaOut)
def cargar_estados_de_adif(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Bloque 1, sesión 2026-09-18 (continuación): recarga `estado_adif` desde
    `ESTADOS_ADIF_PATH` (`app.extraccion.estados_adif`). Mismo mecanismo,
    mismo coste y mismas garantías que `/mantenimiento/estado-sap/cargar`, con
    una diferencia deliberada: **no da de alta ningún expediente**. Ver el
    docstring del módulo."""
    return cargar_estados_adif(db, settings.estados_adif_path)


@router.post("/mantenimiento/vigentes-remanente/cruzar", response_model=VigentesRemanenteCruceOut)
def cruzar_vigentes_remanente(
    buscar: bool = Query(
        True,
        description="Encolar la búsqueda en la Plataforma de los que no estén en la Conciliación.",
    ),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Bloque 2, sesión 2026-09-19 (sexta parte): el cruce de la lista de
    contratos vigentes con remanente que ADIF tiene que enviarnos
    (`VIGENTES_REMANENTE_PATH`, `app.extraccion.vigentes_remanente`).

    Devuelve, para cada uno, su Situación en la Conciliación -- la MISMA lista
    que escribe el Excel, construida aquí con el mismo recuento de filas de
    "Materiales" -- y encola la búsqueda en la Plataforma de los que no
    estén. Con `buscar=false` solo informa, sin tocar la red ni dar de alta
    nada."""
    conciliacion = construir_conciliacion(db, dict(contar_filas_de_materiales(db)))
    return cruzar_vigentes_con_remanente(
        db, settings.vigentes_remanente_path, conciliacion, buscar=buscar
    ).to_dict()


@router.get("/mantenimiento/catalogo-antiguo/resumen", response_model=CatalogoAntiguoResumenOut)
def resumen_catalogo_antiguo(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Las cifras del cruce con el catálogo antiguo de ADIF
    (`CATALOGO_ANTIGUO_PATH`, `app.catalogo_antiguo`), sin generar el fichero."""
    return comparar_con_catalogo_antiguo(db, settings.catalogo_antiguo_path).resumen.to_dict()


@router.get("/mantenimiento/catalogo-antiguo/informe.xlsx")
def informe_catalogo_antiguo(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """El informe de materiales que están en su catálogo y no en el nuestro,
    al revés, y diferencias de precio. **Va aparte del entregable**, que es la
    condición que puso el cliente: su propio fichero, nunca una hoja del Excel
    del catálogo."""
    informe = comparar_con_catalogo_antiguo(db, settings.catalogo_antiguo_path)
    contenido = generar_informe_catalogo_antiguo(informe)
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="informe_catalogo_antiguo_adif.xlsx"'},
    )


@router.post("/mantenimiento/sap-desglose/cargar", response_model=SapDesglosecargaOut)
def cargar_desglose_sap(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Bloque 6, cambios del cliente tras revisar el catálogo: recarga
    `sap_desglose_lineas` desde `SAP_DESGLOSE_PATH`
    (`app.extraccion.sap_desglose`). Mismo criterio que
    `POST /mantenimiento/estado-sap/cargar`: repetible sin duplicar (upsert
    por documento de compras + posición), síncrono, sin pasar por la cola."""
    return cargar_sap_desglose(db, settings.sap_desglose_path)


@router.post("/mantenimiento/maestro-materiales/cargar", response_model=MaestroMaterialesCargaOut)
def cargar_maestro_de_materiales(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Bloque 4, sesión 2026-09-09: recarga `maestro_materiales` desde
    `MAESTRO_MATERIALES_PATH` (`app.extraccion.maestro_materiales`). Mismo
    criterio que las demás fuentes de entrada: repetible sin duplicar (upsert
    por matrícula), síncrono, sin pasar por la cola. Solo carga la tabla de
    referencia -- no toca `lineas_catalogo` (ver el endpoint de abajo)."""
    return cargar_maestro_materiales(db, settings.maestro_materiales_path)


@router.post("/mantenimiento/maestro-materiales/completar-unidades", response_model=MaestroMaterialesCompletarOut)
def completar_unidades_de_medida(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Bloque 4, sesión 2026-09-09: aplica `maestro_materiales` (ya cargado
    por el endpoint de arriba) para rellenar `unidad_medida` de líneas del
    catálogo que tienen matrícula pero no unidad -- nunca pisa un valor ya
    extraído de un documento real (`app.extraccion.maestro_materiales.
    completar_unidades_desde_maestro`). Paso separado de la carga a
    propósito: cargar el maestro no debe escribir en el catálogo sin que
    alguien lo pida explícitamente."""
    return completar_unidades_desde_maestro(db)


@router.post("/mantenimiento/candidatos-matricula/calcular", response_model=ResumenCandidatosMatriculaOut)
def calcular_candidatos_de_matricula(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Bloque 1, sesión 2026-09-11: recalcula la cola de candidatos de
    matrícula (`app.extraccion.candidatos_matricula.calcular_candidatos`)
    contra el estado actual del catálogo y del maestro de materiales --
    nunca asigna nada por sí solo, solo repuebla las opciones que
    `GET /revision/candidatos-matricula` presenta para confirmación humana.
    Síncrono, mismo criterio que el resto de esta sección: se puede volver a
    llamar tantas veces como haga falta (p.ej. tras recargar el maestro, o
    tras un reproceso que cambie qué líneas tienen matrícula) sin duplicar
    nada -- borra y reconstruye la cola entera cada vez."""
    return calcular_candidatos(db)
