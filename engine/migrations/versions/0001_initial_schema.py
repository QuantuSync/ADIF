"""esquema inicial

Revision ID: 0001
Revises:
Create Date: 2026-09-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


# create_type=False: el tipo se crea/destruye explícitamente en upgrade()/downgrade().
# Si no, SQLAlchemy intenta crearlo otra vez al usarlo como tipo de columna en
# create_table y choca con el que ya existe (DuplicateObject).
estado_expediente = postgresql.ENUM(
    "pendiente", "descargando", "extrayendo", "pendiente_revision", "completado", "fallido",
    name="estado_expediente",
    create_type=False,
)
tipo_documento = postgresql.ENUM(
    "anuncio_pcsp", "propuesta_lc27", "contrato", "anejo", "pliego", "otro",
    name="tipo_documento",
    create_type=False,
)
estado_revision_linea = postgresql.ENUM(
    "sin_revisar", "pendiente", "confirmado", "corregido", "descartado",
    name="estado_revision_linea",
    create_type=False,
)
estado_trabajo = postgresql.ENUM(
    "pendiente", "en_proceso", "completado", "fallido",
    name="estado_trabajo",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    estado_expediente.create(bind, checkfirst=True)
    tipo_documento.create(bind, checkfirst=True)
    estado_revision_linea.create(bind, checkfirst=True)
    estado_trabajo.create(bind, checkfirst=True)

    op.create_table(
        "expedientes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo_expediente", sa.String(64), nullable=False, unique=True),
        sa.Column("codigo_matriz", sa.String(64), nullable=True),
        sa.Column("nombre_proyecto", sa.String(255), nullable=True),
        sa.Column("importe_licitacion", sa.Numeric(14, 4), nullable=True),
        sa.Column("importe_adjudicacion", sa.Numeric(14, 4), nullable=True),
        sa.Column("baja_global", sa.Numeric(12, 6), nullable=True),
        sa.Column("estado", estado_expediente, nullable=False, server_default="pendiente"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "lotes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("expediente_id", sa.Integer(), sa.ForeignKey("expedientes.id"), nullable=False),
        sa.Column("identificador_lote", sa.String(64), nullable=False),
        sa.Column("baja_lote", sa.Numeric(12, 6), nullable=True),
        sa.Column("importe_licitacion", sa.Numeric(14, 4), nullable=True),
        sa.Column("importe_adjudicacion", sa.Numeric(14, 4), nullable=True),
        sa.Column("adjudicatario", sa.String(255), nullable=True),
        sa.Column("numero_contrato", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("expediente_id", "identificador_lote", name="uq_lote_expediente_identificador"),
    )

    op.create_table(
        "documentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("expediente_id", sa.Integer(), sa.ForeignKey("expedientes.id"), nullable=False),
        sa.Column("tipo_documento", tipo_documento, nullable=False),
        sa.Column("hash", sa.String(64), nullable=False, unique=True),
        sa.Column("nombre_archivo", sa.String(255), nullable=False),
        sa.Column("ruta_almacenamiento", sa.String(512), nullable=False),
        sa.Column("paginas", sa.Integer(), nullable=True),
        sa.Column("procesado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "lineas_catalogo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lote_id", sa.Integer(), sa.ForeignKey("lotes.id"), nullable=False),
        sa.Column("clave_linea", sa.String(128), nullable=False),
        sa.Column("orden_aparicion", sa.Integer(), nullable=False),
        sa.Column("codigo_precio", sa.String(32), nullable=True),
        sa.Column("matricula", sa.String(9), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("codigo_material", sa.String(64), nullable=True),
        sa.Column("cantidad", sa.Numeric(14, 3), nullable=True),
        sa.Column("precio_unitario", sa.Numeric(14, 4), nullable=True),
        sa.Column("unidad_medida", sa.String(32), nullable=True),
        sa.Column("baja_lote", sa.Numeric(12, 6), nullable=True),
        sa.Column("precio_adjudicado", sa.Numeric(14, 4), nullable=True),
        sa.Column("codigo_interno", sa.String(64), nullable=True),
        sa.Column("documento_origen_id", sa.Integer(), sa.ForeignKey("documentos.id"), nullable=True),
        sa.Column("pagina", sa.Integer(), nullable=True),
        sa.Column("fragmento", sa.Text(), nullable=True),
        sa.Column("confianza", sa.Numeric(5, 4), nullable=True),
        sa.Column("estado_revision", estado_revision_linea, nullable=False, server_default="sin_revisar"),
        sa.Column("comentarios", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("lote_id", "clave_linea", name="uq_linea_lote_clave"),
    )

    op.create_table(
        "trazas_origen",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entidad_tipo", sa.String(32), nullable=False),
        sa.Column("entidad_id", sa.Integer(), nullable=False),
        sa.Column("campo", sa.String(64), nullable=False),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documentos.id"), nullable=False),
        sa.Column("pagina", sa.Integer(), nullable=True),
        sa.Column("fragmento", sa.Text(), nullable=True),
        sa.Column("valor_extraido", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "trabajos_cola",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("tipo", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("estado", estado_trabajo, nullable=False, server_default="pendiente"),
        sa.Column("intentos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_intentos", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("expediente_id", sa.Integer(), sa.ForeignKey("expedientes.id"), nullable=True),
        sa.Column("resultado", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("bloqueado_por", sa.String(128), nullable=True),
        sa.Column("bloqueado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_index("ix_trabajos_cola_estado_created_at", "trabajos_cola", ["estado", "created_at"])


def downgrade() -> None:
    op.drop_table("trabajos_cola")
    op.drop_table("trazas_origen")
    op.drop_table("lineas_catalogo")
    op.drop_table("documentos")
    op.drop_table("lotes")
    op.drop_table("expedientes")

    bind = op.get_bind()
    estado_trabajo.drop(bind, checkfirst=True)
    estado_revision_linea.drop(bind, checkfirst=True)
    tipo_documento.drop(bind, checkfirst=True)
    estado_expediente.drop(bind, checkfirst=True)
