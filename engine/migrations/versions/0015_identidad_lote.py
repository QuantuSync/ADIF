"""lotes/expedientes: identidad propia del lote y cobertura declarada

CLAUDE.md sección 27 (sesión de identidad de lote): en una licitación
multi-lote, cada lote adjudicado tiene su propio código de expediente en la
Plataforma (verificado idéntico al "Contrato nº" de su Contrato firmado),
distinto del expediente principal bajo el que están archivados los
documentos. `lotes.numero_contrato` existía desde la migración 0001 pero
nunca se poblaba -- se renombra a `codigo_expediente_lote` porque el dato
casi siempre se conoce antes, por la Propuesta/Resolución, no solo por el
Contrato.

`expedientes.lotes_totales_declarados` guarda cuántos lotes declara la
licitación en total, para poder detectar cuando solo se conocen algunos
(cobertura parcial) -- nunca se genera una secuencia 1..N a partir de este
número, la numeración real puede tener huecos (lotes desiertos/anulados).

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-04

"""
import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("lotes", "numero_contrato", new_column_name="codigo_expediente_lote")
    op.add_column("expedientes", sa.Column("lotes_totales_declarados", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("expedientes", "lotes_totales_declarados")
    op.alter_column("lotes", "codigo_expediente_lote", new_column_name="numero_contrato")
