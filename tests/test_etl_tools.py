from pathlib import Path

import pandas as pd
import requests

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


def test_execute_code_captures_output():
    assert ETLTools().execute_code("print(sum([1, 2, 3]))") == "6\n"


def test_execute_code_blocks_unapproved_import():
    result = ETLTools().execute_code("import subprocess")

    assert result.startswith("Failed to execute code: ImportError")


def test_execute_code_rejects_oversized_input():
    result = ETLTools().execute_code("x" * 10001)

    assert result == "Error: Code exceeds maximum length (10000 characters)"
