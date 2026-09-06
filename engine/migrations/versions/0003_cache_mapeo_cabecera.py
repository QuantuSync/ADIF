"""cache_mapeo_cabecera

CONTEXTO.md sección 6: "Una llamada por firma de cabecera, no por documento, no
por página, no por fila [...] Si está, ya sabes qué columna es cada cosa. Si
no, una llamada, guardas el mapeo, y no vuelves a preguntarlo nunca." Esta
tabla es esa memoria persistente.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-02

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cache_mapeo_cabecera",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("firma", sa.String(64), nullable=False, unique=True),
        sa.Column("cabecera", sa.JSON(), nullable=False),
        sa.Column("mapeo", sa.JSON(), nullable=False),
        sa.Column("origen", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("cache_mapeo_cabecera")
