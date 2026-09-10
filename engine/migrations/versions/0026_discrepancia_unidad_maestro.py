"""discrepancia_unidad_maestro

Bloque 1, sesión 2026-09-10: el cliente facilita por fin
`LISTADO_MATERIALES_UNIDAD__MEDIDA.xlsx` (32.116 filas, tres columnas:
`Material`, `Denominación`, `UM base` -- distintas de las que suponía la
migración 0025, `Material`/`Texto breve`/`Unidad medida base`; corregido en
`app.extraccion.maestro_materiales` en el mismo bloque).

Dos cambios de esquema:

1. `maestro_materiales.matricula` ensancha de `String(9)` a `String(10)`:
   el fichero real trae 31.665 códigos de nueve dígitos pero también 440 de
   cuatro y 11 de diez (categorías genéricas de SAP, p. ej. "1000" =
   "Material de subestaciones") -- `String(9)` truncaría la carga con un
   error de base de datos en los códigos de diez. No afecta al cruce: la
   matrícula de una línea del catálogo es siempre de nueve dígitos por
   definición de dominio (CONTEXTO.md sección 2), así que las de diez
   simplemente nunca casan con ninguna línea, y eso está bien.

2. `lineas_catalogo.unidad_medida_discrepancia_maestro` (nuevo, nullable):
   encargo explícito del cliente para este bloque -- "si el documento dice
   una cosa y SAP otra, deja la del documento y marca la discrepancia para
   revisión, porque es información útil". Guarda la unidad que dice el
   maestro SOLO cuando la línea ya tiene su propia `unidad_medida` (del
   documento real) y no coincide con la del maestro -- nunca sobrescribe
   `unidad_medida`, mismo principio que CONTEXTO.md sección 12 ("un
   contraste externo puede señalar un desajuste, pero no tiene autoridad
   para cambiar el estado").

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "maestro_materiales",
        "matricula",
        existing_type=sa.String(9),
        type_=sa.String(10),
        existing_nullable=False,
    )
    op.add_column(
        "lineas_catalogo",
        sa.Column("unidad_medida_discrepancia_maestro", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lineas_catalogo", "unidad_medida_discrepancia_maestro")
    op.alter_column(
        "maestro_materiales",
        "matricula",
        existing_type=sa.String(10),
        type_=sa.String(9),
        existing_nullable=False,
    )
