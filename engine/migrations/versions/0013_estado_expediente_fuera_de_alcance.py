"""estado_expediente: añade fuera_de_alcance

Sesión de criterios de alcance del cliente (CONTEXTO.md sección 26): solo bajas
de material por lotes; un contrato de obra no es un fallo de extracción sino
un tipo de contrato fuera del alcance de este motor. Distinto de
`sin_publicar` (ahí no hay expediente que leer) y de `pendiente_revision`
(hace falta un humano decidiendo sobre datos reales) -- aquí no hay nada que
decidir, está fuera de alcance por diseño. Ningún expediente real del corpus
actual lo dispara (CONTEXTO.md sección 26: el único departamento del corpus,
28510, es "Suministros"); es una guarda para cuando aparezca uno.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-04

"""
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE estado_expediente ADD VALUE IF NOT EXISTS 'fuera_de_alcance'")


def downgrade() -> None:
    # Postgres no soporta quitar un valor de un enum. Downgrade no reversible;
    # documentado en vez de fingir que se deshace.
    raise NotImplementedError(
        "No se puede quitar un valor de un enum de Postgres. "
        "Si hace falta revertir, restaurar desde una copia de seguridad anterior a esta migración."
    )
