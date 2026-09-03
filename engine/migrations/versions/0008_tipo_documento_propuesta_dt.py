"""tipo_documento: añade propuesta_dt

docs/analisis-corpus.md hallazgo 4 (sesión de arreglos pequeños,
2026-09-03): tercera plantilla de propuesta ("L9_CM.32-FE",
"INFORME-PROPUESTA DE ADJUDICACIÓN DE CONTRATO"), usada por Dirección
Técnica, sin regla de clasificación propia hasta ahora — caía en `otro` o en
un falso positivo de `pliego`. Mismo tipo de hecho que propuesta_lc27
(declara baja y adjudicatario) pero con su propia anatomía, así que se le da
tipo propio en vez de forzarla como alias.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-03

"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No se puede usar el valor nuevo en la misma transacción en la que se
    # añade (restricción de Postgres para ALTER TYPE ... ADD VALUE); esta
    # migración solo lo añade, no lo usa.
    op.execute("ALTER TYPE tipo_documento ADD VALUE IF NOT EXISTS 'propuesta_dt' AFTER 'pliego'")


def downgrade() -> None:
    # Postgres no soporta quitar un valor de un enum. Downgrade no reversible;
    # documentado en vez de fingir que se deshace.
    raise NotImplementedError(
        "No se puede quitar un valor de un enum de Postgres. "
        "Si hace falta revertir, restaurar desde una copia de seguridad anterior a esta migración."
    )
