"""maestro_materiales

Bloque 4, sesión 2026-09-09: ADIF va a facilitar el maestro de materiales de
SAP -- documento de referencia existente, no derivado de pliegos ni
contratos, con matrícula y unidad de medida de cada material. Resolvería los
dos huecos mayores del catálogo (matrícula al 40%, unidad al 73%). Todavía
no lo tenemos: esta migración deja preparada su carga como fuente de entrada
permanente, mismo mecanismo que `estado_contrato_sap` (migración 0019) y
`sap_desglose_lineas` (migración 0024) -- upsert por `matricula` (clave
natural de un material en SAP, 9 dígitos).

`lineas_catalogo.unidad_medida_completada_desde_maestro` (mismo patrón que
`heredado_de_matriz`, migración inicial, y `lote_heredado_de_pagina_anterior`,
migración 0022): `True` únicamente cuando `unidad_medida` se rellenó desde
este maestro y no desde el documento propio del expediente -- sin esto,
`documento_origen_id`/`pagina`/`fragmento` seguirían apuntando al PDF real
pero ese valor concreto ya no vendría de ahí, rompiendo la trazabilidad
exigida (CONTEXTO.md invariante 10) sin que nada lo señalara.

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "maestro_materiales",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("matricula", sa.String(9), nullable=False, unique=True),
        sa.Column("descripcion", sa.String(255), nullable=True),
        sa.Column("unidad_medida", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_maestro_materiales_matricula", "maestro_materiales", ["matricula"], unique=True)

    op.add_column(
        "lineas_catalogo",
        sa.Column("unidad_medida_completada_desde_maestro", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lineas_catalogo", "unidad_medida_completada_desde_maestro")
    op.drop_index("ix_maestro_materiales_matricula", table_name="maestro_materiales")
    op.drop_table("maestro_materiales")
