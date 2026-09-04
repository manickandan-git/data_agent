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
    extract_folder = tmp_path / "extract"
    response = FakeResponse({"results": [{"name": "bulbasaur", "id": 1}]})
    monkeypatch.setattr("utils.etl_tools.fetch_records", lambda *_: response.payload["results"])

    result = ETLTools(data_root=tmp_path).extract_load(
        "https://example.test/pokemon",
        str(extract_folder),
        "csv",
    )

    output_file = extract_folder / "extracted_data.csv"
    assert output_file.exists()
    assert pd.read_csv(output_file).to_dict("records") == [
        {"name": "bulbasaur", "id": 1}
    ]
    assert "Data successfully extracted" in result


def test_extract_load_reports_request_failure(monkeypatch, tmp_path):
    from utils.api_extractor import ExtractionError
    def fail(*_):
        raise ExtractionError("API request failed.")
    monkeypatch.setattr("utils.etl_tools.fetch_records", fail)

    result = ETLTools(data_root=tmp_path).extract_load(
        "https://example.test/pokemon",
        str(tmp_path / "extract"),
        "csv",
    )

    assert result == "Extraction failed: API request failed."


def test_extract_load_rejects_unsupported_format(monkeypatch, tmp_path):
    monkeypatch.setattr(
        requests,
        "get",
        lambda _url: FakeResponse({"results": [{"id": 1}]}),
    )

    result = ETLTools(data_root=tmp_path).extract_load(
        "https://example.test/items",
        str(tmp_path / "extract"),
        "xml",
    )

    assert result == "Unsupported format: xml"


def test_transform_load_context_reads_only_first_three_rows(tmp_path):
    source = tmp_path / "source.csv"
    pd.DataFrame({"value": [1, 2, 3, 4]}).to_csv(source, index=False)

    context = ETLTools(data_root=tmp_path).transform_load_context(str(source))

    assert "1" in context
    assert "3" in context
    assert "4" not in context


def test_transform_load_context_rejects_unknown_extension(tmp_path):
    source = Path(tmp_path) / "source.txt"
    source.write_text("unsupported", encoding="utf-8")

    assert ETLTools(data_root=tmp_path).transform_load_context(str(source)) == (
        "Unsupported file extension: .txt"
    )


def test_transform_load_applies_validated_plan(tmp_path):
    source = tmp_path / "source.csv"
    output = tmp_path / "transform" / "output"
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

    result = ETLTools(data_root=tmp_path).transform_load(
        str(source), str(output), "csv", plan
    )

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
        ETLTools(data_root=tmp_path).transform_load(
            str(source), str(tmp_path / "transform"), "csv", plan
        )


def test_transformation_plan_rejects_unsupported_operations():
    with pytest.raises(ValueError):
        FilterRule(column="name", operator="execute_python", value="import os")


def test_string_filter_is_literal_not_regex(tmp_path):
    source = tmp_path / "source.csv"
    output = tmp_path / "transform" / "output"
    pd.DataFrame({"value": ["a.b", "axb"]}).to_csv(source, index=False)
    plan = TransformationPlan(
        filters=[FilterRule(column="value", operator="contains", value=".")]
    )

    ETLTools(data_root=tmp_path).transform_load(str(source), str(output), "csv", plan)

    assert pd.read_csv(output / "transformed_data.csv")["value"].tolist() == ["a.b"]


def test_extract_load_blocks_output_outside_extract_directory(tmp_path):
    tools = ETLTools(data_root=tmp_path / "data")

    with pytest.raises(ValueError, match="outside the allowed directory"):
        tools.extract_load(
            "https://example.test/items",
            str(tmp_path / "outside"),
            "csv",
        )


def test_transform_load_blocks_input_outside_data_directory(tmp_path):
    data_root = tmp_path / "data"
    outside_file = tmp_path / "private.csv"
    pd.DataFrame({"secret": [1]}).to_csv(outside_file, index=False)

    with pytest.raises(ValueError, match="outside the allowed directory"):
        ETLTools(data_root=data_root).transform_load(
            str(outside_file),
            str(data_root / "transform"),
            "csv",
            TransformationPlan(),
        )


def test_transform_load_blocks_output_outside_transform_directory(tmp_path):
    source = tmp_path / "source.csv"
    pd.DataFrame({"value": [1]}).to_csv(source, index=False)

    with pytest.raises(ValueError, match="outside the allowed directory"):
        ETLTools(data_root=tmp_path).transform_load(
            str(source),
            str(tmp_path / "extract"),
            "csv",
            TransformationPlan(),
        )


def test_transform_load_refuses_to_overwrite_existing_file(tmp_path):
    source = tmp_path / "source.csv"
    output = tmp_path / "transform"
    output.mkdir()
    pd.DataFrame({"value": [1]}).to_csv(source, index=False)
    (output / "transformed_data.csv").write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        ETLTools(data_root=tmp_path).transform_load(
            str(source),
            str(output),
            "csv",
            TransformationPlan(),
        )
