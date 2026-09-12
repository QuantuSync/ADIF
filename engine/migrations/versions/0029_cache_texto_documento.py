"""cache_texto_documento

Bloque 6, sesión de rendimiento (CONTEXTO.md sección 16, `docs/sesion-2026-
09-12-defecto-mapeo-calidad-interfaz-rendimiento.md` bloque 4): el perfil
real de un reproceso mostró que ~99% del tiempo se va en `pdfplumber`
extrayendo el texto plano de cada página de cada documento (etapa 1 de la
cascada, clasificación de plantilla) -- trabajo idéntico en cada reproceso
mientras el documento no cambie. Mismo mecanismo que `cache_mapeo_cabecera`
(migración 0003): clave por contenido (`Documento.hash`, no por id ni por
ruta), invalidable subiendo `VERSION_LOGICA_TEXTO`
(`app.extraccion.texto`) sin tocar ninguna fila a mano.

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-13

"""
from alembic import op
import sqlalchemy as sa

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cache_texto_documento",
        sa.Column("documento_hash", sa.String(64), primary_key=True),
        sa.Column("version_logica_texto", sa.String(32), nullable=False),
        sa.Column("num_paginas", sa.Integer(), nullable=False),
        sa.Column("paginas", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("cache_texto_documento")
