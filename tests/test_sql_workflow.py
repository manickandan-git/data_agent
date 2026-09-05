import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage

from data_agent.agentschemas import AgentSchema, JudgeSchema
from data_agent.agentschemas.question import QuestionReview


@pytest.fixture
def workflow(monkeypatch):
    module = importlib.import_module("data_agent.agents.sql_analyst")
    settings = SimpleNamespace(
        require_database_url=lambda: "test-dsn",
        database_schema="public",
        sql_row_limit=10,
        sql_timeout_seconds=30,
        sql_categorical_columns={"payments": ["payment_method"]},
        sql_categorical_value_limit=50,
    )
    database = SimpleNamespace(
        connect=AsyncMock(),
        close=AsyncMock(),
        schema_details=AsyncMock(
            return_value=(
                "Table: users; Column: user_id integer\nTable: payments; "
                "Column: payment_method text\nAllowed values for payment_method: "
                "'credit_card', 'cash'"
            )
        ),
        execute_read_only_sql=AsyncMock(return_value="[(1,)]"),
    )
    generation = Mock()
    generation.invoke.return_value = AIMessage(content="SELECT user_id FROM users LIMIT 10")
    summary = Mock()
    summary.invoke.return_value = AIMessage(content="One user found.")
    judge = Mock()
    judge.invoke.return_value = JudgeSchema(answer="Yes", comments="Relevant")
    monkeypatch.setattr(module, "get_config", lambda: settings)
    monkeypatch.setattr(module, "AsyncDatabaseUtil", lambda *_: database)
    monkeypatch.setattr(
        module, "pick_llm", lambda level: generation if level == "medium" else summary
    )
    question_validator = Mock()
    question_validator.invoke.return_value = QuestionReview(
        status="clear", message="The users table supports the request."
    )

    def module_test_models(level, schema):
        return question_validator if schema is QuestionReview else judge

    monkeypatch.setattr(module, "structured_llm", module_test_models)
    return module, database, generation, summary, judge


def test_success_generates_once_and_does_not_duplicate_messages(workflow):
    module, database, generation, summary, judge = workflow
    result = module.sql_analyst.invoke({"messages": [], "user_question": "Show users"})
    assert result["final_answer"] == "One user found."
    assert result["status"] == "success"
    assert len(result["messages"]) == 2
    generation.invoke.assert_called_once()
    summary.invoke.assert_called_once()
    database.schema_details.assert_awaited_once_with(
        "public",
        include_samples=False,
        categorical_columns={"payments": ["payment_method"]},
        categorical_value_limit=50,
    )
    database.execute_read_only_sql.assert_awaited_once()
    assert database.close.await_count == 2


@pytest.mark.parametrize(
    "result_value,expected",
    [
        (None, "database query failed"),
        ("[]", "No matching records"),
    ],
)
def test_failed_and_empty_results_skip_summary(workflow, result_value, expected):
    module, database, _, summary, _ = workflow
    database.execute_read_only_sql.return_value = result_value
    result = module.sql_analyst.invoke({"messages": [], "user_question": "Show users"})
    assert expected in result["final_answer"]
    summary.invoke.assert_not_called()


def test_schema_failure_stops_before_generation(workflow):
    module, database, generation, summary, _ = workflow
    database.schema_details.return_value = "Error: no connection"
    result = module.sql_analyst.invoke({"messages": [], "user_question": "Show users"})
    assert "schema could not be loaded" in result["final_answer"]
    generation.invoke.assert_not_called()
    database.execute_read_only_sql.assert_not_awaited()
    database.close.assert_awaited_once()


def test_rejected_sql_never_reaches_database(workflow):
    module, database, generation, _, judge = workflow
    generation.invoke.return_value = AIMessage(content="DELETE FROM users")
    result = module.sql_analyst.invoke({"messages": [], "user_question": "Delete users"})
    assert "not executed" in result["final_answer"]
    judge.invoke.assert_not_called()
    database.execute_read_only_sql.assert_not_awaited()


def test_empty_question_never_connects(workflow):
    module, database, _, _, _ = workflow
    result = module.sql_analyst.invoke({"messages": [], "user_question": "  "})
    assert "provide a database question" in result["final_answer"]
    database.connect.assert_not_awaited()


def test_execution_requires_approval(workflow):
    module, database, _, _, _ = workflow
    result = module.execute_sql_query(
        AgentSchema(
            messages=[],
            user_question="Show users",
            generated_sql_query="SELECT 1",
        )
    )
    assert result.workflow_error
    database.connect.assert_not_awaited()


@pytest.mark.parametrize(
    "status,message",
    [
        ("ambiguous", "Do you mean highest rating or most completed rides?"),
        ("unsupported", "This database does not contain weather observations."),
    ],
)
def test_question_review_stops_before_sql(workflow, status, message):
    module, database, generation, summary, judge = workflow
    validator = module.structured_llm("medium", QuestionReview)
    validator.invoke.return_value = QuestionReview(status=status, message=message)
    result = module.sql_analyst.invoke({"messages": [], "user_question": "Who is best?"})
    assert result["question_status"] == status
    assert result["status"] == ("needs_clarification" if status == "ambiguous" else "rejected")
    assert result["final_answer"] == message
    assert result["generated_sql_query"] == ""
    assert len(result["messages"]) == 2
    generation.invoke.assert_not_called()
    summary.invoke.assert_not_called()
    judge.invoke.assert_not_called()
    database.execute_read_only_sql.assert_not_awaited()


@pytest.mark.parametrize(
    "invalid",
    [None, {"status": "clear", "message": "   "}, {"status": "maybe", "message": "unknown"}],
)
def test_question_validation_fails_closed(workflow, invalid):
    module, database, generation, _, _ = workflow
    module.structured_llm("medium", QuestionReview).invoke.return_value = invalid
    result = module.sql_analyst.invoke({"messages": [], "user_question": "Show users"})
    assert result["question_status"] == "error"
    assert "could not be validated" in result["final_answer"]
    generation.invoke.assert_not_called()
    database.execute_read_only_sql.assert_not_awaited()


def test_question_review_receives_schema_and_preserves_request(workflow):
    module, _, generation, _, _ = workflow
    question = "Show users with user_id greater than 20"
    result = module.sql_analyst.invoke({"messages": [], "user_question": question})
    prompt = module.structured_llm("medium", QuestionReview).invoke.call_args.args[0]
    assert "Column: user_id integer" in prompt
    assert question in prompt
    assert result["curated_question"] == question
    assert question in generation.invoke.call_args.args[0]


def test_categorical_values_ground_generation_and_judgment(workflow):
    module, _, generation, _, judge = workflow
    generation.invoke.return_value = AIMessage(
        content=("SELECT SUM(amount) FROM payments WHERE payment_method = 'credit_card'")
    )
    result = module.sql_analyst.invoke(
        {
            "messages": [],
            "user_question": "What is the sum of all credit card transactions?",
        }
    )
    generation_prompt = generation.invoke.call_args.args[0]
    judge_prompt = judge.invoke.call_args.args[0]
    value_context = "Allowed values for payment_method: 'credit_card', 'cash'"
    assert value_context in generation_prompt
    assert "Never replace underscores with spaces" in generation_prompt
    assert value_context in judge_prompt
    assert "payment_method = 'credit_card'" in result["generated_sql_query"]


def test_all_transactions_does_not_require_payment_status_clarification(workflow):
    module, database, generation, _, _ = workflow
    question = "What is the sum of all credit card transactions for April 2026?"

    result = module.sql_analyst.invoke({"messages": [], "user_question": question})

    validator = module.structured_llm("medium", QuestionReview)
    validation_prompt = validator.invoke.call_args.args[0]
    normalized_prompt = " ".join(validation_prompt.split())
    assert 'Words such as "all" mean all' in validation_prompt
    assert "without adding a payment_status predicate" in normalized_prompt
    assert result["question_status"] == "clear"
    generation.invoke.assert_called_once()
    database.execute_read_only_sql.assert_awaited_once()
