"""trazas_origen: fuera los duplicados idénticos acumulados, índice por entidad y campo

Sesión 2026-09-17 (bloque 4): cada extracción añadía otra vez la misma traza
(35.777 filas para unas 2.000 distintas). `app.extraccion.traza.registrar_traza`
ya sustituye en vez de sumar; aquí se borra lo acumulado, quedándose con la
copia de `id` mayor de cada traza idéntica (la más reciente es la que se lee).
El índice sirve a la búsqueda de la traza igual en cada escritura.

Revision ID: 0034
Revises: 0033
Create Date: 2026-09-17

"""
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM trazas_origen t
        USING trazas_origen u
        WHERE t.entidad_tipo = u.entidad_tipo
          AND t.entidad_id = u.entidad_id
          AND t.campo = u.campo
          AND t.documento_id = u.documento_id
          AND t.pagina IS NOT DISTINCT FROM u.pagina
          AND t.fragmento IS NOT DISTINCT FROM u.fragmento
          AND t.valor_extraido IS NOT DISTINCT FROM u.valor_extraido
          AND t.id < u.id
        """
    )
    op.create_index("ix_trazas_origen_entidad_campo", "trazas_origen", ["entidad_tipo", "entidad_id", "campo"])


def downgrade() -> None:
    op.drop_index("ix_trazas_origen_entidad_campo", table_name="trazas_origen")
