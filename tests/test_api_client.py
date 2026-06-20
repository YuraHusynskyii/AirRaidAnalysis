"""Tests for alerts.in.ua API client."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.api_client import (
    _extract_alert_records,
    build_alerts_in_ua_history_url,
    fetch_alerts_in_ua_api,
    load_alerts_from_alerts_in_ua,
    load_alerts_history_from_alerts_in_ua,
    parse_alerts_in_ua_records,
)
from src.config import AppConfig


def test_parse_alerts_in_ua_records_filters_air_raid() -> None:
    """Parser keeps only air_raid records and maps schema columns."""
    fixture_path = Path("tests/fixtures/alerts_in_ua_active.json")
    records = json.loads(fixture_path.read_text(encoding="utf-8"))
    df = parse_alerts_in_ua_records(
        records=records,
        datetime_column="timestamp",
        region_column="region",
    )

    assert len(df) == 2
    assert set(df["region"]) == {"м. Київ", "Львівська область"}


def test_extract_alert_records_supports_list_payload() -> None:
    """Extractor accepts top-level list payloads."""
    payload = [{"started_at": "2024-06-01T10:00:00.000Z", "alert_type": "air_raid"}]
    records = _extract_alert_records(payload)
    assert len(records) == 1


@patch("src.api_client.urlopen")
def test_load_alerts_from_alerts_in_ua(mock_urlopen, tmp_path: Path) -> None:
    """API loader parses mocked JSON response."""
    fixture = Path("tests/fixtures/alerts_in_ua_active.json").read_text(encoding="utf-8")

    class _Response:
        def read(self) -> bytes:
            return fixture.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    mock_urlopen.return_value = _Response()
    config = AppConfig(
        data_source_type="alerts_in_ua_api",
        alerts_in_ua_token="test-token",
        raw_data_path=tmp_path / "alerts.csv",
    )

    df = load_alerts_from_alerts_in_ua(config=config)
    assert len(df) == 2


def test_fetch_alerts_in_ua_api_requires_token() -> None:
    """Missing API token raises ValueError."""
    with pytest.raises(ValueError, match="token is required"):
        fetch_alerts_in_ua_api(
            api_url="https://api.alerts.in.ua/v1/alerts/active.json",
            token="",
        )


def test_build_alerts_in_ua_history_url() -> None:
    """History URL builder follows alerts.in.ua pattern."""
    url = build_alerts_in_ua_history_url(
        base_url="https://api.alerts.in.ua/v1/regions",
        region_uid=16,
        period="month_ago",
    )
    assert url.endswith("/16/alerts/month_ago.json")


@patch("src.api_client.time.sleep")
@patch("src.api_client._fetch_json_url")
def test_fetch_alerts_in_ua_api_retries_on_http_error(
    mock_fetch,
    mock_sleep,
) -> None:
    """HTTP 429 responses trigger retry with exponential backoff."""
    from urllib.error import HTTPError

    mock_fetch.side_effect = [
        HTTPError("https://api", 429, "Too Many Requests", hdrs=None, fp=None),
        [{"started_at": "2024-06-01T10:00:00.000Z", "alert_type": "air_raid"}],
    ]

    payload = fetch_alerts_in_ua_api(
        api_url="https://api.alerts.in.ua/v1/alerts/active.json",
        token="token",
        max_retries=2,
        retry_backoff_seconds=0.01,
    )

    assert isinstance(payload, list)
    assert mock_fetch.call_count == 2
    mock_sleep.assert_called_once_with(0.01)


@patch("src.api_client.fetch_alerts_in_ua_history")
@patch("src.api_client.time.sleep")
def test_load_alerts_history_applies_rate_limit(mock_sleep, mock_fetch) -> None:
    """Multi-region history loading sleeps between region requests."""
    fixture = json.loads(
        Path("tests/fixtures/alerts_in_ua_history.json").read_text(encoding="utf-8")
    )
    mock_fetch.return_value = fixture
    config = AppConfig(
        alerts_in_ua_token="token",
        alerts_in_ua_region_uids=[16, 25],
        datetime_column="timestamp",
        region_column="region",
        api_rate_limit_seconds=0.25,
    )

    df = load_alerts_history_from_alerts_in_ua(config=config)
    assert len(df) >= 3
    mock_sleep.assert_called_once_with(0.25)


@patch("src.api_client.fetch_alerts_in_ua_api")
def test_load_alerts_history_from_alerts_in_ua(mock_fetch) -> None:
    """History loader combines records across configured region UIDs."""
    fixture = json.loads(
        Path("tests/fixtures/alerts_in_ua_history.json").read_text(encoding="utf-8")
    )
    mock_fetch.return_value = fixture
    config = AppConfig(
        alerts_in_ua_token="token",
        alerts_in_ua_region_uids=[16],
        datetime_column="timestamp",
        region_column="region",
    )

    df = load_alerts_history_from_alerts_in_ua(config=config)
    assert len(df) == 3
    assert df["region"].iloc[0] == "Луганська область"
