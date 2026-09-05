from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, make_url, text

from data_agent.config import get_config

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.getenv("MIGRATION_TEST_DATABASE_URL")
DOMAIN_TABLES = {"payments", "ratings", "rides", "users", "vehicles"}

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="MIGRATION_TEST_DATABASE_URL is not configured",
)


def alembic_config() -> Config:
    return Config(PROJECT_ROOT / "alembic.ini")


def synchronous_url(database_url: str) -> str:
    url = make_url(database_url)
    if "test" not in (url.database or "").lower():
        raise ValueError("Migration tests require a database name containing 'test'")
    return url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)


def test_migrations_upgrade_match_models_and_downgrade(monkeypatch):
    assert TEST_DATABASE_URL is not None
    sync_url = synchronous_url(TEST_DATABASE_URL)
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    get_config.cache_clear()
    engine = create_engine(sync_url)

    try:
        command.upgrade(alembic_config(), "head")

        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names(schema="public"))
            seeded_users = connection.execute(
                text("SELECT count(*) FROM public.users")
            ).scalar_one()

        assert DOMAIN_TABLES <= tables
        assert seeded_users > 0

        # Fails if ORM metadata differs from the schema at the current migration head.
        command.check(alembic_config())

        command.downgrade(alembic_config(), "base")
        with engine.connect() as connection:
            remaining_tables = set(inspect(connection).get_table_names(schema="public"))

        assert DOMAIN_TABLES.isdisjoint(remaining_tables)
    finally:
        engine.dispose()
        get_config.cache_clear()
