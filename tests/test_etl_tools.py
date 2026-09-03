from pathlib import Path

import pandas as pd
import pytest
import requests

from agentschemas import FilterRule, SortRule, TransformationPlan
from utils.etl_tools import ETLTools


class FakeResponse:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


def test_extract_load_writes_api_results_to_csv(monkeypatch, tmp_path):
    response = FakeResponse({"results": [{"name": "bulbasaur", "id": 1}]})
    monkeypatch.setattr(requests, "get", lambda _url: response)

    result = ETLTools().extract_load(
        "https://example.test/pokemon",
        str(tmp_path),
        "csv",
    )

    output_file = tmp_path / "extracted_data.csv"
    assert output_file.exists()
    assert pd.read_csv(output_file).to_dict("records") == [
        {"name": "bulbasaur", "id": 1}
    ]
    assert "Data successfully extracted" in result


def test_extract_load_reports_request_failure(monkeypatch, tmp_path):
    error = requests.RequestException("service unavailable")
    monkeypatch.setattr(
        requests,
        "get",
        lambda _url: FakeResponse(error=error),
    )

    result = ETLTools().extract_load(
        "https://example.test/pokemon",
        str(tmp_path),
        "csv",
    )

    assert result == "An error occurred during extraction: service unavailable"


def test_extract_load_rejects_unsupported_format(monkeypatch, tmp_path):
    monkeypatch.setattr(
        requests,
        "get",
        lambda _url: FakeResponse({"results": [{"id": 1}]}),
    )

    result = ETLTools().extract_load(
        "https://example.test/items",
        str(tmp_path),
        "xml",
    )

    assert result == "Unsupported format: xml"


def test_transform_load_context_reads_only_first_three_rows(tmp_path):
    source = tmp_path / "source.csv"
    pd.DataFrame({"value": [1, 2, 3, 4]}).to_csv(source, index=False)

    context = ETLTools().transform_load_context(str(source))

    assert "1" in context
    assert "3" in context
    assert "4" not in context


def test_transform_load_context_rejects_unknown_extension(tmp_path):
    source = Path(tmp_path) / "source.txt"

    assert ETLTools().transform_load_context(str(source)) == (
        "Unsupported file extension: .txt"
    )


def test_transform_load_applies_validated_plan(tmp_path):
    source = tmp_path / "source.csv"
    output = tmp_path / "output"
    pd.DataFrame(
        {
            "name": ["venusaur", "bulbasaur", "ivysaur", "bulbasaur"],
            "score": [3, 1, 2, 1],
        }
    ).to_csv(source, index=False)
    plan = TransformationPlan(
        filters=[
            FilterRule(
                column="name",
                operator="in",
                value=["bulbasaur", "ivysaur"],
            )
        ],
        select_columns=["name", "score"],
        rename_columns={"score": "rank"},
        drop_duplicates_on=["name"],
        sort=[SortRule(column="rank", ascending=False)],
        limit=2,
    )

    result = ETLTools().transform_load(str(source), str(output), "csv", plan)

    transformed = pd.read_csv(output / "transformed_data.csv")
    assert transformed.to_dict("records") == [
        {"name": "ivysaur", "rank": 2},
        {"name": "bulbasaur", "rank": 1},
    ]
    assert "Transformed 2 rows" in result


def test_transform_load_rejects_unknown_columns(tmp_path):
    source = tmp_path / "source.csv"
    pd.DataFrame({"name": ["bulbasaur"]}).to_csv(source, index=False)
    plan = TransformationPlan(
        filters=[FilterRule(column="password", operator="eq", value="secret")]
    )

    with pytest.raises(ValueError, match="Unknown columns"):
        ETLTools().transform_load(str(source), str(tmp_path / "output"), "csv", plan)


def test_transformation_plan_rejects_unsupported_operations():
    with pytest.raises(ValueError):
        FilterRule(column="name", operator="execute_python", value="import os")


def test_string_filter_is_literal_not_regex(tmp_path):
    source = tmp_path / "source.csv"
    output = tmp_path / "output"
    pd.DataFrame({"value": ["a.b", "axb"]}).to_csv(source, index=False)
    plan = TransformationPlan(
        filters=[FilterRule(column="value", operator="contains", value=".")]
    )

    ETLTools().transform_load(str(source), str(output), "csv", plan)

    assert pd.read_csv(output / "transformed_data.csv")["value"].tolist() == ["a.b"]
