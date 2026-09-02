"""expedientes.error

CLAUDE.md, encargo de esta sesión, punto 2: "si falla, guardar por qué, con
el mensaje real, no un genérico". `trabajos_cola.error` ya guarda el motivo
de fallo de cada trabajo, pero un expediente puede acabar en
`pendiente_revision` sin que ningún trabajo haya fallado (p.ej. faltan
importes para calcular la baja) — ese motivo también tiene que quedar
anclado al expediente, no solo en el log del worker.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-02

"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expedientes", sa.Column("error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("expedientes", "error")
