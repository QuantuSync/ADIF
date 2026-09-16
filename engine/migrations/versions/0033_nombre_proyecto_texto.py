"""expedientes.nombre_proyecto y trazas_origen.valor_extraido a texto sin límite

Sesión 2026-09-16 (noche): la extracción de `6.21/28510.0040` y
`6.15/28510.0081` fallaba entera al guardar un objeto de contrato de más de
255 caracteres. La causa era un fallo de lectura (el objeto se comía media
página del anuncio, ya corregido en `app.extraccion.campos_pcsp`), pero hay
objetos reales más largos (292 caracteres en la sindicación de
`6.26/28510.0073`): un título largo no debe tumbar la extracción de un
expediente. La traza del mismo campo guarda el mismo valor.

Revision ID: 0033
Revises: 0032
Create Date: 2026-09-16

"""
from alembic import op
import sqlalchemy as sa

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("expedientes", "nombre_proyecto", type_=sa.Text(), existing_type=sa.String(255))
    op.alter_column("trazas_origen", "valor_extraido", type_=sa.Text(), existing_type=sa.String(255))


def downgrade() -> None:
    op.alter_column("trazas_origen", "valor_extraido", type_=sa.String(255), existing_type=sa.Text())
    op.alter_column("expedientes", "nombre_proyecto", type_=sa.String(255), existing_type=sa.Text())
