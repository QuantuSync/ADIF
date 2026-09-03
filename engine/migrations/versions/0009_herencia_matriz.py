"""Herencia de acuerdo marco: matriz_expediente_id, matriz_conflicto,
baja_heredada_de_matriz, heredado_de_matriz, estado esperando_matriz

Pedidos derivados de acuerdo marco (docs/analisis-corpus.md hallazgo 3, 14
expedientes): su cuadro de precios y su baja no están en sus propios
documentos, viven en la matriz. `matriz_expediente_id` es la relación
resuelta (distinta del `codigo_matriz` de texto que ya existía: ese es un
código extraído del Anuncio PCSP o del Excel, este es la fila real de
`expedientes`, si y cuando existe). `esperando_matriz` es el estado mientras
el sistema resuelve la matriz solo (crearla, encolar su descarga o su
extracción) — distinto de `pendiente_revision`, que significa que hace falta
un humano.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-03

"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No se puede usar el valor nuevo en la misma transacción en la que se
    # añade (restricción de Postgres para ALTER TYPE ... ADD VALUE) — igual
    # que la migración 0008, esta migración solo lo añade, no lo usa.
    op.execute("ALTER TYPE estado_expediente ADD VALUE IF NOT EXISTS 'esperando_matriz' AFTER 'pendiente_revision'")

    op.add_column("expedientes", sa.Column("matriz_expediente_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_expedientes_matriz_expediente_id", "expedientes", "expedientes", ["matriz_expediente_id"], ["id"]
    )
    op.add_column("expedientes", sa.Column("matriz_conflicto", sa.Boolean(), nullable=True))

    op.add_column("lotes", sa.Column("baja_heredada_de_matriz", sa.Boolean(), nullable=True))

    op.add_column("lineas_catalogo", sa.Column("heredado_de_matriz", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("lineas_catalogo", "heredado_de_matriz")
    op.drop_column("lotes", "baja_heredada_de_matriz")
    op.drop_constraint("fk_expedientes_matriz_expediente_id", "expedientes", type_="foreignkey")
    op.drop_column("expedientes", "matriz_conflicto")
    op.drop_column("expedientes", "matriz_expediente_id")
    # Postgres no soporta quitar un valor de un enum: 'esperando_matriz' se
    # queda en el tipo aunque se revierta el resto (mismo criterio que 0008).
