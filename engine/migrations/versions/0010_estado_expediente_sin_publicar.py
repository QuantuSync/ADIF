"""estado_expediente: añade sin_publicar

Sesión de expedientes sin publicar (CLAUDE.md sección 22): 14 códigos reales
de la Plataforma (6 expedientes derivados sin documentos + 8 matrices de
acuerdo marco) se comprobaron a mano y por scraping real, con todas las
variantes de separador, y no devuelven resultados. No son recuperables ni son
trabajo pendiente -- `sin_publicar` los distingue de `fallido` (que sugiere
que reintentar podría funcionar) y de `pendiente_revision` (que dice que hace
falta un humano).

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-03

"""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE estado_expediente ADD VALUE IF NOT EXISTS 'sin_publicar'")


def downgrade() -> None:
    # Postgres no soporta quitar un valor de un enum. Downgrade no reversible;
    # documentado en vez de fingir que se deshace.
    raise NotImplementedError(
        "No se puede quitar un valor de un enum de Postgres. "
        "Si hace falta revertir, restaurar desde una copia de seguridad anterior a esta migración."
    )
