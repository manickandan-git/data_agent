from unittest.mock import Mock

from fastapi.testclient import TestClient

from data_agent.api import create_app
from data_agent.config import Settings


def test_health_endpoint():
    app = create_app(workflow=Mock(), settings=Settings(_env_file=None))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
