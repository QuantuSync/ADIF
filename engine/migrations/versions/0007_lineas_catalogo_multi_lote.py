"""lineas_catalogo.expediente_id, lineas_catalogo.lote_id nullable,
lineas_catalogo.motivo_revision, expedientes.baja_variable_por_lote

Extracción por lote (CONTEXTO.md secciones 2 y 4, y encargo de esta sesión):
un expediente multi-lote (p.ej. 6.25/28510.0027, LOTE 1 al 7,13% y LOTE 3 al
1,18%) tiene una baja distinta por lote, y hay que poder guardar una línea
del cuadro de precios sin saber todavía a qué lote pertenece (cuando la
banda vertical que precede a su tabla no trae una única cabecera "LOTE N" —
ver `app.extraccion.lote_tabla`), en vez de forzarla a un lote que no le
corresponde o inventar un lote "SIN_DETERMINAR" que contaminaría `lotes`
(tabla de negocio) con un estado de proceso.

`lote_id` pasa a admitir NULL para esas líneas huérfanas; `expediente_id` se
añade directamente porque, sin lote, ya no hay camino de join hasta
`expedientes` (antes bastaba `lineas_catalogo -> lotes -> expedientes`).
`motivo_revision` guarda por qué esa línea concreta no tiene lote —
distinto de `comentarios`, que es para notas humanas (CONTEXTO.md sección 7).

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-02

"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lineas_catalogo", sa.Column("expediente_id", sa.Integer(), nullable=True))
    op.add_column("lineas_catalogo", sa.Column("motivo_revision", sa.Text(), nullable=True))

    # Backfill: toda línea existente ya cuelga de un lote (lote_id era NOT
    # NULL hasta ahora), así que expediente_id sale de ahí sin ambigüedad.
    op.execute(
        """
        UPDATE lineas_catalogo
        SET expediente_id = lotes.expediente_id
        FROM lotes
        WHERE lineas_catalogo.lote_id = lotes.id
        """
    )
    op.alter_column("lineas_catalogo", "expediente_id", nullable=False)
    op.create_foreign_key(
        "fk_lineas_catalogo_expediente_id", "lineas_catalogo", "expedientes", ["expediente_id"], ["id"]
    )

    op.alter_column("lineas_catalogo", "lote_id", nullable=True)

    op.add_column("expedientes", sa.Column("baja_variable_por_lote", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("expedientes", "baja_variable_por_lote")

    op.alter_column("lineas_catalogo", "lote_id", nullable=False)

    op.drop_constraint("fk_lineas_catalogo_expediente_id", "lineas_catalogo", type_="foreignkey")
    op.drop_column("lineas_catalogo", "motivo_revision")
    op.drop_column("lineas_catalogo", "expediente_id")
