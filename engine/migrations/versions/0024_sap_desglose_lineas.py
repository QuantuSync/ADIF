"""sap_desglose_lineas

Bloque 6, cambios del cliente tras revisar el catálogo: ADIF ha facilitado
un desglose exportado de SAP con las matrículas concretas de cada contrato
-- justo lo que los pliegos no traen. Fuente de entrada permanente, mismo
mecanismo que `estado_contrato_sap` (migración 0019)/`codigo_matriz_en_cruce`
(migración 0023): un dato de negocio que no existe en ningún documento de la
Plataforma, cargado desde un fichero externo (`app.extraccion.sap_desglose`),
repetible sin duplicar (upsert por `documento_compras` + `posicion`, la
clave natural de una línea de pedido de compras real en SAP).

`codigo_expediente` se guarda como texto, no como FK a `expedientes.id`:
el cruce es "por número de expediente por clave exacta" (encargo de esta
sesión), no una relación estructural -- una línea de SAP de un expediente
que este sistema no conoce todavía (o que nunca llega a procesar) sigue
siendo un dato válido que conservar, igual que `expedientes.codigo_matriz`
tampoco es FK.

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sap_desglose_lineas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo_expediente", sa.String(64), nullable=False),
        sa.Column("documento_compras", sa.String(32), nullable=False),
        sa.Column("posicion", sa.String(16), nullable=False),
        sa.Column("material", sa.String(64), nullable=True),
        sa.Column("texto_breve", sa.String(255), nullable=True),
        sa.Column("cantidad_prevista", sa.Numeric(14, 3), nullable=True),
        sa.Column("precio_neto", sa.Numeric(14, 4), nullable=True),
        sa.Column("unidad_medida", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("documento_compras", "posicion", name="uq_sap_desglose_documento_posicion"),
    )
    op.create_index(
        "ix_sap_desglose_lineas_codigo_expediente", "sap_desglose_lineas", ["codigo_expediente"]
    )
    op.create_index("ix_sap_desglose_lineas_material", "sap_desglose_lineas", ["material"])


def downgrade() -> None:
    op.drop_index("ix_sap_desglose_lineas_material", table_name="sap_desglose_lineas")
    op.drop_index("ix_sap_desglose_lineas_codigo_expediente", table_name="sap_desglose_lineas")
    op.drop_table("sap_desglose_lineas")
