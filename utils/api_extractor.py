"""Bounded JSON API extraction with same-origin pagination."""

import time
from urllib.parse import urljoin, urlsplit

import requests

from config import get_config


class ExtractionError(ValueError):
    """Safe, user-facing extraction error; never includes response bodies or URLs."""


def origin(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ExtractionError("Only HTTPS URLs without embedded credentials are supported.")
    return parsed.scheme, parsed.hostname.lower(), parsed.port or 443


def at_path(payload, path):
    value = payload
    for key in path.split(".") if path else []:
        if not isinstance(value, dict) or key not in value:
            raise ExtractionError("Configured JSON path was not found in the response.")
        value = value[key]
    return value


def fetch_records(url, records_path="results", next_path="next", settings=None):
    settings = settings or get_config()
    first_origin = origin(url)
    headers = {"Accept": "application/json"}
    token = settings.etl_bearer_token
    if token and token.get_secret_value():
        if not settings.etl_auth_origin or origin(settings.etl_auth_origin) != first_origin:
            raise ExtractionError("Authenticated extraction requires a matching ETL_AUTH_ORIGIN.")
        headers["Authorization"] = "Bearer " + token.get_secret_value()

    rows, visited = [], set()
    with requests.Session() as session:
        # Do not inherit credentials from .netrc or send them through environment proxies.
        session.trust_env = False
        for _ in range(settings.etl_max_pages):
            if origin(url) != first_origin:
                raise ExtractionError("Cross-origin pagination is not permitted.")
            if url in visited:
                raise ExtractionError("Pagination cycle detected.")
            visited.add(url)
            payload = None
            for attempt in range(settings.etl_max_retries + 1):
                retryable = False
                try:
                    with session.get(url, headers=headers, timeout=settings.etl_timeout_seconds,
                                     allow_redirects=False) as response:
                        status = response.status_code
                        if status == 429 or 500 <= status <= 599:
                            retryable = True
                        elif 300 <= status <= 399:
                            raise ExtractionError("Redirects are disabled; supply the final HTTPS endpoint.")
                        elif status >= 400:
                            raise ExtractionError(f"API request failed with HTTP {status}.")
                        else:
                            try:
                                payload = response.json()
                            except ValueError:
                                raise ExtractionError("API response is not valid JSON.") from None
                except (requests.Timeout, requests.ConnectionError):
                    retryable = True
                except requests.RequestException:
                    raise ExtractionError("API request failed.") from None
                if not retryable:
                    break
                if attempt == settings.etl_max_retries:
                    raise ExtractionError("API request failed after bounded retries.")
                time.sleep(min(2 ** attempt, 8))

            records = at_path(payload, records_path)
            if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
                raise ExtractionError("Records must be a JSON array of objects.")
            rows.extend(records)
            if len(rows) > settings.etl_max_rows:
                raise ExtractionError("Extraction row limit exceeded; no output was saved.")
            if not next_path or (next_path == "next" and isinstance(payload, list)):
                return rows
            # An absent top-level 'next' means a single page, for backwards compatibility.
            next_url = payload.get("next") if next_path == "next" and isinstance(payload, dict) else at_path(payload, next_path)
            if next_url is None or next_url == "":
                return rows
            if not isinstance(next_url, str):
                raise ExtractionError("The next-page value must be a URL string or null.")
            url = urljoin(url, next_url)
        raise ExtractionError("Pagination page limit exceeded; no output was saved.")
