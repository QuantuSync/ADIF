"""lotes: modelo de precio indexado por pedido (segunda familia de baja)

Sesión de trabajo pendiente real (2026-09-05): 3 expedientes reales
(`6.23/28510.0018`, `6.23/28510.0102`, `6.25/28510.0016`) son Acuerdos Marco
de suministro de carril nuevo cuya fórmula de precio es
`P(t) = Precio_ofertado × Kt × Coeficiente_de_baja`, verificada contra los
tres documentos reales -- distinta del modelo de baja única por lote
(CLAUDE.md sección 4). Ni `Kt` (índices IPRI de energía/acero, publicados por
el INE) ni el "Coeficiente de baja" existen en ningún documento de la
licitación: los fija ADIF pedido a pedido, en el futuro, contra el acuerdo
marco ya adjudicado. Lo único que la licitación sí fija es el "coeficiente de
transformación" (1,276 en los tres casos), que se aplica a los precios de
referencia del PPT para obtener el precio ofertado.

`lotes.baja_lote`/`precio_adjudicado` de las líneas de este modelo se quedan
NULL por diseño, no por fallo -- no hay un valor único que extraer. Este
campo (`modelo_precio`) es la señal explícita y auditable de por qué, en vez
de dejarlo implícito en un motivo de texto que se pierde en el histórico de
`trabajos_cola`. Deliberadamente NO se añade ninguna columna para los pesos
de `Kt` ni los grupos IPRI (encargo explícito de esta sesión: sin caso de uso
real hoy, ver `docs/identidad-expediente.md` sección 28 para la propuesta
completa sin implementar).

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-05

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

modelo_precio = postgresql.ENUM(
    "fijo", "indexado_por_pedido",
    name="modelo_precio",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    modelo_precio.create(bind, checkfirst=True)
    op.add_column(
        "lotes",
        sa.Column("modelo_precio", modelo_precio, nullable=False, server_default="fijo"),
    )
    op.add_column(
        "lotes",
        sa.Column("coeficiente_transformacion", sa.Numeric(8, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lotes", "coeficiente_transformacion")
    op.drop_column("lotes", "modelo_precio")
    modelo_precio.drop(op.get_bind(), checkfirst=True)
