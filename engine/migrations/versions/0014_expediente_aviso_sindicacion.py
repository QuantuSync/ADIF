"""expedientes: añade aviso_sindicacion

CLAUDE.md sección 26 (regresión de 6.24/28510.0088, el ejemplo central de la
sección 4): el contraste con sindicación mandaba a revisión un expediente
correcto porque comparaba contra una instantánea de otro alcance (la
licitación completa de varios lotes, no el lote concreto que trae el PDF
firmado). El PDF es el acto administrativo, la sindicación es un volcado de
otra fuente sin la misma autoridad -- un desajuste ya no cambia `estado` ni
`error`, se guarda aquí como aviso informativo.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-04

"""
import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expedientes", sa.Column("aviso_sindicacion", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("expedientes", "aviso_sindicacion")
