"""lineas_catalogo.unidad_medida_original: una forma única por unidad de medida

Sesión 2026-09-16 (noche), encargo del cliente: la columna de unidad traía 32
valores distintos y varios eran la misma unidad escrita de otra forma ("UD.",
"UN", "UD", "ud", "Ud." -- unidad; "t", "T", "Ton"; "t x km", "Txkm",
"Ton*km"). `unidad_medida` pasa a guardar la forma única
(`app.extraccion.unidad_medida.normalizar_unidad`) y la nueva columna, el
valor tal como venía.

Relleno de lo ya guardado, sin reextraer: `unidad_medida_original` toma el
valor actual y `unidad_medida` su forma única. Se hace valor distinto a valor
con la misma función que usa la extracción (son pocas decenas), para que no
haya dos definiciones de la equivalencia.

Revision ID: 0032
Revises: 0031
Create Date: 2026-09-16

"""
from alembic import op
import sqlalchemy as sa

from app.extraccion.unidad_medida import normalizar_unidad

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lineas_catalogo", sa.Column("unidad_medida_original", sa.String(32), nullable=True))
    conexion = op.get_bind()
    conexion.execute(sa.text(
        "UPDATE lineas_catalogo SET unidad_medida_original = unidad_medida WHERE unidad_medida IS NOT NULL"
    ))
    valores = conexion.execute(sa.text(
        "SELECT DISTINCT unidad_medida FROM lineas_catalogo WHERE unidad_medida IS NOT NULL"
    )).scalars().all()
    for valor in valores:
        forma = normalizar_unidad(valor)
        if forma != valor:
            conexion.execute(
                sa.text("UPDATE lineas_catalogo SET unidad_medida = :forma WHERE unidad_medida = :valor"),
                {"forma": forma, "valor": valor},
            )


def downgrade() -> None:
    op.execute(
        "UPDATE lineas_catalogo SET unidad_medida = unidad_medida_original WHERE unidad_medida_original IS NOT NULL"
    )
    op.drop_column("lineas_catalogo", "unidad_medida_original")
