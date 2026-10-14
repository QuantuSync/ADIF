"""Usuarios, sesiones y registro de accesos

Sesión 2026-10-14 (preparación del despliegue): la plataforma va a estar
publicada en internet y deja de ser de acceso libre. Un solo perfil, altas
por consola (`python -m app.usuarios`), contraseña en argon2id.

Revision ID: 0044
Revises: 0043
Create Date: 2026-10-14

"""
from alembic import op
import sqlalchemy as sa

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(64), nullable=False, unique=True),
        sa.Column("hash_contrasena", sa.String(255), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("debe_cambiar_contrasena", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("contrasena_cambiada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "sesiones_usuario",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hash_token", sa.String(64), nullable=False, unique=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ultima_actividad", sa.DateTime(timezone=True), nullable=False),
        sa.Column("caduca_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
    )
    op.create_index("ix_sesiones_usuario_usuario_id", "sesiones_usuario", ["usuario_id"])
    op.create_table(
        "registro_accesos",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("momento", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usuario_nombre", sa.String(128), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resultado", sa.String(32), nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("agente", sa.String(255), nullable=True),
    )
    op.create_index("ix_registro_accesos_nombre_momento", "registro_accesos", ["usuario_nombre", "momento"])
    op.create_index("ix_registro_accesos_ip_momento", "registro_accesos", ["ip", "momento"])


def downgrade() -> None:
    op.drop_table("registro_accesos")
    op.drop_table("sesiones_usuario")
    op.drop_table("usuarios")
