"""expedientes.codigo_interno, expedientes.codigos_cruzados

CONTEXTO.md sección 7, "Cruce con el Excel de códigos": código interno y
código de proyecto/matriz salen de `Expedientes.xlsx` por clave exacta, nunca
por similitud de nombre, y "el sistema nunca inventa una matriz — si no
cruza, se deja vacío y se marca". `codigo_matriz` ya existe (puede venir del
Anuncio PCSP o de este cruce, el que llegue primero); estas dos columnas
nuevas guardan el resultado del cruce en sí: el código interno encontrado, y
si el cruce se intentó y no encontró fila (para poder marcarlo en vez de
dejarlo indistinguible de "todavía no procesado").

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-02

"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expedientes", sa.Column("codigo_interno", sa.String(64), nullable=True))
    op.add_column("expedientes", sa.Column("codigos_cruzados", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("expedientes", "codigos_cruzados")
    op.drop_column("expedientes", "codigo_interno")
