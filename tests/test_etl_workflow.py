import importlib
from types import SimpleNamespace
from unittest.mock import Mock

from langchain_core.messages import AIMessage

from data_agent.agentschemas import ETLSchema


def test_llm_node_sets_standard_success_output(monkeypatch):
    module = importlib.import_module("data_agent.agents.etl_analyst")
    bound = Mock()
    bound.invoke.return_value = AIMessage(content="Extraction completed.")
    client = Mock()
    client.bind_tools.return_value = bound
    monkeypatch.setattr(module, "pick_llm", lambda _level: client)

    result = module.llm_node(ETLSchema(messages=[]))

    assert result.status == "success"
    assert result.final_answer == "Extraction completed."
    assert result.workflow_error == ""


def test_llm_node_converts_model_failure_to_standard_error(monkeypatch):
    module = importlib.import_module("data_agent.agents.etl_analyst")

    def fail(_level):
        raise RuntimeError("provider details")

    monkeypatch.setattr(module, "pick_llm", fail)

    result = module.llm_node(ETLSchema(messages=[]))

    assert result.status == "error"
    assert result.final_answer == result.workflow_error
    assert "provider details" not in result.workflow_error


def test_tool_failure_sets_error_and_stops_workflow(monkeypatch):
    module = importlib.import_module("data_agent.agents.etl_analyst")
    fake_tool = SimpleNamespace(
        name="extract",
        invoke=lambda _arguments: "Extraction failed: unavailable",
    )
    monkeypatch.setattr(module, "tools", [fake_tool])
    call = AIMessage(
        content="",
        tool_calls=[{"name": "extract", "args": {}, "id": "call-1"}],
    )

    result = module.tool_node(ETLSchema(messages=[call]))

    assert result.status == "error"
    assert result.workflow_error == "Extraction failed: unavailable"
    assert module.tool_result_edge(result) == "end"


def test_successful_tool_result_returns_to_model(monkeypatch):
    module = importlib.import_module("data_agent.agents.etl_analyst")
    fake_tool = SimpleNamespace(
        name="extract",
        invoke=lambda _arguments: "Data successfully extracted.",
    )
    monkeypatch.setattr(module, "tools", [fake_tool])
    call = AIMessage(
        content="",
        tool_calls=[{"name": "extract", "args": {}, "id": "call-1"}],
    )

    result = module.tool_node(ETLSchema(messages=[call]))

    assert result.status == "pending"
    assert module.tool_result_edge(result) == "llm_node"
