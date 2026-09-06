"""expedientes: columnas de frescura para ejecución incremental

Bloque 1 de la sesión de mantenimiento automático (CONTEXTO.md sección 23):
reprocesar tenía que dejar de significar "rehacerlo todo" y pasar a
significar "procesar solo lo que falta o ha cambiado". Estas cuatro columnas
son la base de esa decisión, sin abrir ningún documento ni tocar la cascada
de extracción: `descargado_en`/`extraido_en` (cuándo terminó con éxito el
último intento real de cada etapa), `version_logica_extraccion` (para que un
cambio en `app.extraccion.*` pueda forzar reproceso aunque los documentos no
hayan cambiado) y `huella_documentos` (hash del conjunto de documentos en la
última extracción, para detectar un documento añadido/quitado/sustituido sin
releer nada).

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-04

"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expedientes", sa.Column("descargado_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column("expedientes", sa.Column("extraido_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "expedientes", sa.Column("version_logica_extraccion", sa.String(length=32), nullable=True)
    )
    op.add_column("expedientes", sa.Column("huella_documentos", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("expedientes", "huella_documentos")
    op.drop_column("expedientes", "version_logica_extraccion")
    op.drop_column("expedientes", "extraido_en")
    op.drop_column("expedientes", "descargado_en")
