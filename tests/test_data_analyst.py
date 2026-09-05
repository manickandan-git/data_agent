import pytest
from langchain_core.messages import AIMessage, HumanMessage

import data_agent.agents.data_analyst as module
from data_agent.agents.data_analyst import route_edge
from data_agent.agentschemas import DataSchema, RouterSchema


@pytest.mark.parametrize(
    ("route", "expected_node"),
    [("sql", "sql_node"), ("etl", "etl_node")],
)
def test_route_edge_selects_expected_agent(route, expected_node):
    state = DataSchema(messages=[], route_response=route)

    assert route_edge(state) == expected_node


def test_route_edge_rejects_unknown_route():
    state = DataSchema(messages=[], route_response="unknown")

    with pytest.raises(ValueError, match="Invalid route response"):
        route_edge(state)


def test_router_node_selects_route(monkeypatch):
    validator = type(
        "Validator",
        (),
        {
            "invoke": staticmethod(
                lambda _message: RouterSchema(answer="sql", comments="database question")
            )
        },
    )()
    monkeypatch.setattr(module, "structured_llm", lambda *_args: validator)
    state = DataSchema(messages=[HumanMessage(content="Count the rides")])

    result = module.router_node(state)

    assert result.route_response == "sql"
    assert result.status == "pending"


def test_router_node_returns_safe_error(monkeypatch):
    def fail(*_args):
        raise RuntimeError("provider secret")

    monkeypatch.setattr(module, "structured_llm", fail)
    state = DataSchema(messages=[HumanMessage(content="Count the rides")])

    result = module.router_node(state)

    assert result.status == "error"
    assert result.final_answer == result.workflow_error
    assert "provider secret" not in result.workflow_error
    assert route_edge(result) == "end"


@pytest.mark.parametrize(
    "node_name,workflow_name",
    [("sql_node", "sql_analyst"), ("etl_node", "etl_analyst")],
)
def test_child_workflow_exception_is_normalized(monkeypatch, node_name, workflow_name):
    child = type(
        "Child",
        (),
        {"invoke": staticmethod(lambda _state: (_ for _ in ()).throw(RuntimeError("secret")))},
    )()
    monkeypatch.setattr(module, workflow_name, child)

    result = getattr(module, node_name)(DataSchema(messages=[HumanMessage(content="Do the work")]))

    assert result.status == "error"
    assert result.final_answer == result.workflow_error
    assert "secret" not in result.workflow_error


@pytest.mark.parametrize(
    "node_name,workflow_name",
    [
        ("sql_node", "sql_analyst"),
        ("etl_node", "etl_analyst"),
    ],
)
def test_child_workflow_output_is_normalized(monkeypatch, node_name, workflow_name):
    child = type(
        "Child",
        (),
        {
            "invoke": staticmethod(
                lambda _state: {
                    "status": "success",
                    "final_answer": "Finished.",
                    "workflow_error": "",
                }
            )
        },
    )()
    monkeypatch.setattr(module, workflow_name, child)
    state = DataSchema(messages=[HumanMessage(content="Do the work")])

    result = getattr(module, node_name)(state)

    assert result.status == "success"
    assert result.final_answer == "Finished."
    assert result.workflow_error == ""
    assert isinstance(result.messages[-1], AIMessage)
    assert result.messages[-1].content == "Finished."
