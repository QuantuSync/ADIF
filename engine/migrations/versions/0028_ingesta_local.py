"""ingesta_local

Bloque 6, sesión de comparación documento-vs-listado interno: segunda vía de
ingesta de documentos, para expedientes vigentes en el SAP del cliente que
todavía no están publicados en la Plataforma (`app.ingesta_local`).

- `documentos.origen`: de dónde viene el fichero físico ("plataforma" /
  "manual", ver docstring de `OrigenDocumento`). `server_default`
  "plataforma": todo documento anterior a esta sesión llegó por scraping.
- `expedientes.aviso_ingesta_manual`: un documento de la carpeta de ingesta
  declara un código propio distinto del de su carpeta -- no se adivina, se
  señala para revisión.
- `expedientes.aviso_conflicto_documento_manual`: el expediente combina, para
  el mismo tipo de documento, uno descargado y uno aportado a mano -- aviso
  informativo de que puede haber dos versiones del mismo hecho (la Plataforma
  gana en la cascada, pero el valor descartado no se pierde en silencio).

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-11

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

origen_documento = postgresql.ENUM(
    "plataforma", "manual",
    name="origen_documento",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    origen_documento.create(bind, checkfirst=True)
    op.add_column(
        "documentos",
        sa.Column("origen", origen_documento, nullable=False, server_default="plataforma"),
    )
    op.add_column("expedientes", sa.Column("aviso_ingesta_manual", sa.Text(), nullable=True))
    op.add_column("expedientes", sa.Column("aviso_conflicto_documento_manual", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("expedientes", "aviso_conflicto_documento_manual")
    op.drop_column("expedientes", "aviso_ingesta_manual")
    op.drop_column("documentos", "origen")
    origen_documento.drop(op.get_bind(), checkfirst=True)
