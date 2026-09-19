"""Descripción del material tomada de la referencia del documento

Bloque 1, decisión 5 del cliente (sesión 2026-09-19, sexta parte): la línea
sale de un cuadro cuya única columna de texto es la referencia del artículo
("SFT01-2388L-PH-6920"), aceptada como Descripción del material. Misma marca
que `texto_reconocido` (migración 0035) y `precio_corregido_desde_importe`
(0039): `True` o ausente, nunca `False`.

Revision ID: 0040
Revises: 0039
Create Date: 2026-09-19

"""
from alembic import op
import sqlalchemy as sa

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lineas_catalogo", sa.Column("descripcion_desde_referencia", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("lineas_catalogo", "descripcion_desde_referencia")
