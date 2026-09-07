"""estado_contrato_sap

Bloque 1, sesión del Excel de ejecución SAP (2026-09-07): estado del
CONTRATO frente a ADIF ("En ejecución", ...), leído de la exportación SAP de
ADIF (`app.extraccion.estado_sap`) -- distinto de `estado` (estado de
PROCESAMIENTO de este sistema), que la migración 0001 ya crea. Dato de
negocio que no existe en ningún documento de la Plataforma; el sistema no
puede deducirlo solo.

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-07

"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expedientes", sa.Column("estado_contrato_sap", sa.String(64), nullable=True))
    op.add_column(
        "expedientes",
        sa.Column("estado_contrato_sap_actualizado_en", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("expedientes", "estado_contrato_sap_actualizado_en")
    op.drop_column("expedientes", "estado_contrato_sap")
