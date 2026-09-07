"""cache_codigo_material

CONTEXTO.md sección 6 y bloque 5 de la sesión de vocabulario del código de
material: "Si algún caso no encaja por reglas, ahí sí puede intervenir el
modelo, una vez por término nuevo y cacheado" -- mismo mecanismo que
`cache_mapeo_cabecera` (migración 0003), aplicado al término candidato
(primera palabra con forma de sustantivo de la descripción) en vez de a una
firma de cabecera.

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-07

"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cache_codigo_material",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("termino", sa.String(64), nullable=False, unique=True),
        sa.Column("codigo_material", sa.String(64), nullable=True),
        sa.Column("origen", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("cache_codigo_material")
