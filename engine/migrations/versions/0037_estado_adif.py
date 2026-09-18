"""Estado de contratación según el listado que envía ADIF

Sesión 2026-09-18 (continuación, bloque 1 del encargo): ADIF nos envió el
18/09/2026 un listado de 358 expedientes del departamento 28510 con su estado
de contratación, sacado por ellos de una transacción de SAP. Se guarda en
campos propios, **no** en `estado_contrato_sap`, aunque las dos fuentes sean
exportaciones de SAP y su vocabulario de estados coincida: son dos volcados
distintos, con selecciones distintas de expedientes (212 códigos en común, 155
solo en el anterior, 146 solo en este), y meterlos en el mismo campo haría
imposible decir de cuál de los dos vino cada valor.

`estado_adif_creado_en` es la columna "Fecha de creación" del propio listado
-- un dato de ADIF, no una fecha de este sistema.

Revision ID: 0037
Revises: 0036
Create Date: 2026-09-18

"""
from alembic import op
import sqlalchemy as sa

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expedientes", sa.Column("estado_adif", sa.String(length=64), nullable=True))
    op.add_column("expedientes", sa.Column("estado_adif_creado_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "expedientes",
        sa.Column("estado_adif_actualizado_en", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("expedientes", "estado_adif_actualizado_en")
    op.drop_column("expedientes", "estado_adif_creado_en")
    op.drop_column("expedientes", "estado_adif")
