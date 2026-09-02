"""tipo_documento: añade resolucion_adjudicacion

CLAUDE.md sección 5, etapa 1 y sección 17: la Propuesta de Adjudicación
(LC.27) y la Resolución de Adjudicación son documentos distintos que pueden
coexistir para un mismo expediente, y el motor debe poder clasificarlos por
separado aunque declaren el mismo hecho.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-02

"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No se puede usar el valor nuevo en la misma transacción en la que se
    # añade (restricción de Postgres para ALTER TYPE ... ADD VALUE); esta
    # migración solo lo añade, no lo usa.
    op.execute("ALTER TYPE tipo_documento ADD VALUE IF NOT EXISTS 'resolucion_adjudicacion' AFTER 'propuesta_lc27'")


def downgrade() -> None:
    # Postgres no soporta quitar un valor de un enum. Downgrade no reversible;
    # documentado en vez de fingir que se deshace.
    raise NotImplementedError(
        "No se puede quitar un valor de un enum de Postgres. "
        "Si hace falta revertir, restaurar desde una copia de seguridad anterior a esta migración."
    )
