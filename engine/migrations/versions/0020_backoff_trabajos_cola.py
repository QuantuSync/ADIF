"""disponible_en en trabajos_cola (backoff creciente en reintentos)

Sesión de límite de tasa de la Plataforma (2026-09-07): 454 descargas
fallidas seguidas y 11 periodos de sindicación fallando consecutivamente
tras 10 correctos apuntan a un bloqueo/límite de tasa bajo carga, no a
ausencias reales -- `tomar_siguiente_trabajo` reintentaba un trabajo
fallido en la siguiente vuelta del bucle (3 s después) sin ninguna espera,
machacando la Plataforma real sin pausa. `disponible_en` (NULL = disponible
ya, como siempre) deja que un reintento espere con backoff creciente antes
de que `tomar_siguiente_trabajo` vuelva a recogerlo.

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-07

"""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trabajos_cola", sa.Column("disponible_en", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("trabajos_cola", "disponible_en")
