"""Presupuesto de licitación del listado de estados de ADIF

Bloque 2, sesión 2026-09-19 (sexta parte): la columna que ADIF tiene que
añadir a su listado de estados. El campo se crea ya, vacío, para que meter el
fichero cuando llegue sea dejarlo en `Ejemplo/Input` y ejecutar un comando.
Dato de contraste: nunca escribe en `expedientes.importe_licitacion`, que sale
de los documentos publicados.

Revision ID: 0041
Revises: 0040
Create Date: 2026-09-19

"""
from alembic import op
import sqlalchemy as sa

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "expedientes", sa.Column("presupuesto_licitacion_adif", sa.Numeric(14, 4), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("expedientes", "presupuesto_licitacion_adif")
