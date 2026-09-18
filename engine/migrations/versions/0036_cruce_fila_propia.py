"""Por cuál de las cuatro claves entró el cruce con el Excel de códigos

Sesión 2026-09-18 (bloque 2, decisión del cliente): `expedientes.
cruce_fila_propia` distingue el cruce que encontró la fila DEL PROPIO
expediente (`codigo_expediente` contra `Nº Expediente`) del que encontró la
de otro (las otras tres claves de `_IndiceCodigosProyecto.buscar`). De esa
fila ajena salía el "Código interno", que es la columna por la que buscan en
almacenes.

Se deja a `NULL` para todos los expedientes ya cruzados: `asegurar_cruce_
codigos` rehace el cruce una sola vez sobre cada uno (el índice del Excel ya
está en memoria) y lo rellena. Esta migración no lee el Excel de códigos --
no es su trabajo, y una migración que dependa de un fichero de entrada
externo no se puede volver a aplicar sobre una base limpia.

Revision ID: 0036
Revises: 0035
Create Date: 2026-09-18

"""
from alembic import op
import sqlalchemy as sa

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expedientes", sa.Column("cruce_fila_propia", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("expedientes", "cruce_fila_propia")
