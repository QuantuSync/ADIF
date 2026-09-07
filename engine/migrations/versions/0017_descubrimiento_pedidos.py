"""descubrimiento inverso matriz -> pedidos

Sesión de descubrimiento inverso: hasta ahora el sistema solo sabía que un
pedido cuelga de una matriz porque el propio pedido lo declara (pedido ->
matriz); nunca había recorrido la dirección contraria (matriz -> pedidos).

- `expedientes.aviso_descubrimiento_pedidos`: por qué no se pudo lanzar la
  búsqueda de pedidos de una matriz (hoy, el único motivo real es "sin
  adjudicatario extraído todavía") -- mismo patrón que
  `aviso_sindicacion` (migración 0014), informativo, nunca bloqueante.
- `candidatos_acuerdo_marco`: caché de qué matriz declara cada candidato ya
  comprobado contra la Plataforma, para no reabrir su ficha en cada ciclo
  (ver docstring de `CandidatoAcuerdoMarco` en app.models).

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-07

"""
import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expedientes", sa.Column("aviso_descubrimiento_pedidos", sa.Text(), nullable=True))
    op.create_table(
        "candidatos_acuerdo_marco",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo_expediente_candidato", sa.String(64), nullable=False, unique=True),
        sa.Column("codigo_matriz_declarado", sa.String(64), nullable=True),
        sa.Column("verificado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("candidatos_acuerdo_marco")
    op.drop_column("expedientes", "aviso_descubrimiento_pedidos")
