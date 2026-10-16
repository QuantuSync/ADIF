"""Perfil de usuario: escritura o consulta

Sesión 2026-10-16 (cambio de alcance del cliente): dos perfiles. «escritura»
es lo que había hasta ahora; «consulta» ve todas las pantallas y exporta,
y nada más (`app.auth.get_usuario_con_permiso`). Los usuarios que ya existen
quedan con «escritura».

Revision ID: 0045
Revises: 0044
Create Date: 2026-10-16

"""
from alembic import op
import sqlalchemy as sa

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usuarios",
        sa.Column("perfil", sa.String(16), nullable=False, server_default="escritura"),
    )
    op.create_check_constraint("ck_usuarios_perfil", "usuarios", "perfil IN ('escritura', 'consulta')")


def downgrade() -> None:
    op.drop_constraint("ck_usuarios_perfil", "usuarios", type_="check")
    op.drop_column("usuarios", "perfil")
