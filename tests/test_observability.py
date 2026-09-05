import json
import logging

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from data_agent.agentschemas import DataSchema
from data_agent.config import Settings
from data_agent.utils.observability import (
    configure_observability,
    configure_telemetry,
    log_event,
    observed_node,
)


def test_json_event_contains_safe_operational_fields(capsys):
    configure_observability("INFO", json_logs=True)

    log_event(
        logging.INFO,
        "workflow.test",
        workflow="sql",
        node="generate",
        run_id="test-run",
        duration_ms=12.5,
    )

    event = json.loads(capsys.readouterr().err)
    assert event["event"] == "workflow.test"
    assert event["workflow"] == "sql"
    assert event["run_id"] == "test-run"
    assert event["duration_ms"] == 12.5


def test_observed_node_assigns_correlation_id_and_logs_completion(capsys):
    configure_observability("INFO", json_logs=True)
    state = DataSchema(messages=[])

    result = observed_node("data", "test_node", lambda value: value)(state)

    events = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert result.run_id
    assert [event["event"] for event in events] == [
        "workflow.node.started",
        "workflow.node.completed",
    ]
    assert {event["run_id"] for event in events} == {result.run_id}
    assert events[-1]["duration_ms"] >= 0


def test_failed_node_logs_only_exception_type(capsys):
    configure_observability("INFO", json_logs=True)

    def fail(_state):
        raise RuntimeError("secret payload")

    with pytest.raises(RuntimeError, match="secret payload"):
        observed_node("etl", "test_node", fail)(DataSchema(messages=[]))

    logged = capsys.readouterr().err
    event = json.loads(logged.splitlines()[-1])
    assert event["event"] == "workflow.node.failed"
    assert event["exception_type"] == "RuntimeError"
    assert "secret payload" not in logged


def test_telemetry_is_disabled_by_default():
    assert configure_telemetry(Settings(_env_file=None)) is None


def test_workflow_span_contains_only_safe_operational_attributes():
    exporter = InMemorySpanExporter()
    settings = Settings(
        _env_file=None,
        otel_enabled=True,
        otel_exporter_endpoint="http://collector.test/v1/traces",
        app_environment="test",
    )
    provider = configure_telemetry(settings, span_exporter=exporter)
    state = DataSchema(messages=[])

    observed_node("sql", "generate", lambda value: value)(state)

    provider.force_flush()
    span = exporter.get_finished_spans()[0]
    assert span.name == "sql.generate"
    assert span.attributes == {
        "data_agent.workflow": "sql",
        "data_agent.node": "generate",
        "data_agent.run_id": state.run_id,
    }
    assert span.resource.attributes["service.name"] == "data-agent"
    assert span.resource.attributes["deployment.environment.name"] == "test"
    provider.shutdown()


def test_json_logs_include_active_trace_correlation(capsys):
    exporter = InMemorySpanExporter()
    settings = Settings(
        _env_file=None,
        otel_enabled=True,
        otel_exporter_endpoint="http://collector.test/v1/traces",
    )
    provider = configure_telemetry(settings, span_exporter=exporter)
    configure_observability("INFO", json_logs=True)

    with provider.get_tracer("test").start_as_current_span("test-span"):
        log_event(logging.INFO, "workflow.test", run_id="test-run")

    event = json.loads(capsys.readouterr().err)
    assert len(event["trace_id"]) == 32
    assert len(event["span_id"]) == 16
    provider.shutdown()


def test_failed_span_does_not_export_exception_message():
    exporter = InMemorySpanExporter()
    settings = Settings(
        _env_file=None,
        otel_enabled=True,
        otel_exporter_endpoint="http://collector.test/v1/traces",
    )
    provider = configure_telemetry(settings, span_exporter=exporter)

    with pytest.raises(RuntimeError):
        observed_node(
            "etl",
            "extract",
            lambda _state: (_ for _ in ()).throw(RuntimeError("secret payload")),
        )(DataSchema(messages=[]))

    provider.force_flush()
    span = exporter.get_finished_spans()[0]
    assert span.status.status_code.name == "ERROR"
    assert span.attributes["exception.type"] == "RuntimeError"
    assert "secret payload" not in str(span.to_json())
    provider.shutdown()
