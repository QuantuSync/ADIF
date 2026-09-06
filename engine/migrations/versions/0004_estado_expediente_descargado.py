"""estado_expediente: añade descargado

CONTEXTO.md, encargo de esta sesión (cola y seguimiento), punto 2: la descarga
y la extracción son dos trabajos de cola encadenados, no uno solo. Sin este
estado intermedio, un expediente que ya terminó de descargar pero cuyo
trabajo de extracción todavía no ha arrancado (encolado, esperando al
worker) se ve indistinguible de uno que ya está extrayendo — un estado que
miente, justo lo que CONTEXTO.md sección 12 pide evitar.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-02

"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE estado_expediente ADD VALUE IF NOT EXISTS 'descargado' AFTER 'descargando'")


def downgrade() -> None:
    # Postgres no soporta quitar un valor de un enum. Downgrade no reversible;
    # documentado en vez de fingir que se deshace.
    raise NotImplementedError(
        "No se puede quitar un valor de un enum de Postgres. "
        "Si hace falta revertir, restaurar desde una copia de seguridad anterior a esta migración."
    )
