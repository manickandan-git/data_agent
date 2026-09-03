import pytest
from pydantic import ValidationError

from agentschemas import DataSchema, JudgeSchema, RouterSchema


def test_data_schema_defaults_to_no_route():
    state = DataSchema(messages=[])

    assert state.route_response == ""


@pytest.mark.parametrize("route", ["sql", "etl"])
def test_router_schema_accepts_supported_routes(route):
    result = RouterSchema(answer=route, comments="classified")

    assert result.answer == route


def test_router_schema_rejects_unknown_route():
    with pytest.raises(ValidationError):
        RouterSchema(answer="other", comments="unsupported")


@pytest.mark.parametrize("answer", ["Yes", "No"])
def test_judge_schema_accepts_supported_answers(answer):
    assert JudgeSchema(answer=answer, comments="checked").answer == answer
