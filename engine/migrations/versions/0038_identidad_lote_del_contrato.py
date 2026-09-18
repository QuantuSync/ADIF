"""Qué lote dice un Contrato firmado que es, guardado en el propio documento

Bloque 3, sesión 2026-09-18 (sexta parte). `app.extraccion.lotes.
extraer_identidad_contrato` ya leía bien la cabecera de un Contrato firmado
("Contrato nº: X" + "LOTE N"), pero su resultado se perdía cuando el
expediente no traía además una Resolución de Adjudicación o una Propuesta que
declarase lotes: `app.extraccion.orquestador._extraer_lotes` solo abre
candidatos con esas tres plantillas y, sin ninguna, devuelve lista vacía sin
mirar las identidades de los Contratos. Consecuencia medida: los tres
expedientes que un Contrato declara por número como lote de otro
(`4.23/28510.0081`, `6.19/28510.0213`, `6.19/28510.0216`) salían del
entregable como "no publicados", que es falso.

Crear el lote desde esa identidad NO es un arreglo pequeño (toca 40
expedientes y puede dejar huérfanas miles de líneas ya atribuidas), así que
aquí solo se **guarda el hecho leído**, en el documento que lo declara, para
que la hoja "Conciliación" pueda decir la verdad sobre esos expedientes
(`app.conciliacion._lotes_en_ficha_de_otro`). No crea ni cambia ningún lote,
ninguna línea de catálogo y ningún estado.

Va en `documentos` y no en `lotes` porque es una propiedad del fichero --
lo que ese PDF dice de sí mismo --, igual que `tipo_documento`: el mismo
Contrato enlazado a dos expedientes declara el mismo lote en los dos.

Se deja a NULL en todos los documentos ya clasificados; `_clasificar_documentos`
lo rellena en la siguiente extracción de cada expediente.

Revision ID: 0038
Revises: 0037
Create Date: 2026-09-18

"""
from alembic import op
import sqlalchemy as sa

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documentos", sa.Column("identidad_lote_codigo", sa.String(length=64), nullable=True))
    op.add_column("documentos", sa.Column("identidad_lote_identificador", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("documentos", "identidad_lote_identificador")
    op.drop_column("documentos", "identidad_lote_codigo")
