"""lineas_catalogo.lote_heredado_de_pagina_anterior: trazabilidad de la
herencia de lote entre páginas de continuación

Sesión de verificación del Excel de 6.599 líneas (2026-09-08,
docs/sesion-2026-09-08-verificacion-excel-6599.md y
docs/sesion-2026-09-08-herencia-lote-continuacion.md): `app.extraccion.
lote_tabla` ahora puede heredar el lote de la tabla anterior cuando la
franja que precede a una tabla no trae NINGÚN rastro de la palabra "LOTE"
(ni siquiera ambiguo). Encargo explícito del cliente al aprobar la
propuesta: "deja constancia en la línea de que su lote es heredado, no
leído... si mañana aparece un documento donde la herencia falla, hay que
poder encontrar todas las afectadas".

`True` solo cuando el lote de esa línea vino de heredarse; `None` en
cualquier otro caso (leído de una cabecera propia, o expediente de un solo
lote donde nunca se ejercita esta etapa) -- mismo convenio que
`heredado_de_matriz`, nunca `False` explícito.

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lineas_catalogo",
        sa.Column("lote_heredado_de_pagina_anterior", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lineas_catalogo", "lote_heredado_de_pagina_anterior")
