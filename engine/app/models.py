import enum

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db import Base


class EstadoExpediente(str, enum.Enum):
    pendiente = "pendiente"
    descargando = "descargando"
    descargado = "descargado"
    extrayendo = "extrayendo"
    pendiente_revision = "pendiente_revision"
    # Un pedido derivado de acuerdo marco (docs/analisis-corpus.md hallazgo 3)
    # descubrió que necesita su matriz y el sistema ya la está resolviendo
    # solo (creándola, encolando su descarga o su extracción) —
    # app.extraccion.herencia_matriz. Distinto de `pendiente_revision`: ese
    # dice "hace falta un humano", este dice "ya se está resolviendo, todavía
    # no hay nada que revisar".
    esperando_matriz = "esperando_matriz"
    completado = "completado"
    fallido = "fallido"
    # El expediente no existe en la Plataforma (docs/analisis-corpus.md,
    # sesión de expedientes sin publicar): comprobado a mano y confirmado por
    # `app.scraping.pcsp.ExpedienteNoPublicadoError` en todas las variantes de
    # separador de búsqueda. Distinto de `fallido`: ese dice "algo salió mal,
    # puede que reintentando funcione"; este dice "no hay nada que
    # reintentar, el documento no está publicado". Distinto también de
    # `pendiente_revision`: no hace falta un humano, no es trabajo pendiente,
    # es un expediente fuera de alcance del sistema.
    sin_publicar = "sin_publicar"


class TipoDocumento(str, enum.Enum):
    anuncio_pcsp = "anuncio_pcsp"
    propuesta_lc27 = "propuesta_lc27"
    resolucion_adjudicacion = "resolucion_adjudicacion"
    contrato = "contrato"
    anejo = "anejo"
    pliego = "pliego"
    # Tercera plantilla de propuesta (código "L9_CM.32-FE",
    # "INFORME-PROPUESTA DE ADJUDICACIÓN DE CONTRATO"), usada por Dirección
    # Técnica en vez de la Mesa de Contratación (docs/analisis-corpus.md
    # hallazgo 4): mismo tipo de hecho que propuesta_lc27 (declara baja y
    # adjudicatario) pero con anatomía propia, así que es su propio tipo, no
    # un alias forzado.
    propuesta_dt = "propuesta_dt"
    otro = "otro"


class EstadoRevisionLinea(str, enum.Enum):
    sin_revisar = "sin_revisar"
    pendiente = "pendiente"
    confirmado = "confirmado"
    corregido = "corregido"
    descartado = "descartado"


class EstadoTrabajo(str, enum.Enum):
    pendiente = "pendiente"
    en_proceso = "en_proceso"
    completado = "completado"
    fallido = "fallido"


class Expediente(Base):
    __tablename__ = "expedientes"

    id = Column(Integer, primary_key=True)
    codigo_expediente = Column(String(64), nullable=False, unique=True)
    codigo_matriz = Column(String(64), nullable=True)
    nombre_proyecto = Column(String(255), nullable=True)
    # Cruce con el Excel de códigos (CLAUDE.md sección 7, "Cruce con el
    # Excel de códigos"): por clave exacta contra `codigo_expediente` /
    # `codigo_matriz`, nunca por similitud de nombre. `codigos_cruzados` es
    # `None` mientras no se ha intentado el cruce (expedientes procesados
    # antes de que existiera esta columna), `False` si se intentó y no
    # cruzó ninguna fila del Excel (el sistema nunca inventa un código:
    # `codigo_interno` se deja vacío), `True` si cruzó.
    codigo_interno = Column(String(64), nullable=True)
    codigos_cruzados = Column(Boolean, nullable=True)
    importe_licitacion = Column(Numeric(14, 4), nullable=True)
    importe_adjudicacion = Column(Numeric(14, 4), nullable=True)
    baja_global = Column(Numeric(12, 6), nullable=True)
    # True cuando el expediente tiene 2+ lotes con baja declarada distinta
    # entre sí: ahí `baja_global` se deja en NULL a propósito (CLAUDE.md
    # sección 4, "no hay una baja distinta por material dentro de un lote"
    # no dice nada de que todos los lotes de un expediente compartan baja) y
    # este campo es lo que le dice a la web que explique el vacío en vez de
    # dejarlo parecer un fallo de extracción (encargo de esta sesión, punto
    # 4, ajuste 3). None mientras no se sepa (expediente de un solo lote, o
    # todavía sin procesar); False si hay varios lotes pero comparten baja.
    baja_variable_por_lote = Column(Boolean, nullable=True)
    # Relación resuelta con la matriz (app.extraccion.herencia_matriz),
    # distinta de `codigo_matriz` de arriba: ese es el código de texto
    # extraído del Anuncio PCSP o del Excel, que puede no tener fila propia
    # todavía. `matriz_expediente_id` es esa fila real, una vez existe.
    matriz_expediente_id = Column(Integer, ForeignKey("expedientes.id"), nullable=True)
    # True cuando el Anuncio PCSP propio y la columna MATRIZ del Excel de
    # códigos declaran una matriz distinta entre sí: el sistema nunca elige
    # una de las dos en silencio (encargo de la sesión de herencia de
    # acuerdo marco, requisito 1 — "si discrepan, a revisión").
    matriz_conflicto = Column(Boolean, nullable=True)
    estado = Column(
        Enum(EstadoExpediente, name="estado_expediente"),
        nullable=False,
        default=EstadoExpediente.pendiente,
        server_default=EstadoExpediente.pendiente.value,
    )
    # Por qué está en fallido o pendiente_revision, con el mensaje real
    # (CLAUDE.md, encargo de esta sesión, punto 2). `trabajos_cola.error`
    # cubre el fallo de un trabajo concreto; este cubre el motivo a nivel de
    # expediente, incluida la revisión sin que ningún trabajo haya fallado.
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    lotes = relationship("Lote", back_populates="expediente")
    documentos = relationship("Documento", back_populates="expediente")
    # Autorreferencial: la matriz de este expediente, si ya se resolvió
    # (app.extraccion.herencia_matriz.resolver_o_encolar_matriz).
    matriz = relationship("Expediente", remote_side=[id], foreign_keys=[matriz_expediente_id])


class Lote(Base):
    __tablename__ = "lotes"
    __table_args__ = (
        UniqueConstraint("expediente_id", "identificador_lote", name="uq_lote_expediente_identificador"),
    )

    id = Column(Integer, primary_key=True)
    expediente_id = Column(Integer, ForeignKey("expedientes.id"), nullable=False)
    identificador_lote = Column(String(64), nullable=False)
    baja_lote = Column(Numeric(12, 6), nullable=True)
    importe_licitacion = Column(Numeric(14, 4), nullable=True)
    importe_adjudicacion = Column(Numeric(14, 4), nullable=True)
    adjudicatario = Column(String(255), nullable=True)
    numero_contrato = Column(String(64), nullable=True)
    # True cuando `baja_lote` (y los importes, si los trae) vinieron de la
    # matriz de un pedido derivado de acuerdo marco, no de los propios
    # documentos de este expediente (app.extraccion.herencia_matriz). None
    # cuando no aplica.
    baja_heredada_de_matriz = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    expediente = relationship("Expediente", back_populates="lotes")
    lineas_catalogo = relationship("LineaCatalogo", back_populates="lote")


class Documento(Base):
    __tablename__ = "documentos"

    id = Column(Integer, primary_key=True)
    expediente_id = Column(Integer, ForeignKey("expedientes.id"), nullable=False)
    tipo_documento = Column(Enum(TipoDocumento, name="tipo_documento"), nullable=False)
    hash = Column(String(64), nullable=False, unique=True)
    nombre_archivo = Column(String(255), nullable=False)
    ruta_almacenamiento = Column(String(512), nullable=False)
    paginas = Column(Integer, nullable=True)
    procesado_en = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    expediente = relationship("Expediente", back_populates="documentos")


class LineaCatalogo(Base):
    __tablename__ = "lineas_catalogo"
    __table_args__ = (
        UniqueConstraint("lote_id", "clave_linea", name="uq_linea_lote_clave"),
    )

    id = Column(Integer, primary_key=True)
    # `expediente_id` es directo, no derivado de `lote_id` -> `lotes.expediente_id`:
    # una línea huérfana (tabla de precios cuyo lote no se pudo determinar
    # con fiabilidad, CLAUDE.md encargo de esta sesión punto 3) no tiene
    # lote, pero sigue perteneciendo a un expediente concreto y tiene que
    # poder trazarse hasta él.
    expediente_id = Column(Integer, ForeignKey("expedientes.id"), nullable=False)
    # NULL cuando la tabla de origen de esta línea no se pudo asociar a un
    # único lote sin ambigüedad (ver `app.extraccion.lote_tabla`). No existe
    # un lote "SIN_DETERMINAR": mezclar un estado de proceso con la tabla de
    # negocio `lotes` obligaría a toda consulta futura por lote a acordarse
    # de excluirlo. La línea huérfana va a la cola de revisión vía
    # `motivo_revision` y el estado del expediente, no vía un lote falso.
    lote_id = Column(Integer, ForeignKey("lotes.id"), nullable=True)
    clave_linea = Column(String(128), nullable=False)
    orden_aparicion = Column(Integer, nullable=False)
    codigo_precio = Column(String(32), nullable=True)
    matricula = Column(String(9), nullable=True)
    descripcion = Column(Text, nullable=False)
    codigo_material = Column(String(64), nullable=True)
    cantidad = Column(Numeric(14, 3), nullable=True)
    precio_unitario = Column(Numeric(14, 4), nullable=True)
    unidad_medida = Column(String(32), nullable=True)
    baja_lote = Column(Numeric(12, 6), nullable=True)
    precio_adjudicado = Column(Numeric(14, 4), nullable=True)
    codigo_interno = Column(String(64), nullable=True)
    documento_origen_id = Column(Integer, ForeignKey("documentos.id"), nullable=True)
    pagina = Column(Integer, nullable=True)
    fragmento = Column(Text, nullable=True)
    confianza = Column(Numeric(5, 4), nullable=True)
    estado_revision = Column(
        Enum(EstadoRevisionLinea, name="estado_revision_linea"),
        nullable=False,
        default=EstadoRevisionLinea.sin_revisar,
        server_default=EstadoRevisionLinea.sin_revisar.value,
    )
    comentarios = Column(Text, nullable=True)
    # Por qué esta línea no tiene lote asignado (siempre None si `lote_id`
    # no es None). Distinto de `comentarios` (notas humanas, sección 7):
    # esto lo escribe el motor, no una persona.
    motivo_revision = Column(Text, nullable=True)
    # True cuando esta línea se copió del cuadro de precios de la matriz de
    # un pedido derivado de acuerdo marco (app.extraccion.herencia_matriz),
    # no se extrajo de los documentos propios de este expediente.
    # `documento_origen_id`/`pagina`/`fragmento` siguen apuntando al
    # documento real de origen (el de la matriz): la trazabilidad no se
    # pierde por heredar, solo se marca para que se distinga a simple vista.
    heredado_de_matriz = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    expediente = relationship("Expediente")
    lote = relationship("Lote", back_populates="lineas_catalogo")
    documento_origen = relationship("Documento")


class TrazaOrigen(Base):
    __tablename__ = "trazas_origen"

    id = Column(Integer, primary_key=True)
    entidad_tipo = Column(String(32), nullable=False)
    entidad_id = Column(Integer, nullable=False)
    campo = Column(String(64), nullable=False)
    documento_id = Column(Integer, ForeignKey("documentos.id"), nullable=False)
    pagina = Column(Integer, nullable=True)
    fragmento = Column(Text, nullable=True)
    valor_extraido = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MapeoCabeceraCache(Base):
    """Caché de la etapa 5 (CLAUDE.md sección 6): una cabecera de tabla ya
    vista no vuelve a pasar por el mapeo determinista ni por el modelo. La
    firma es un hash estable de la cabecera normalizada (ver
    app.extraccion.firma_cabecera); `mapeo` guarda a qué índice de columna
    corresponde cada campo del esquema (o null si esa tabla no trae ese
    campo). `JSON` genérico (no `JSONB`) a propósito: esta tabla es
    consultable en SQLite para tests sin Postgres levantado, sin perder
    validez en Postgres."""

    __tablename__ = "cache_mapeo_cabecera"

    id = Column(Integer, primary_key=True)
    firma = Column(String(64), nullable=False, unique=True)
    cabecera = Column(JSON, nullable=False)
    mapeo = Column(JSON, nullable=False)
    origen = Column(String(16), nullable=False)  # "determinista" | "modelo"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TrabajoCola(Base):
    __tablename__ = "trabajos_cola"

    # BigInteger con variante Integer en SQLite: sqlite solo autoasigna el
    # id de una PK declarada como INTEGER (su alias del rowid); en Postgres
    # sigue siendo bigint, igual que crea la migración 0001.
    id = Column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    tipo = Column(String(64), nullable=False)
    # JSON genérico con variante JSONB solo en Postgres (mismo tipo de
    # columna real que crea la migración 0001): así esta tabla también se
    # puede crear en SQLite para tests sin Postgres levantado, igual que
    # `MapeoCabeceraCache` — ver su docstring.
    payload = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    estado = Column(
        Enum(EstadoTrabajo, name="estado_trabajo"),
        nullable=False,
        default=EstadoTrabajo.pendiente,
        server_default=EstadoTrabajo.pendiente.value,
    )
    intentos = Column(Integer, nullable=False, default=0, server_default="0")
    max_intentos = Column(Integer, nullable=False, default=3, server_default="3")
    expediente_id = Column(Integer, ForeignKey("expedientes.id"), nullable=True)
    resultado = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    error = Column(Text, nullable=True)
    bloqueado_por = Column(String(128), nullable=True)
    bloqueado_en = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
