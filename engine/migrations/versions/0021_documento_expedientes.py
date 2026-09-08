"""documento_expedientes: un documento puede pertenecer a varios expedientes

Sesión de colisión de hash entre expedientes hermanos (2026-09-08, ver
docs/analisis-corpus-467-expedientes.md sección 2): `documentos.expediente_id`
era una FK simple (un documento, un único expediente dueño). Con la
constraint `UNIQUE(documentos.hash)`, cuando dos códigos de expediente
distintos resuelven al mismo PDF real (expedientes hermanos de la misma
licitación multi-lote, verificado con `4.25/28510.0124`/`0132`, bytes
idénticos), el segundo en reclamar ese hash se quedaba sin ninguna fila de
`Documento` propia -- el fichero existía en el sistema, pero ese expediente
no lo veía. Confirmado en al menos 26 de los 303 expedientes en revisión.

Encargo explícito del cliente: "es correcto no duplicar el fichero, pero un
documento tiene que poder pertenecer a varios expedientes". Se separa la
identidad del fichero físico (`documentos`: hash, tipo, ruta, páginas -- lo
que decide el CONTENIDO del PDF, igual sea cual sea el expediente que lo
mire) de la relación con cada expediente que lo referencia
(`documento_expedientes`: qué expedientes lo ven y cómo lo llama cada uno
-- `nombre_archivo` se mueve aquí porque es "cómo numeró ESA descarga
concreta este documento dentro de su categoría", puede variar entre
expedientes que comparten el mismo fichero).

Migración sin pérdida: cada fila de `documentos` existente pasa a
`documento_expedientes` conservando su expediente y nombre actuales antes
de retirar esas dos columnas de `documentos`.

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documento_expedientes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documentos.id"), nullable=False),
        sa.Column("expediente_id", sa.Integer(), sa.ForeignKey("expedientes.id"), nullable=False),
        sa.Column("nombre_archivo", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("documento_id", "expediente_id", name="uq_documento_expediente"),
    )

    # Migración sin pérdida: una fila de relación por cada documento
    # existente, conservando su expediente y nombre actuales antes de
    # retirar esas columnas de `documentos`.
    op.execute(
        """
        INSERT INTO documento_expedientes (documento_id, expediente_id, nombre_archivo, created_at)
        SELECT id, expediente_id, nombre_archivo, created_at FROM documentos
        """
    )

    op.drop_column("documentos", "expediente_id")
    op.drop_column("documentos", "nombre_archivo")


def downgrade() -> None:
    op.add_column("documentos", sa.Column("expediente_id", sa.Integer(), nullable=True))
    op.add_column("documentos", sa.Column("nombre_archivo", sa.String(255), nullable=True))

    # Recupera un único (expediente, nombre) por documento -- el más antiguo
    # enlazado, para volver al estado "un documento, un dueño" de antes.
    op.execute(
        """
        UPDATE documentos d
        SET expediente_id = de.expediente_id, nombre_archivo = de.nombre_archivo
        FROM (
            SELECT DISTINCT ON (documento_id) documento_id, expediente_id, nombre_archivo
            FROM documento_expedientes
            ORDER BY documento_id, id
        ) de
        WHERE de.documento_id = d.id
        """
    )

    op.alter_column("documentos", "expediente_id", nullable=False)
    op.alter_column("documentos", "nombre_archivo", nullable=False)
    op.create_foreign_key(
        "documentos_expediente_id_fkey", "documentos", "expedientes", ["expediente_id"], ["id"]
    )
    op.drop_table("documento_expedientes")
