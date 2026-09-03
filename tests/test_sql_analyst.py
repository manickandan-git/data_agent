import pytest

from agents.sql_analyst import clean_sql_query, is_safe_sql_edge
from agentschemas import AgentSchema


@pytest.mark.parametrize(
    ("raw_query", "expected"),
    [
        ("SELECT 1", "SELECT 1"),
        ("```sql\nSELECT * FROM users;\n```", "SELECT * FROM users;"),
        ("```\nSELECT count(*) FROM rides;\n```", "SELECT count(*) FROM rides;"),
    ],
)
def test_clean_sql_query(raw_query, expected):
    assert clean_sql_query(raw_query) == expected


@pytest.mark.parametrize(
    ("answer", "expected_node"),
    [("Yes", "execute_sql_query"), ("No", "cancel_sql_query")],
)
def test_safety_edge_routes_to_expected_node(answer, expected_node):
    state = AgentSchema(messages=[], user_question="question", is_safe=answer)

    assert is_safe_sql_edge(state) == expected_node
