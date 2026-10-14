from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.db import Base
from app import models  # noqa: F401  registra los modelos en Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # Una transacción por migración (sesión 2026-10-14): varias añaden un
        # valor a un enum con ALTER TYPE ... ADD VALUE, y PostgreSQL no deja
        # usar ese valor hasta que esa transacción se confirma. Con todas en
        # una sola, migrar una base vacía desde cero fallaba en la 0031 (usa
        # `sin_publicar`, añadido en la 0010); una base que se había ido
        # migrando poco a poco nunca lo vio. Pasó al probar el despliegue.
        context.configure(
            connection=connection, target_metadata=target_metadata, transaction_per_migration=True
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
