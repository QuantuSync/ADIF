"""Listado de expedientes en ejecución de ADIF, con la fecha de firma del acta de inicio

Bloque 2, sesión 2026-09-21. Listado interno de ADIF (no sale de la
Plataforma), compartido en el grupo de trabajo el 18/09/2026 y reenviado
ordenado el 21/09/2026. Tres campos propios del expediente: si figura en el
último listado cargado, su fecha de firma del acta de inicio y el fichero del
que sale. No decide si un expediente consta publicado.

Revision ID: 0043
Revises: 0042
Create Date: 2026-09-21

"""
from alembic import op
import sqlalchemy as sa

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expedientes", sa.Column("en_ejecucion_adif", sa.Boolean(), nullable=True))
    op.add_column("expedientes", sa.Column("acta_inicio_adif", sa.Date(), nullable=True))
    op.add_column("expedientes", sa.Column("en_ejecucion_adif_listado", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("expedientes", "en_ejecucion_adif_listado")
    op.drop_column("expedientes", "acta_inicio_adif")
    op.drop_column("expedientes", "en_ejecucion_adif")
