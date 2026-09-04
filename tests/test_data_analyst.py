import pytest
from langchain_core.messages import AIMessage, HumanMessage

import agents.data_analyst as module
from agents.data_analyst import route_edge
from agentschemas import DataSchema


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


@pytest.mark.parametrize("node_name,workflow_name", [
    ("sql_node", "sql_analyst"),
    ("etl_node", "etl_analyst"),
])
def test_child_workflow_output_is_normalized(monkeypatch, node_name, workflow_name):
    child = type("Child", (), {
        "invoke": staticmethod(lambda _state: {
            "status": "success",
            "final_answer": "Finished.",
            "workflow_error": "",
        })
    })()
    monkeypatch.setattr(module, workflow_name, child)
    state = DataSchema(messages=[HumanMessage(content="Do the work")])

    result = getattr(module, node_name)(state)

    assert result.status == "success"
    assert result.final_answer == "Finished."
    assert result.workflow_error == ""
    assert isinstance(result.messages[-1], AIMessage)
    assert result.messages[-1].content == "Finished."
