from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from config import get_config
from models.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Resolve the migration database URL.

    DATABASE_URL takes precedence over sqlalchemy.url from alembic.ini.
    Percent signs are escaped because Alembic uses ConfigParser internally.
    """
    secret_url = get_config().database_url
    database_url = secret_url.get_secret_value() if secret_url else None

    if not database_url:
        database_url = config.get_main_option("sqlalchemy.url")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not set and sqlalchemy.url is missing from alembic.ini")

    return database_url


def configure_database_url() -> None:
    database_url = get_database_url()
    config.set_main_option(
        "sqlalchemy.url",
        database_url.replace("%", "%%"),
    )


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""
    configure_database_url()

    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_sync_migrations(connection: Connection) -> None:
    """Configure Alembic using an active synchronous connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an asynchronous engine and run migrations."""
    configure_database_url()

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(run_sync_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations using an asynchronous database connection."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
