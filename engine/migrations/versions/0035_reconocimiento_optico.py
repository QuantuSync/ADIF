"""Reconocimiento óptico de documentos escaneados: caché por hash y marca en la línea

Sesión 2026-09-17: `cache_ocr_documento` guarda el texto reconocido de cada
documento escaneado (por hash, como `cache_texto_documento`) y
`lineas_catalogo.texto_reconocido` marca las líneas que salen de él.

Revision ID: 0035
Revises: 0034
Create Date: 2026-09-17

"""
from alembic import op
import sqlalchemy as sa

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cache_ocr_documento",
        sa.Column("documento_hash", sa.String(64), primary_key=True),
        sa.Column("version_logica_ocr", sa.String(32), nullable=False),
        sa.Column("modelo", sa.String(64), nullable=False),
        sa.Column("num_paginas", sa.Integer(), nullable=False),
        sa.Column("completo", sa.Boolean(), nullable=False),
        sa.Column("paginas", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column("lineas_catalogo", sa.Column("texto_reconocido", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("lineas_catalogo", "texto_reconocido")
    op.drop_table("cache_ocr_documento")
