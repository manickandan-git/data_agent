import pytest

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
