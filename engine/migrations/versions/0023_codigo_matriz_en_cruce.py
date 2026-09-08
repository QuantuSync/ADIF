"""expedientes.codigo_matriz_en_cruce: reintento del cruce con el Excel de
códigos cuando cambia la matriz

Sesión de auditoría automática (2026-09-08, bloque 2 punto 2,
docs/sesion-2026-09-08-auditoria-automatica.md): `asegurar_cruce_codigos`
solo se intentaba una vez por expediente (`codigos_cruzados` pasa de `None`
a `True`/`False` para siempre). Un pedido derivado de acuerdo marco
descubierto por el mecanismo inverso resuelve su `codigo_matriz` DESPUÉS de
que el cruce ya se intentó y falló -- quedaba `codigos_cruzados=False` para
siempre aunque la matriz recién conocida sí cruzara (verificado con
`6.26/28510.0032`, `0071`, `0014`).

`codigo_matriz_en_cruce` guarda qué `codigo_matriz` (normalizado) tenía el
expediente en el último intento, para poder distinguir "sigue sin haber
nada nuevo que probar" de "hay una matriz distinta desde el último
intento, vale la pena reintentar".

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "expedientes",
        sa.Column("codigo_matriz_en_cruce", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("expedientes", "codigo_matriz_en_cruce")
