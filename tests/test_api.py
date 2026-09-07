import asyncio
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from data_agent.api import create_app
from data_agent.config import Settings


def test_health_endpoint():
    app = create_app(workflow=Mock(), settings=Settings(_env_file=None))

    with TestClient(app) as client:
        response = client.get("/health")
        live = client.get("/health/live")
        ready = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert live.status_code == 200
    assert ready.status_code == 200


def test_readiness_checks_database_when_enabled():
    check = AsyncMock()
    settings = Settings(
        _env_file=None,
        database_url="postgresql://test",
        api_readiness_database_enabled=True,
    )
    app = create_app(workflow=Mock(), settings=settings, readiness_check=check)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    check.assert_awaited_once_with(settings)


def test_readiness_hides_database_failure_details():
    check = AsyncMock(side_effect=OSError("database password leaked"))
    settings = Settings(
        _env_file=None,
        database_url="postgresql://test",
        api_readiness_database_enabled=True,
    )
    app = create_app(workflow=Mock(), settings=settings, readiness_check=check)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "The service is not ready."}
    assert "password" not in response.text


def test_production_disables_interactive_api_documentation_by_default():
    settings = Settings(
        _env_file=None,
        app_environment="production",
        api_keys="a" * 32,
    )
    app = create_app(workflow=Mock(), settings=settings)

    with TestClient(app) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_query_endpoint_returns_standardized_workflow_result():
    workflow = Mock()
    workflow.invoke.return_value = {
        "run_id": "workflow-run",
        "status": "success",
        "route_response": "sql",
        "final_answer": "The total is 42.",
        "workflow_error": "",
    }
    app = create_app(workflow=workflow, settings=Settings(_env_file=None))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/query",
            json={"question": "What is the total?"},
        )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "workflow-run"
    assert response.json() == {
        "run_id": "workflow-run",
        "status": "success",
        "route": "sql",
        "final_answer": "The total is 42.",
        "workflow_error": "",
    }
    submitted = workflow.invoke.call_args.args[0]
    assert submitted["run_id"]
    assert submitted["messages"][0].content == "What is the total?"


def test_query_rejects_empty_or_unknown_fields():
    app = create_app(workflow=Mock(), settings=Settings(_env_file=None))

    with TestClient(app) as client:
        empty = client.post("/api/v1/query", json={"question": ""})
        extra = client.post(
            "/api/v1/query",
            json={"question": "hello", "sql": "DROP TABLE users"},
        )

    assert empty.status_code == 422
    assert extra.status_code == 422


def test_query_rejects_oversized_request():
    settings = Settings(_env_file=None, api_max_request_bytes=1024)
    app = create_app(workflow=Mock(), settings=settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/query",
            json={"question": "x" * 2_000},
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body is too large."}


def test_query_hides_unhandled_exception_details():
    workflow = Mock()
    workflow.invoke.side_effect = RuntimeError("database password leaked")
    app = create_app(workflow=workflow, settings=Settings(_env_file=None))

    with TestClient(app) as client:
        response = client.post("/api/v1/query", json={"question": "hello"})

    assert response.status_code == 500
    assert response.json()["status"] == "error"
    assert response.json()["workflow_error"] == "The request could not be processed."
    assert "password" not in response.text


def test_api_telemetry_correlates_request_without_exporting_question():
    workflow = Mock()
    workflow.invoke.return_value = {
        "status": "success",
        "route_response": "sql",
        "final_answer": "safe answer",
        "workflow_error": "",
    }
    exporter = InMemorySpanExporter()
    settings = Settings(
        _env_file=None,
        app_environment="test",
        otel_enabled=True,
        otel_exporter_endpoint="http://collector.test/v1/traces",
    )
    app = create_app(
        workflow=workflow,
        settings=settings,
        span_exporter=exporter,
        metric_reader=InMemoryMetricReader(),
    )

    with TestClient(app) as client:
        response = client.post("/api/v1/query", json={"question": "private question"})
        client.get("/health")

    spans = exporter.get_finished_spans()
    correlated = [span for span in spans if "data_agent.run_id" in span.attributes]
    assert response.status_code == 200
    assert correlated[0].attributes["data_agent.run_id"] == response.headers["x-request-id"]
    assert "private question" not in "".join(span.to_json() for span in spans)
    assert all("/health" not in span.name for span in spans)


def test_query_requires_valid_bearer_key_when_authentication_is_enabled():
    key = "a" * 32
    workflow = Mock()
    workflow.invoke.return_value = {
        "status": "success",
        "route_response": "sql",
        "final_answer": "answer",
        "workflow_error": "",
    }
    settings = Settings(_env_file=None, api_auth_enabled=True, api_keys=key)
    app = create_app(workflow=workflow, settings=settings)

    with TestClient(app) as client:
        health = client.get("/health")
        missing = client.post("/api/v1/query", json={"question": "hello"})
        invalid = client.post(
            "/api/v1/query",
            headers={"Authorization": "Bearer wrong-key"},
            json={"question": "hello"},
        )
        accepted = client.post(
            "/api/v1/query",
            headers={"Authorization": f"Bearer {key}"},
            json={"question": "hello"},
        )

    assert health.status_code == 200
    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert invalid.status_code == 401
    assert accepted.status_code == 200
    assert key not in missing.text + invalid.text + accepted.text


def test_query_rate_limit_returns_retry_after():
    settings = Settings(
        _env_file=None,
        api_rate_limit_requests=1,
        api_rate_limit_window_seconds=60,
    )
    workflow = Mock()
    workflow.invoke.return_value = {
        "status": "success",
        "route_response": "sql",
        "final_answer": "answer",
        "workflow_error": "",
    }
    app = create_app(workflow=workflow, settings=settings)

    with TestClient(app) as client:
        assert client.post("/api/v1/query", json={"question": "first"}).status_code == 200
        limited = client.post("/api/v1/query", json={"question": "second"})

    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"


def test_query_concurrency_limit_rejects_without_queueing():
    settings = Settings(_env_file=None, api_max_concurrent_requests=1)
    app = create_app(workflow=Mock(), settings=settings)
    assert asyncio.run(app.state.concurrency_limiter.try_acquire()) is True

    with TestClient(app) as client:
        try:
            response = client.post("/api/v1/query", json={"question": "hello"})
        finally:
            asyncio.run(app.state.concurrency_limiter.release())

    assert response.status_code == 503
    assert response.headers["retry-after"] == "1"
