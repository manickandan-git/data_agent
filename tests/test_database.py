import asyncio
from unittest.mock import AsyncMock

from data_agent.utils.database import AsyncDatabaseUtil


class AsyncContext:
    def __init__(self, value=None):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
        return False


class FakeConnection:
    def __init__(self):
        self.fetch = AsyncMock()
        self.execute = AsyncMock()
        self.transaction_options = None

    def transaction(self, **options):
        self.transaction_options = options
        return AsyncContext()


class FakePool:
    def __init__(self, connection):
        self.connection = connection
        self.close = AsyncMock()

    def acquire(self):
        return AsyncContext(self.connection)


def run(awaitable):
    return asyncio.run(awaitable)


def test_connect_and_close_pool(monkeypatch):
    pool = FakePool(FakeConnection())
    create_pool = AsyncMock(return_value=pool)
    monkeypatch.setattr("data_agent.utils.database.asyncpg.create_pool", create_pool)
    database = AsyncDatabaseUtil("postgresql://test")

    run(database.connect())
    run(database.connect())
    run(database.close())

    create_pool.assert_awaited_once_with("postgresql://test")
    pool.close.assert_awaited_once()


def test_connect_failure_is_handled(monkeypatch, capsys):
    monkeypatch.setattr(
        "data_agent.utils.database.asyncpg.create_pool",
        AsyncMock(side_effect=OSError("unavailable")),
    )
    database = AsyncDatabaseUtil("postgresql://test")

    run(database.connect())

    assert database._pool is None
    assert "Error creating connection pool" in capsys.readouterr().out


def test_schema_details_include_columns_values_and_samples():
    connection = FakeConnection()

    async def fetch(query, *_args, **_kwargs):
        if "information_schema.tables" in query:
            return [{"table_name": "payments"}]
        if "information_schema.columns" in query:
            return [
                {"column_name": "payment_method", "data_type": "text"},
                {"column_name": "amount", "data_type": "numeric"},
            ]
        if "SELECT DISTINCT" in query:
            return [{"value": "credit_card"}, {"value": "paypal"}]
        return [{"payment_method": "credit_card", "amount": 12}]

    connection.fetch.side_effect = fetch
    database = AsyncDatabaseUtil("postgresql://test")
    database._pool = FakePool(connection)

    result = run(
        database.schema_details(
            "public",
            categorical_columns={"payments": ["payment_method", "missing"]},
            categorical_value_limit=10,
        )
    )

    assert "Table: payments" in result
    assert "Column: amount, Data Type: numeric" in result
    assert "Allowed values for payment_method: 'credit_card', 'paypal'" in result
    assert "Sample Data:" in result
    assert "('credit_card', 12)" in result


def test_schema_details_can_skip_samples_and_categories():
    connection = FakeConnection()
    connection.fetch.side_effect = [
        [{"table_name": "users"}],
        [{"column_name": "user_id", "data_type": "integer"}],
    ]
    database = AsyncDatabaseUtil("postgresql://test")
    database._pool = FakePool(connection)

    result = run(database.schema_details("public", include_samples=False))

    assert "Column: user_id" in result
    assert "Sample Data" not in result
    assert connection.fetch.await_count == 2


def test_schema_details_handles_missing_pool_and_fetch_error(capsys):
    database = AsyncDatabaseUtil("postgresql://test")
    assert "No active database" in run(database.schema_details("public"))

    connection = FakeConnection()
    connection.fetch.side_effect = OSError("unavailable")
    database._pool = FakePool(connection)
    result = run(database.schema_details("public"))

    assert result.startswith("Error fetching schema details")
    assert "Error fetching schema details" in capsys.readouterr().out


def test_execute_sql_supports_reads_writes_and_failures(capsys):
    connection = FakeConnection()
    connection.fetch.return_value = [{"count": 2}]
    connection.execute.return_value = "UPDATE 2"
    database = AsyncDatabaseUtil("postgresql://test")
    database._pool = FakePool(connection)

    assert run(database.execute_sql("SELECT count(*) FROM users")) == "[(2,)]"
    assert run(database.execute_sql("UPDATE users SET is_active = true")) == (
        "Query executed successfully: UPDATE 2"
    )
    assert run(database.execute_sql("UPDATE users SET x = 1 RETURNING user_id")) == "[(2,)]"

    connection.fetch.side_effect = OSError("unavailable")
    assert run(database.execute_sql("SELECT 1")) is None
    assert "Error executing query" in capsys.readouterr().out

    database._pool = None
    assert run(database.execute_sql("SELECT 1")) is None


def test_read_only_execution_uses_transaction_timeout_and_handles_errors(capsys):
    connection = FakeConnection()
    connection.fetch.return_value = [{"value": 7}]
    database = AsyncDatabaseUtil("postgresql://test")
    database._pool = FakePool(connection)

    assert run(database.execute_read_only_sql("SELECT 7", timeout=4)) == "[(7,)]"
    assert connection.transaction_options == {"readonly": True}
    assert connection.fetch.await_args.kwargs["timeout"] == 4

    connection.fetch.side_effect = TimeoutError
    assert run(database.execute_read_only_sql("SELECT 7")) is None
    assert "Error executing read-only query" in capsys.readouterr().out

    database._pool = None
    assert run(database.execute_read_only_sql("SELECT 7")) is None
