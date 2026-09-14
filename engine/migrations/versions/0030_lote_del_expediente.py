"""lineas_catalogo.lote_del_expediente: trazabilidad del lote atribuido por
ser el del propio expediente

Sesión 2026-09-14, tercera parte (decisión del cliente): en un expediente
que es uno de los lotes de una licitación y sabe cuál (su Contrato o la
adjudicación ligan su número a su código), una tabla que no declara lote se
le atribuye -- salvo el anejo de criterios técnicos del conjunto de los
lotes (`app.extraccion.pipeline_anejo`, `lote_propio`). Como con la herencia
entre páginas (migración 0022), la línea deja constancia de que su lote no
se leyó en una cabecera, para poder encontrar todas las afectadas.

`True` solo en ese caso; `None` en cualquier otro -- mismo convenio que
`lote_heredado_de_pagina_anterior`, nunca `False` explícito.

Revision ID: 0030
Revises: 0029
Create Date: 2026-09-14

"""
from alembic import op
import sqlalchemy as sa

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lineas_catalogo", sa.Column("lote_del_expediente", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("lineas_catalogo", "lote_del_expediente")
