"""sindicacion_expedientes: bloque 2, descubrimiento por sindicación

CONTEXTO.md sección 24: instantánea más reciente de cada expediente conocida
por el XML CODICE de sindicación, guardada aparte de `expedientes`/`lotes`
para poder contrastarla contra lo que extrae la cascada de los PDFs sin que
una fuente pise a la otra.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sindicacion_expedientes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo_expediente", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expediente_id", sa.Integer(), sa.ForeignKey("expedientes.id"), nullable=True),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estado_pcsp", sa.String(length=16), nullable=True),
        sa.Column("organo_contratacion", sa.String(length=255), nullable=True),
        sa.Column("titulo", sa.Text(), nullable=True),
        sa.Column("importe_licitacion_sin_impuestos", sa.Numeric(14, 4), nullable=True),
        sa.Column("importe_licitacion_con_impuestos", sa.Numeric(14, 4), nullable=True),
        sa.Column("importe_adjudicacion_sin_impuestos", sa.Numeric(14, 4), nullable=True),
        sa.Column("importe_adjudicacion_con_impuestos", sa.Numeric(14, 4), nullable=True),
        sa.Column("adjudicatario", sa.String(length=255), nullable=True),
        sa.Column("lotes", postgresql.JSONB(), nullable=True),
        sa.Column("periodo_zip", sa.String(length=6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("sindicacion_expedientes")
