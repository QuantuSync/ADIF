from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import ModeloPrecio


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
    # Bloque 1, sesión del Excel de ejecución SAP (2026-09-07): estado del
    # CONTRATO frente a ADIF, distinto de `estado` de arriba (estado de
    # PROCESAMIENTO de este sistema) -- ver docstring de
    # `Expediente.estado_contrato_sap`.
    estado_contrato_sap: Optional[str] = None
    estado_contrato_sap_actualizado_en: Optional[datetime] = None
    created_at: datetime


class DocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo_documento: str
    nombre_archivo: str
    paginas: Optional[int] = None
    procesado_en: Optional[datetime] = None


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
