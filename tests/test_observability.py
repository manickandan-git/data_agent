import json
import logging

import pytest

from agentschemas import DataSchema
from utils.observability import (
    configure_observability,
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

    events = [
        json.loads(line)
        for line in capsys.readouterr().err.splitlines()
    ]
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
