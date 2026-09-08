from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_compose_defines_the_production_stack() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    for service in (
        "postgres:",
        "bootstrap-db-roles:",
        "migrate:",
        "otel-collector:",
        "api:",
    ):
        assert service in compose
    assert "condition: service_healthy" in compose
    assert "condition: service_completed_successfully" in compose
    assert compose.count("${COMPOSE_ENV_FILE:-.env.compose}") == 2
    assert 'API_READINESS_DATABASE_ENABLED: "true"' in compose
    assert "OTEL_EXPORTER_ENDPOINT: http://otel-collector:4318/v1/traces" in compose
    assert "POSTGRES_MIGRATION_USER" in compose
    assert "POSTGRES_APP_USER" in compose
    assert "default_transaction_read_only" in (
        ROOT / "docker" / "postgres" / "bootstrap-roles.sh"
    ).read_text(encoding="utf-8")


def test_compose_keeps_mutable_data_in_separate_volumes() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "postgres-data:/var/lib/postgresql/data" in compose
    assert '"${POSTGRES_HOST_PORT:-5445}:5432"' in compose
    assert '"${API_HOST_PORT:-8000}:8000"' in compose
    assert "extract-data:/app/data/extract" in compose
    assert "transform-data:/app/data/transform" in compose
    assert ":/app/data\n" not in compose


def test_collector_accepts_and_exports_traces_and_metrics() -> None:
    collector = (ROOT / "docker" / "otel-collector.yaml").read_text(encoding="utf-8")

    assert "traces:" in collector
    assert "metrics:" in collector
    assert "receivers: [otlp]" in collector
    assert "exporters: [debug]" in collector


def test_database_role_bootstrap_enforces_least_privilege() -> None:
    bootstrap = (ROOT / "docker" / "postgres" / "bootstrap-roles.sh").read_text(encoding="utf-8")

    assert "Database administrator, migration, and application roles must be distinct" in bootstrap
    assert "REVOKE ALL PRIVILEGES ON ALL TABLES" in bootstrap
    assert "REVOKE TEMPORARY ON DATABASE" in bootstrap
    assert "GRANT SELECT ON ALL TABLES" in bootstrap
    assert "ALTER DEFAULT PRIVILEGES" in bootstrap
    assert "default_transaction_read_only = on" in bootstrap

    verification = (ROOT / "docker" / "postgres" / "verify-read-only-role.sh").read_text(
        encoding="utf-8"
    )
    assert "current_setting('default_transaction_read_only')" in verification
    assert "has_table_privilege" in verification
    assert "table_owners" in verification
    assert "CREATE TABLE public.data_agent_role_probe" in verification
