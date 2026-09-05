from unittest.mock import MagicMock

import pytest
import requests

from config import Settings
from utils.api_extractor import ExtractionError, fetch_records


def response(payload, status=200):
    result = MagicMock()
    result.__enter__.return_value = result
    result.status_code = status
    result.json.return_value = payload
    return result


@pytest.fixture
def transport(monkeypatch):
    session = MagicMock()
    session.__enter__.return_value = session
    monkeypatch.setattr("utils.api_extractor.requests.Session", lambda: session)
    monkeypatch.setattr("utils.api_extractor.time.sleep", lambda _: None)
    return session


def settings(**overrides):
    return Settings(_env_file=None, etl_bearer_token=None, **overrides)


def test_pagination_and_request_bounds(transport):
    transport.get.side_effect = [
        response({"results": [{"id": 1}], "next": "/items?page=2"}),
        response({"results": [{"id": 2}], "next": None}),
    ]
    assert fetch_records("https://example.test/items", settings=settings()) == [
        {"id": 1},
        {"id": 2},
    ]
    assert transport.get.call_count == 2
    assert transport.get.call_args.kwargs["allow_redirects"] is False
    assert transport.get.call_args.kwargs["timeout"] == 30
    assert transport.trust_env is False


@pytest.mark.parametrize("first", [requests.Timeout(), response(None, 429), response(None, 503)])
def test_transient_failure_retried(transport, first):
    transport.get.side_effect = [first, response({"results": []})]
    assert fetch_records("https://example.test/items", settings=settings()) == []
    assert transport.get.call_count == 2


def test_permanent_failure_not_retried(transport):
    transport.get.return_value = response(None, 401)
    with pytest.raises(ExtractionError, match="HTTP 401"):
        fetch_records("https://example.test/items", settings=settings())
    assert transport.get.call_count == 1


@pytest.mark.parametrize(
    "payload,path", [([{"id": 1}], ""), ({"data": {"items": [{"id": 1}]}}, "data.items")]
)
def test_alternate_record_paths(transport, payload, path):
    transport.get.return_value = response(payload)
    assert fetch_records("https://example.test/items", path, "", settings()) == [{"id": 1}]


@pytest.mark.parametrize(
    "payload,match",
    [
        ({"results": "bad"}, "array of objects"),
        ({"missing": []}, "JSON path"),
        ({"results": [], "next": "https://other.test/items"}, "Cross-origin"),
        ({"results": [], "next": "/items"}, "cycle"),
    ],
)
def test_malformed_data_and_bad_pagination(transport, payload, match):
    transport.get.return_value = response(payload)
    with pytest.raises(ExtractionError, match=match):
        fetch_records("https://example.test/items", settings=settings())


def test_auth_scope(transport):
    configured = Settings(
        _env_file=None, etl_bearer_token="secret", etl_auth_origin="https://example.test"
    )
    transport.get.return_value = response({"results": []})
    fetch_records("https://example.test/items", settings=configured)
    assert transport.get.call_args.kwargs["headers"]["Authorization"] == "Bearer secret"
    with pytest.raises(ExtractionError, match="matching ETL_AUTH_ORIGIN"):
        fetch_records("https://untrusted.test/items", settings=configured)
    assert transport.get.call_count == 1


def test_page_limit(transport):
    transport.get.return_value = response({"results": [], "next": "/other"})
    with pytest.raises(ExtractionError, match="page limit"):
        fetch_records("https://example.test/items", settings=settings(etl_max_pages=1))


def test_retry_limit_and_safe_error(transport):
    transport.get.side_effect = requests.ConnectionError("secret in url")
    with pytest.raises(ExtractionError, match="bounded retries") as error:
        fetch_records("https://example.test/items", settings=settings(etl_max_retries=1))
    assert "secret" not in str(error.value)
    assert transport.get.call_count == 2


def test_invalid_json(transport):
    transport.get.return_value = response(None)
    transport.get.return_value.json.side_effect = ValueError("private response")
    with pytest.raises(ExtractionError, match="not valid JSON"):
        fetch_records("https://example.test/items", settings=settings())


def test_row_limit(transport):
    transport.get.return_value = response({"results": [{"id": 1}, {"id": 2}]})
    with pytest.raises(ExtractionError, match="row limit"):
        fetch_records("https://example.test/items", settings=settings(etl_max_rows=1))


def test_redirects_are_not_followed(transport):
    transport.get.return_value = response(None, 302)
    with pytest.raises(ExtractionError, match="Redirects are disabled"):
        fetch_records("https://example.test/items", settings=settings())
    assert transport.get.call_count == 1
