"""Presupuestos de licitación por lote leídos de los documentos publicados

Bloque 1, sesión 2026-09-21: el contraste de presupuestos (suma de cantidad ×
precio de cada lote contra su presupuesto publicado) necesita el presupuesto
de cada lote, y el sistema solo lo guardaba en `lotes.importe_licitacion`
cuando lo declara la adjudicación o el Contrato del propio lote. En los
documentos ya descargados está en muchos más sitios (el bloque de cada lote
del anuncio, "Lote N: ..., X € sin IVA" del pliego, el Contrato del lote
hermano). Tabla aparte, y no `lotes.importe_licitacion`, a propósito: ese
campo interviene en la baja, en la prueba del reparto por lotes y en los
precios que un presupuesto demuestra, y rellenarlo cambiaría datos del
catálogo. Esta tabla solo la lee el contraste. Guarda también el
"Presupuesto de Ejecución Material" que declaran los documentos (sin lote:
se liga a un lote solo por la aritmética, en el contraste).

Revision ID: 0042
Revises: 0041
Create Date: 2026-09-21

"""
from alembic import op
import sqlalchemy as sa

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "presupuestos_lote_documento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("expediente_id", sa.Integer(), sa.ForeignKey("expedientes.id"), nullable=False),
        sa.Column("identificador_lote", sa.String(64), nullable=True),
        sa.Column("importe", sa.Numeric(14, 4), nullable=False),
        sa.Column("importe_con_iva", sa.Numeric(14, 4), nullable=True),
        sa.Column("redaccion", sa.String(32), nullable=False),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documentos.id"), nullable=False),
        sa.Column("pagina", sa.Integer(), nullable=True),
        sa.Column("fragmento", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_presupuestos_lote_documento_expediente", "presupuestos_lote_documento", ["expediente_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_presupuestos_lote_documento_expediente", table_name="presupuestos_lote_documento")
    op.drop_table("presupuestos_lote_documento")
