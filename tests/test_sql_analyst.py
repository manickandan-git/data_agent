import importlib

import pytest

from agents.sql_analyst import clean_sql_query, is_safe_sql, is_safe_sql_edge
from agentschemas import AgentSchema
from utils.sql_safety import validate_read_only_sql


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


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM users",
        "SELECT 'DELETE FROM users' AS harmless_text",
        "SELECT 1 /* UPDATE users SET is_active = false */",
        "WITH active_users AS (SELECT * FROM users) SELECT * FROM active_users;",
    ],
)
def test_deterministic_safety_allows_read_only_queries(query):
    assert validate_read_only_sql(query).is_safe is True


@pytest.mark.parametrize(
    ("query", "reason"),
    [
        ("", "empty"),
        ("DELETE FROM users", "Only SELECT"),
        ("SELECT 1; DELETE FROM users", "one SQL statement"),
        (
            "WITH deleted AS (DELETE FROM users RETURNING *) SELECT * FROM deleted",
            "DELETE",
        ),
        ("SELECT * INTO users_backup FROM users", "SELECT INTO"),
        ("SELECT user_id INTO users_backup FROM users", "SELECT INTO"),
        ("SELECT * FROM users FOR UPDATE", "UPDATE"),
        ("SELECT * FROM users FOR KEY SHARE", "Row-locking"),
        ("SELECT pg_sleep(60)", "PG_SLEEP"),
    ],
)
def test_deterministic_safety_blocks_unsafe_queries(query, reason):
    result = validate_read_only_sql(query)

    assert result.is_safe is False
    assert reason in result.reason


def test_unsafe_query_is_rejected_before_llm_judge(monkeypatch):
    def fail_if_called(_level):
        raise AssertionError("LLM judge must not run for mechanically unsafe SQL")

    sql_analyst_module = importlib.import_module("agents.sql_analyst")
    monkeypatch.setattr(sql_analyst_module, "pick_llm", fail_if_called)
    state = AgentSchema(
        messages=[],
        user_question="Remove all users",
        curated_question="Remove all users",
        generated_sql_query="DELETE FROM users",
    )

    result = is_safe_sql(state)

    assert result.is_safe == "No"
    assert "Only SELECT" in result.comments
