"""candidatos_matricula

Bloque 1, sesión 2026-09-11: cola de candidatos de matrícula para revisión
humana (CONTEXTO.md, análisis previo de la sesión del maestro de
materiales, 2026-09-10, bloque 2 -- "si esto se construye, tiene que ser
una cola de candidatos para confirmación humana... nunca una asignación
automática, ni siquiera para el 8,6% de coincidencia exacta").

- `candidatos_matricula`: caché recomputable (mismo patrón que
  `cache_mapeo_cabecera`/`candidatos_acuerdo_marco`) de qué matrículas del
  maestro de materiales podrían corresponder a cada línea de catálogo sin
  matrícula, con su grado de coincidencia -- nunca se lee como fuente de
  verdad, se recalcula entera cada vez que se pide.
- `lineas_catalogo.matricula_confirmada_manualmente`: `True` cuando la
  matrícula se aceptó desde esta cola, no se extrajo del documento -- mismo
  patrón que `unidad_medida_completada_desde_maestro` (migración 0025).
- `lineas_catalogo.matricula_candidatos_rechazados`: `True` cuando un
  humano revisó los candidatos de esta línea y determinó que ninguno es
  correcto -- saca la línea de la cola sin borrar los candidatos (que
  siguen contando para "líneas con al menos un candidato").

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-11

"""
from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lineas_catalogo",
        sa.Column("matricula_confirmada_manualmente", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "lineas_catalogo",
        sa.Column("matricula_candidatos_rechazados", sa.Boolean(), nullable=True),
    )
    op.create_table(
        "candidatos_matricula",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "linea_catalogo_id",
            sa.Integer(),
            sa.ForeignKey("lineas_catalogo.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("matricula_candidata", sa.String(10), nullable=False),
        sa.Column("denominacion_maestro", sa.String(255), nullable=True),
        sa.Column("similitud", sa.Numeric(5, 4), nullable=False),
        sa.Column("exacto", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("calculado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_candidatos_matricula_linea_catalogo_id", "candidatos_matricula", ["linea_catalogo_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_candidatos_matricula_linea_catalogo_id", table_name="candidatos_matricula")
    op.drop_table("candidatos_matricula")
    op.drop_column("lineas_catalogo", "matricula_candidatos_rechazados")
    op.drop_column("lineas_catalogo", "matricula_confirmada_manualmente")
