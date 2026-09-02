import enum

from sqlalchemy import (
    BigInteger,
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
    extrayendo = "extrayendo"
    pendiente_revision = "pendiente_revision"
    completado = "completado"
    fallido = "fallido"


class TipoDocumento(str, enum.Enum):
    anuncio_pcsp = "anuncio_pcsp"
    propuesta_lc27 = "propuesta_lc27"
    contrato = "contrato"
    anejo = "anejo"
    pliego = "pliego"
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
    importe_licitacion = Column(Numeric(14, 4), nullable=True)
    importe_adjudicacion = Column(Numeric(14, 4), nullable=True)
    baja_global = Column(Numeric(12, 6), nullable=True)
    estado = Column(
        Enum(EstadoExpediente, name="estado_expediente"),
        nullable=False,
        default=EstadoExpediente.pendiente,
        server_default=EstadoExpediente.pendiente.value,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    lotes = relationship("Lote", back_populates="expediente")
    documentos = relationship("Documento", back_populates="expediente")


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
    lote_id = Column(Integer, ForeignKey("lotes.id"), nullable=False)
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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

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


class TrabajoCola(Base):
    __tablename__ = "trabajos_cola"

    id = Column(BigInteger, primary_key=True)
    tipo = Column(String(64), nullable=False)
    payload = Column(JSONB, nullable=True)
    estado = Column(
        Enum(EstadoTrabajo, name="estado_trabajo"),
        nullable=False,
        default=EstadoTrabajo.pendiente,
        server_default=EstadoTrabajo.pendiente.value,
    )
    intentos = Column(Integer, nullable=False, default=0, server_default="0")
    max_intentos = Column(Integer, nullable=False, default=3, server_default="3")
    expediente_id = Column(Integer, ForeignKey("expedientes.id"), nullable=True)
    resultado = Column(JSONB, nullable=True)
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
