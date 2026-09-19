"""Precio unitario recalculado desde la columna de importes del documento

Bloque 2, sesión 2026-09-19 (decisión del cliente): una línea cuyo precio no
salió literal de su celda del cuadro, sino de dividir el importe del renglón
entre su cantidad -- y solo cuando además el lote suma exactamente un total
declarado por el propio documento. Misma marca que `texto_reconocido`
(migración 0035): `True` o ausente, nunca `False`.

Revision ID: 0039
Revises: 0038
Create Date: 2026-09-19

"""
from alembic import op
import sqlalchemy as sa

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lineas_catalogo", sa.Column("precio_corregido_desde_importe", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("lineas_catalogo", "precio_corregido_desde_importe")
