from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.config import settings
from app.mantenimiento.frescura import sin_publicar_confirmado, sin_publicar_reintento_desde
from app.models import EstadoExpediente, ModeloPrecio


class LoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identificador_lote: str
    baja_lote: Optional[Decimal] = None
    importe_licitacion: Optional[Decimal] = None
    importe_adjudicacion: Optional[Decimal] = None
    adjudicatario: Optional[str] = None
    # True cuando `baja_lote` vino de la matriz de un pedido derivado de
    # acuerdo marco, no de los propios documentos de este expediente
    # (app.extraccion.herencia_matriz).
    baja_heredada_de_matriz: Optional[bool] = None
    # Migración 0016 (sesión de trabajo pendiente real, 2026-09-05, ver
    # docs/identidad-expediente.md sección 28): `indexado_por_pedido` explica
    # por qué `baja_lote` es `None` a propósito, no por fallo -- ese modelo
    # fija la baja en cada pedido futuro contra un Acuerdo Marco, no en la
    # licitación. Sin exponer todavía en la web (mismo pendiente menor que
    # `aviso_sindicacion`, `docs/decisiones-cliente.md` sección 26).
    modelo_precio: ModeloPrecio = ModeloPrecio.fijo
    coeficiente_transformacion: Optional[Decimal] = None


class ExpedientePedidoOut(BaseModel):
    """Resumen ligero de un pedido derivado, para la lista `pedidos` de su
    matriz (ExpedienteOut) -- solo lo que hace falta para presentarlos
    juntos (punto 2 del encargo de descubrimiento inverso: "la matriz con
    sus precios de referencia y sus pedidos con la baja de cada uno"). No es
    un ExpedienteOut completo a propósito: evita anidar `lotes`/`pedidos`
    recursivamente por algo que la web no necesita en esta vista."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo_expediente: str
    nombre_proyecto: Optional[str] = None
    estado: str
    baja_global: Optional[Decimal] = None
    importe_adjudicacion: Optional[Decimal] = None


class ExpedienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo_expediente: str
    codigo_matriz: Optional[str] = None
    nombre_proyecto: Optional[str] = None
    codigo_interno: Optional[str] = None
    codigos_cruzados: Optional[bool] = None
    importe_licitacion: Optional[Decimal] = None
    importe_adjudicacion: Optional[Decimal] = None
    baja_global: Optional[Decimal] = None
    # CONTEXTO.md, encargo de esta sesión, punto 4 (ajuste 3): True cuando hay
    # 2+ lotes con baja distinta entre sí — `baja_global` queda en None a
    # propósito y la web tiene que decir explícitamente "varía por lote", no
    # dejar el campo vacío sin explicación.
    baja_variable_por_lote: Optional[bool] = None
    # True cuando la matriz declarada en el Anuncio PCSP propio y la columna
    # MATRIZ del Excel de códigos no coinciden entre sí (CONTEXTO.md sección 7
    # y app.extraccion.cruce_codigos): el sistema no elige una en silencio.
    matriz_conflicto: Optional[bool] = None
    lotes: list[LoteOut] = []
    estado: str
    error: Optional[str] = None
    # CONTEXTO.md sección 26: desajuste con la instantánea de sindicación,
    # nunca bloqueante (el PDF es el acto administrativo, la sindicación no
    # tiene su misma autoridad) — informativo, distinto de `error`.
    aviso_sindicacion: Optional[str] = None
    # Descubrimiento inverso (sesión de descubrimiento inverso, punto 2 del
    # encargo): los pedidos que ya se sabe que cuelgan de este expediente
    # como acuerdo marco -- vacío en la inmensa mayoría de expedientes, que
    # no son un acuerdo marco de nadie.
    pedidos: list[ExpedientePedidoOut] = []
    # Por qué no se pudo lanzar la búsqueda de pedidos de esta matriz (hoy,
    # solo "sin adjudicatario extraído todavía") -- mismo patrón informativo
    # que `aviso_sindicacion`, nunca bloqueante.
    aviso_descubrimiento_pedidos: Optional[str] = None
    # Bloque 6, sesión de comparación documento-vs-listado interno
    # (`app.ingesta_local`): un documento de la carpeta de ingesta manual
    # declara su propio código distinto del de su carpeta -- no se enlaza
    # sin revisión. Mismo patrón informativo que `aviso_sindicacion`.
    aviso_ingesta_manual: Optional[str] = None
    # Este expediente combina, para el mismo tipo de documento, uno
    # descargado de la Plataforma y uno aportado a mano -- la Plataforma ya
    # gana en la cascada, esto solo señala dónde revisar si el aportado a
    # mano sigue haciendo falta. Mismo patrón informativo que
    # `aviso_sindicacion`.
    aviso_conflicto_documento_manual: Optional[str] = None
    # Bloque 1, sesión del Excel de ejecución SAP (2026-09-07): estado del
    # CONTRATO frente a ADIF, distinto de `estado` de arriba (estado de
    # PROCESAMIENTO de este sistema) -- ver docstring de
    # `Expediente.estado_contrato_sap`.
    estado_contrato_sap: Optional[str] = None
    estado_contrato_sap_actualizado_en: Optional[datetime] = None
    # Bloque 5, sesión 2026-09-19 (quinta parte): "Estado según ADIF", el del
    # listado que ADIF envió el 18/09/2026 (`Expediente.estado_adif`,
    # CONTEXTO.md sección 7). Columna 11 del Excel desde la sesión 2026-09-18
    # y hasta ahora invisible en la web, que era el hueco que la revisión de
    # esta sesión buscaba. **Nunca se mezcla con `estado_contrato_sap` ni con
    # `estado`**: son tres hechos de tres fuentes distintas (dos volcados de
    # SAP distintos y el estado de procesamiento de este sistema).
    estado_adif: Optional[str] = None
    estado_adif_actualizado_en: Optional[datetime] = None
    # Sesión 2026-09-15: un `sin_publicar` ya no es definitivo -- ver
    # `Expediente.sin_publicar_en` y `app.mantenimiento.frescura`.
    sin_publicar_en: Optional[datetime] = None
    sin_publicar_version_busqueda: Optional[str] = None
    created_at: datetime

    @computed_field
    @property
    def sin_publicar_confirmado(self) -> Optional[bool]:
        """`None` si no está `sin_publicar`; si lo está, si el negativo se
        confirmó con la lógica de búsqueda vigente o viene de antes."""
        if self.estado != EstadoExpediente.sin_publicar:
            return None
        return sin_publicar_confirmado(self)

    @computed_field
    @property
    def sin_publicar_reintento_desde(self) -> Optional[datetime]:
        """Desde cuándo lo vuelve a buscar el ciclo de mantenimiento. `None`
        si no está `sin_publicar` o si no consta cuándo se marcó (toca ya)."""
        if self.estado != EstadoExpediente.sin_publicar or self.sin_publicar_en is None:
            return None
        return sin_publicar_reintento_desde(self, timedelta(days=settings.sin_publicar_reintento_dias))


class DocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo_documento: str
    nombre_archivo: str
    paginas: Optional[int] = None
    procesado_en: Optional[datetime] = None
    # Bloque 6, sesión de comparación documento-vs-listado interno:
    # "plataforma" (descargado con navegador, CONTEXTO.md sección 10) o
    # "manual" (aportado por el cliente, `app.ingesta_local`) -- ver
    # docstring de `OrigenDocumento`.
    origen: str = "plataforma"


class LineaCatalogoPosibleDuplicado(BaseModel):
    """Bloque 4, sesión de huérfanos de banda vacía (2026-09-07): señal
    informativa para la cola de revisión, nunca una decisión automática
    (CONTEXTO.md, "un contraste externo puede señalar un desajuste, pero no
    tiene autoridad para cambiar el estado" -- mismo principio aplicado
    aquí). Los datos de la línea YA resuelta con la que coincide una
    huérfana en matrícula/descripción/precio, para comparar de un vistazo
    sin abrir el PDF -- confirmar o descartar sigue siendo una decisión
    humana, con los endpoints de siempre
    (`POST /catalogo/lineas/{id}/confirmar` o `/descartar`)."""

    model_config = ConfigDict(from_attributes=True)

    linea_id: int
    identificador_lote: str
    codigo_precio: Optional[str] = None
    matricula: Optional[str] = None
    descripcion: str
    precio_unitario: Optional[Decimal] = None


class CeldaVaciaOut(BaseModel):
    """Por qué está vacía una celda de datos (`app.celdas_vacias`): los
    mismos códigos que `MotivoVacio` de la web."""

    motivo: str  # "na" | "no-consta" | "pendiente"
    detalle: Optional[str] = None


class LineaCatalogoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # None cuando la tabla de origen no se pudo asociar a un único lote sin
    # ambigüedad (CONTEXTO.md, encargo de esta sesión, punto 3): la línea
    # existe y se puede revisar, pero no cuelga de ningún lote.
    lote_id: Optional[int] = None
    expediente_id: int
    codigo_expediente: str
    codigo_matriz: Optional[str] = None
    nombre_proyecto: Optional[str] = None
    codigo_interno: Optional[str] = None
    codigos_cruzados: Optional[bool] = None
    identificador_lote: Optional[str] = None
    codigo_precio: Optional[str] = None
    matricula: Optional[str] = None
    descripcion: str
    codigo_material: Optional[str] = None
    cantidad: Optional[Decimal] = None
    precio_unitario: Optional[Decimal] = None
    unidad_medida: Optional[str] = None
    baja_lote: Optional[Decimal] = None
    precio_adjudicado: Optional[Decimal] = None
    comentarios: Optional[str] = None
    # Por qué esta línea no tiene lote (siempre None si `lote_id` no es
    # None) — distinto de `comentarios`, que son notas humanas.
    motivo_revision: Optional[str] = None
    # True cuando esta línea se copió del cuadro de precios de la matriz de
    # un pedido derivado de acuerdo marco (app.extraccion.herencia_matriz).
    # `documento_origen_id`/`pagina`/`fragmento` de abajo siguen apuntando al
    # documento real de origen (el de la matriz): la trazabilidad no cambia.
    heredado_de_matriz: Optional[bool] = None
    # Bloque 1, sesión 2026-09-10: `True` cuando `unidad_medida` se rellenó
    # desde `maestro_materiales` (el documento propio no la traía).
    unidad_medida_completada_desde_maestro: Optional[bool] = None
    # La unidad que dice el maestro cuando no coincide con la que ya tiene
    # la línea (del documento real) -- `unidad_medida` nunca se pisa, esto
    # solo señala la discrepancia para revisión.
    unidad_medida_discrepancia_maestro: Optional[str] = None
    # Sesión 2026-09-16 (noche): la unidad tal como venía en el documento (o
    # en el maestro); `unidad_medida` es su forma única.
    unidad_medida_original: Optional[str] = None
    # Bloque 1, sesión 2026-09-11: `True` cuando la matrícula se aceptó
    # desde la cola de candidatos (`GET /revision/candidatos-matricula`),
    # no se extrajo del documento -- distinción explícita pedida en el
    # encargo de este bloque.
    matricula_confirmada_manualmente: Optional[bool] = None
    estado_revision: str
    # Trazabilidad (CONTEXTO.md sección 9.10 y encargo de esta sesión, punto 2):
    # de qué documento, página y fragmento salió esta línea.
    documento_origen_id: Optional[int] = None
    documento_origen_nombre: Optional[str] = None
    pagina: Optional[int] = None
    fragmento: Optional[str] = None
    # Bloque 4 (2026-09-07): solo se calcula para huérfanas (`lote_id is
    # None`) que coinciden en matrícula/descripción/precio con una línea ya
    # resuelta del mismo expediente -- `None` en cualquier otro caso,
    # incluida una huérfana sin ninguna coincidencia real.
    posible_duplicado_de: Optional[LineaCatalogoPosibleDuplicado] = None
    # Campo de datos vacío -> su motivo (sesión 2026-09-14, continuación).
    celdas_vacias: dict[str, CeldaVaciaOut] = {}


class CatalogoRespuesta(BaseModel):
    total: int
    pagina: int
    tamano_pagina: int
    lineas: list[LineaCatalogoOut]


class ColaRevisionRespuesta(BaseModel):
    """Paginación de `GET /revision` (sesión de paginación de la cola de
    revisión, 2026-09-08): antes devolvía siempre TODOS los
    `pendiente_revision` de golpe -- con el corpus de 45-52 expedientes no
    se notaba, pero con 303 casos reales eran 400 KB por respuesta,
    sondeados cada 3 segundos por la web. Misma forma que `CatalogoRespuesta`,
    para que el cliente pagine igual en las dos pantallas."""

    total: int
    pagina: int
    tamano_pagina: int
    expedientes: list[ExpedienteOut]


class CandidatoMatriculaOut(BaseModel):
    """Bloque 1, sesión 2026-09-11: una opción de matrícula para una línea
    sin ella, con su denominación en el maestro de SAP al lado de la
    descripción del pliego para comparar de un vistazo. `exacto` destaca la
    coincidencia de texto perfecta, pero sigue sin ser una decisión --
    2.388 denominaciones del maestro (8,3%) identifican más de una
    matrícula (análisis de la sesión del maestro de materiales, 2026-09-10),
    así que ni un `exacto=True` basta por sí solo."""

    model_config = ConfigDict(from_attributes=True)

    matricula_candidata: str
    denominacion_maestro: Optional[str] = None
    similitud: Decimal
    exacto: bool


class LineaCandidatosMatriculaOut(BaseModel):
    """Una línea de catálogo sin matrícula, con sus candidatos ordenados por
    confianza (exactos primero, luego por similitud descendente) -- la
    descripción del pliego (`descripcion`) va al lado de cada
    `denominacion_maestro` para que la comparación no exija abrir nada
    más."""

    model_config = ConfigDict(from_attributes=True)

    linea_id: int
    expediente_id: int
    codigo_expediente: str
    identificador_lote: Optional[str] = None
    codigo_precio: Optional[str] = None
    descripcion: str
    candidatos: list[CandidatoMatriculaOut]


class ColaCandidatosMatriculaRespuesta(BaseModel):
    total: int
    pagina: int
    tamano_pagina: int
    lineas: list[LineaCandidatosMatriculaOut]


class CandidatoMatriculaAceptar(BaseModel):
    # La propia matrícula candidata, no un índice de lista: evita aceptar el
    # candidato equivocado si la cola se recalculó entre que se cargó la
    # pantalla y se pulsó "aceptar" (CONTEXTO.md: el sistema nunca inventa
    # una matrícula, así que tampoco debe asignar una que ya no está entre
    # las opciones vigentes de esta línea).
    matricula_candidata: str = Field(min_length=1)


class ResumenCandidatosMatriculaOut(BaseModel):
    lineas_sin_matricula: int
    lineas_con_candidato: int
    lineas_sin_candidato: int
    candidatos_generados: int


class LineaCatalogoCorreccion(BaseModel):
    matricula: Optional[str] = None
    descripcion: Optional[str] = None
    codigo_material: Optional[str] = None
    cantidad: Optional[Decimal] = None
    precio_unitario: Optional[Decimal] = None
    unidad_medida: Optional[str] = None
    comentarios: Optional[str] = None


class LineaCatalogoDescartar(BaseModel):
    # CONTEXTO.md bloque 2 ("descartar la línea con motivo"): el motivo es
    # obligatorio -- una línea que sale del catálogo entregado al cliente
    # (`app.exportacion.generar_excel_catalogo`) sin dejar dicho por qué no
    # se puede auditar después.
    motivo: str = Field(min_length=1)


class LineaCatalogoPendiente(BaseModel):
    # CONTEXTO.md bloque 2 ("dejarla pendiente con una nota"): igual que el
    # motivo de descarte, la nota es obligatoria -- es el único rastro de
    # por qué esta línea se dejó para consultar con otra persona en vez de
    # confirmarse o corregirse ya.
    nota: str = Field(min_length=1)


class ExpedienteCorreccion(BaseModel):
    importe_licitacion: Optional[Decimal] = None
    importe_adjudicacion: Optional[Decimal] = None
    baja_global: Optional[Decimal] = None
    codigo_matriz: Optional[str] = None
    codigo_interno: Optional[str] = None


class ExpedienteRevisionOut(BaseModel):
    expediente: ExpedienteOut
    documentos: list[DocumentoOut]
    lineas: list[LineaCatalogoOut]


class ExpedienteCreate(BaseModel):
    codigo_expediente: str
    codigo_matriz: Optional[str] = None


class EstadoSapCargaOut(BaseModel):
    """Resumen de `POST /mantenimiento/estado-sap/cargar` (bloque 1, sesión
    del Excel de ejecución SAP): `configurado=False` significa que
    `ESTADO_SAP_PATH` no tiene ninguna ruta montada -- no es un error, es la
    misma configuración vacía por defecto que `codigos_proyecto_path`."""

    configurado: bool
    filas_leidas: int = 0
    filas_sin_codigo: int = 0
    expedientes_nuevos: int = 0
    expedientes_actualizados: int = 0
    expedientes_sin_cambios: int = 0


class EstadosAdifCargaOut(BaseModel):
    """Resumen de `POST /mantenimiento/estados-adif/cargar` (bloque 1, sesión
    2026-09-18 continuación): mismo criterio que `EstadoSapCargaOut` --
    `configurado=False` significa que `ESTADOS_ADIF_PATH` no tiene ninguna
    ruta montada. No hay `expedientes_nuevos` a propósito: esta carga **no da
    de alta ningún expediente** (ver docstring de `app.extraccion.estados_adif`),
    los códigos que no casan salen en `codigos_sin_expediente`."""

    configurado: bool
    filas_leidas: int = 0
    filas_sin_codigo: int = 0
    codigos_distintos: int = 0
    expedientes_actualizados: int = 0
    expedientes_sin_cambios: int = 0
    sin_expediente_en_el_sistema: int = 0
    codigos_sin_expediente: list[str] = []
    # Bloque 2, sesión 2026-09-19 (sexta parte): si el listado llegó con la
    # columna de presupuesto de licitación y cuántas filas la traían. Hoy es
    # siempre `False`/`0`: el fichero que tenemos no la trae.
    trae_presupuesto: bool = False
    presupuestos_leidos: int = 0


class VigentesRemanenteCruceOut(BaseModel):
    """Resumen de `POST /mantenimiento/vigentes-remanente/cruzar` (bloque 2,
    sesión 2026-09-19 sexta parte). `configurado=False` significa que
    `VIGENTES_REMANENTE_PATH` no tiene ninguna ruta montada;
    `formato_reconocido=False`, que el fichero está pero no se ha podido
    localizar en él ninguna columna de códigos de expediente -- y entonces no
    se toca nada."""

    configurado: bool
    formato_reconocido: bool = False
    columna_localizada_por: str = "no encontrada"
    hoja: Optional[str] = None
    filas_leidas: int = 0
    codigos_distintos: int = 0
    en_la_conciliacion: int = 0
    fuera_de_la_conciliacion: int = 0
    dados_de_alta: int = 0
    busquedas_encoladas: int = 0
    por_situacion: dict[str, int] = {}
    filas: list[dict] = []


class CatalogoAntiguoResumenOut(BaseModel):
    """Resumen de `GET /mantenimiento/catalogo-antiguo/resumen` (bloque 2,
    misma sesión). El informe en sí es un `.xlsx` aparte, nunca parte del
    entregable."""

    configurado: bool
    formato_reconocido: bool = False
    hojas_leidas: list[str] = []
    columnas: dict[str, Optional[int]] = {}
    materiales_suyos: int = 0
    materiales_nuestros: int = 0
    emparejados_por_matricula: int = 0
    emparejados_por_descripcion: int = 0
    solo_en_el_suyo: int = 0
    solo_en_el_nuestro: int = 0
    con_precio_distinto: int = 0


class SapDesglosecargaOut(BaseModel):
    """Resumen de `POST /mantenimiento/sap-desglose/cargar` (bloque 6,
    cambios del cliente tras revisar el catálogo): mismo criterio que
    `EstadoSapCargaOut` -- `configurado=False` significa que
    `SAP_DESGLOSE_PATH` no tiene ninguna ruta montada."""

    configurado: bool
    filas_leidas: int = 0
    filas_sin_clave: int = 0
    lineas_nuevas: int = 0
    lineas_actualizadas: int = 0
    lineas_sin_cambios: int = 0


class MaestroMaterialesCargaOut(BaseModel):
    """Resumen de `POST /mantenimiento/maestro-materiales/cargar` (bloque 4,
    sesión 2026-09-09): mismo criterio que `SapDesglosecargaOut` --
    `configurado=False` significa que `MAESTRO_MATERIALES_PATH` no tiene
    ninguna ruta montada (el cliente todavía no lo ha facilitado)."""

    configurado: bool
    filas_leidas: int = 0
    filas_sin_matricula: int = 0
    materiales_nuevos: int = 0
    materiales_actualizados: int = 0
    materiales_sin_cambios: int = 0


class MaestroMaterialesCompletarOut(BaseModel):
    """Resumen de `POST /mantenimiento/maestro-materiales/completar-unidades`
    (bloque 4, sesión 2026-09-09): solo actúa sobre líneas que ya tienen
    matrícula y no tienen unidad de medida -- nunca pisa un valor ya
    extraído de un documento real."""

    lineas_evaluadas: int = 0
    lineas_completadas: int = 0
    sin_matricula_en_maestro: int = 0
    discrepancias_detectadas: int = 0


class TrabajoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    estado: str
    intentos: int
    max_intentos: int
    expediente_id: Optional[int] = None
    payload: Optional[dict] = None
    resultado: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class EstadoMantenimientoOut(BaseModel):
    ultima_ejecucion: Optional[TrabajoOut] = None
    en_curso: bool
    proxima_ejecucion: datetime
    intervalo_segundos: float
    programado_activo: bool


# Bloque 5, sesión 2026-09-19 (quinta parte): la hoja "Conciliación" servida a
# la web (`app.routers.conciliacion`). Un espejo exacto de
# `app.conciliacion.FilaConciliacion` -- ni un campo calculado aquí, ni un
# nombre distinto del que lleva la columna del Excel.
class FilaConciliacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo_expediente: str
    titulo: Optional[str] = None
    organo_contratacion: Optional[str] = None
    estado_plataforma: Optional[str] = None
    estado_adif: Optional[str] = None
    documentos_descargados: int
    documentos_reconocimiento_optico: int
    lineas_en_catalogo: int
    baja: str
    situacion: str
    motivo: str


class RecuentoSituacionOut(BaseModel):
    situacion: str
    expedientes: int


class RegistroPublicadoOut(BaseModel):
    """De qué fecha es el registro de lo publicado y qué cubre -- el mismo
    texto que el Resumen del Excel, para que la web no dé una cifra sin decir
    de cuándo es."""

    model_config = ConfigDict(from_attributes=True)

    departamentos: list[str] = []
    periodos_sindicacion: list[str] = []
    sindicacion_actualizado_hasta: Optional[datetime] = None
    busqueda_ejecutada_en: Optional[datetime] = None
    busqueda_fragmentos: list[str] = []
    busqueda_codigos_encontrados: Optional[int] = None
    expedientes_publicados: int = 0
    expedientes_no_publicados: int = 0
    expedientes_en_ficha_de_otro: int = 0


class ConciliacionOut(BaseModel):
    total: int
    total_lineas: int
    situaciones: list[RecuentoSituacionOut]
    filas: list[FilaConciliacionOut]
    registro: RegistroPublicadoOut


# Bloque 1, sesión 2026-09-21: la hoja "Contraste de presupuestos" del Excel,
# campo a campo (`app.contraste_presupuestos.FilaContraste`), con el mismo
# nombre que su columna.
class FilaContrasteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo_expediente: str
    lote: str
    presupuesto_publicado: Decimal
    tipo_cifra: str
    cifra_comparada: Decimal
    documento: Optional[str] = None
    pagina: Optional[int] = None
    suma_lineas: Decimal
    diferencia: Decimal
    diferencia_relativa: Optional[Decimal] = None
    lineas: int
    lineas_sin_cantidad: int
    resultado: str
    explicacion: str


class RecuentoContrasteOut(BaseModel):
    resultado: str
    lotes: int


class LoteFueraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo_expediente: str
    lote: str
    lineas: int
    motivo: str


class RecuentoFueraOut(BaseModel):
    motivo: str
    lotes: int


class ContrasteOut(BaseModel):
    total: int
    resultados: list[RecuentoContrasteOut]
    filas: list[FilaContrasteOut]
    fuera_total: int
    fuera: list[RecuentoFueraOut]
    lotes_fuera: list[LoteFueraOut]
