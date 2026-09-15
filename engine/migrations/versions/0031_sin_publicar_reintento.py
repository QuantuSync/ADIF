"""expedientes.sin_publicar_en / sin_publicar_version_busqueda: `sin_publicar`
deja de ser definitivo

Sesión 2026-09-15 (expedientes de 2026 que faltaban): 6 expedientes de 2026
del departamento 28510 estaban `sin_publicar` por búsquedas hechas durante el
bloqueo de la Plataforma del 2026-09-07 (17:00-18:50 UTC), antes de que el
arreglo de límite de tasa (commit `eeab48b`) llegara al worker a las 20:00
UTC -- hasta entonces un timeout o un bloqueo se leía como "no publicado".
Reintentados, aparecieron los seis. El ciclo de mantenimiento no volvía a
buscar nunca un `sin_publicar`.

Las dos columnas dicen cuándo y con qué versión de la lógica de búsqueda
(`app.mantenimiento.frescura.VERSION_LOGICA_BUSQUEDA`) se confirmó el
negativo. Relleno de los `sin_publicar` existentes: la fecha es la de su
última búsqueda "no encontrado"; la versión solo se pone si esa búsqueda es
posterior al despliegue del arreglo -- las anteriores quedan sin versión (no
confirmadas) y el ciclo las vuelve a buscar en seguida.

Revision ID: 0031
Revises: 0030
Create Date: 2026-09-15

"""
from alembic import op
import sqlalchemy as sa

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expedientes", sa.Column("sin_publicar_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column("expedientes", sa.Column("sin_publicar_version_busqueda", sa.String(32), nullable=True))
    op.execute(
        """
        UPDATE expedientes e
        SET sin_publicar_en = (
            SELECT max(t.updated_at) FROM trabajos_cola t
            WHERE t.expediente_id = e.id
              AND t.tipo = 'descargar_expediente'
              AND t.error LIKE 'no encontrado en la Plataforma%'
        )
        WHERE e.estado = 'sin_publicar'
        """
    )
    op.execute(
        """
        UPDATE expedientes
        SET sin_publicar_version_busqueda = '2026-09-07'
        WHERE estado = 'sin_publicar'
          AND sin_publicar_en >= TIMESTAMPTZ '2026-09-07 20:00:00+00'
        """
    )


def downgrade() -> None:
    op.drop_column("expedientes", "sin_publicar_version_busqueda")
    op.drop_column("expedientes", "sin_publicar_en")
