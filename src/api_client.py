"""Production API client for alerts.in.ua."""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from src.config import AppConfig


def _extract_alert_records(payload: Any) -> list[dict[str, Any]]:
    """Normalize API payload to a list of alert records.

    Args:
        payload: Parsed JSON payload from alerts.in.ua API.

    Returns:
        list[dict[str, Any]]: Alert record dictionaries.
    """
    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, dict)]
    if isinstance(payload, dict):
        for key in ("alerts", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [record for record in value if isinstance(record, dict)]
    raise ValueError("Unsupported alerts.in.ua payload format.")


def parse_alerts_in_ua_records(
    records: list[dict[str, Any]],
    datetime_column: str,
    region_column: str,
    alert_type_filter: str = "air_raid",
) -> pd.DataFrame:
    """Convert alerts.in.ua records to project schema dataframe.

    Args:
        records: Alert records from API.
        datetime_column: Target datetime column name.
        region_column: Target region column name.
        alert_type_filter: Alert type to keep (default: air_raid).

    Returns:
        pd.DataFrame: Normalized alerts dataframe.

    Raises:
        ValueError: If no valid records remain after filtering.
    """
    rows: list[dict[str, str]] = []
    for record in records:
        if record.get("alert_type") != alert_type_filter:
            continue
        started_at = record.get("started_at")
        region = record.get("location_oblast") or record.get("location_title")
        if not started_at or not region:
            continue
        rows.append({datetime_column: started_at, region_column: str(region)})

    if not rows:
        raise ValueError("No air_raid records found in alerts.in.ua response.")

    dataframe = pd.DataFrame(rows)
    dataframe[datetime_column] = pd.to_datetime(dataframe[datetime_column], utc=True)
    return dataframe


def _fetch_json_url(request_url: str, timeout_seconds: int) -> Any:
    """Fetch and parse JSON from a URL.

    Args:
        request_url: Fully qualified request URL.
        timeout_seconds: Network timeout in seconds.

    Returns:
        Any: Parsed JSON payload.

    Raises:
        HTTPError: On non-2xx HTTP responses.
        URLError: On network failures.
        json.JSONDecodeError: If response is not valid JSON.
    """
    with urlopen(request_url, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_alerts_in_ua_api(
    api_url: str,
    token: str,
    timeout_seconds: int = 30,
    max_retries: int = 3,
    retry_backoff_seconds: float = 1.0,
) -> Any:
    """Fetch alerts.in.ua JSON payload with retry/backoff.

    Args:
        api_url: Base API endpoint URL.
        token: Personal API token.
        timeout_seconds: Network timeout in seconds.
        max_retries: Maximum retry attempts after the first request.
        retry_backoff_seconds: Base delay for exponential backoff.

    Returns:
        Any: Parsed JSON payload.

    Raises:
        ValueError: If token is missing.
        RuntimeError: If request or JSON parsing fails after retries.
    """
    if not token:
        raise ValueError(
            "alerts.in.ua token is required. Set AIRRAID_ALERTS_IN_UA_TOKEN."
        )

    query = urlencode({"token": token})
    separator = "&" if "?" in api_url else "?"
    request_url = f"{api_url}{separator}{query}"

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return _fetch_json_url(request_url, timeout_seconds=timeout_seconds)
        except HTTPError as exc:
            last_error = exc
            retryable = exc.code in (429, 500, 502, 503, 504)
            if retryable and attempt < max_retries:
                time.sleep(retry_backoff_seconds * (2**attempt))
                continue
            raise RuntimeError(f"Failed to fetch alerts.in.ua API: {api_url}") from exc
        except (URLError, OSError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(retry_backoff_seconds * (2**attempt))
                continue
            raise RuntimeError(f"Failed to fetch alerts.in.ua API: {api_url}") from exc

    raise RuntimeError(f"Failed to fetch alerts.in.ua API: {api_url}") from last_error


def load_alerts_from_alerts_in_ua(config: AppConfig) -> pd.DataFrame:
    """Load and normalize alerts from alerts.in.ua production API.

    Args:
        config: Application settings with API token and URL.

    Returns:
        pd.DataFrame: Normalized alerts dataframe.

    Raises:
        RuntimeError: If API loading or parsing fails.
    """
    try:
        payload = fetch_alerts_in_ua_api(
            api_url=config.alerts_in_ua_api_url,
            token=config.alerts_in_ua_token or "",
            max_retries=config.api_max_retries,
            retry_backoff_seconds=config.api_retry_backoff_seconds,
        )
        records = _extract_alert_records(payload)
        dataframe = parse_alerts_in_ua_records(
            records=records,
            datetime_column=config.datetime_column,
            region_column=config.region_column or "region",
        )
        return dataframe
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Failed to load alerts from alerts.in.ua API.") from exc


def build_alerts_in_ua_history_url(
    base_url: str,
    region_uid: int,
    period: str,
) -> str:
    """Build alerts.in.ua regional history endpoint URL.

    Args:
        base_url: Base URL, e.g. ``https://api.alerts.in.ua/v1/regions``.
        region_uid: Region UID from alerts.in.ua docs.
        period: History period slug, e.g. ``month_ago``.

    Returns:
        str: Fully qualified history endpoint without token query param.
    """
    return f"{base_url.rstrip('/')}/{region_uid}/alerts/{period}.json"


def fetch_alerts_in_ua_history(
    base_url: str,
    token: str,
    region_uid: int,
    period: str,
    timeout_seconds: int = 30,
    max_retries: int = 3,
    retry_backoff_seconds: float = 1.0,
) -> Any:
    """Fetch regional alert history from alerts.in.ua API.

    Args:
        base_url: Base URL for regions history API.
        token: Personal API token.
        region_uid: Region UID.
        period: History period slug.
        timeout_seconds: Network timeout in seconds.
        max_retries: Maximum retry attempts after the first request.
        retry_backoff_seconds: Base delay for exponential backoff.

    Returns:
        Any: Parsed JSON payload.

    Raises:
        RuntimeError: If request fails for the given region.
    """
    history_url = build_alerts_in_ua_history_url(
        base_url=base_url,
        region_uid=region_uid,
        period=period,
    )
    try:
        return fetch_alerts_in_ua_api(
            api_url=history_url,
            token=token,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to fetch alerts.in.ua history for region {region_uid}."
        ) from exc


def load_alerts_history_from_alerts_in_ua(config: AppConfig) -> pd.DataFrame:
    """Load alert history for configured regions from alerts.in.ua API.

    Args:
        config: Application settings with token, region UIDs and period.

    Returns:
        pd.DataFrame: Combined normalized alerts dataframe.

    Raises:
        ValueError: If configuration is invalid.
        RuntimeError: If loading fails for all configured regions.
    """
    token = config.alerts_in_ua_token or ""
    if not token:
        raise ValueError(
            "alerts.in.ua token is required. Set AIRRAID_ALERTS_IN_UA_TOKEN."
        )
    if not config.alerts_in_ua_region_uids:
        raise ValueError("alerts_in_ua_region_uids must contain at least one UID.")

    frames: list[pd.DataFrame] = []
    errors: list[str] = []

    for index, region_uid in enumerate(config.alerts_in_ua_region_uids):
        if index > 0 and config.api_rate_limit_seconds > 0:
            time.sleep(config.api_rate_limit_seconds)
        try:
            payload = fetch_alerts_in_ua_history(
                base_url=config.alerts_in_ua_history_base_url,
                token=token,
                region_uid=region_uid,
                period=config.alerts_in_ua_history_period,
                max_retries=config.api_max_retries,
                retry_backoff_seconds=config.api_retry_backoff_seconds,
            )
            records = _extract_alert_records(payload)
            frames.append(
                parse_alerts_in_ua_records(
                    records=records,
                    datetime_column=config.datetime_column,
                    region_column=config.region_column or "region",
                )
            )
        except Exception as exc:
            errors.append(f"region={region_uid}: {exc}")

    if not frames:
        details = "; ".join(errors) if errors else "no regions loaded"
        raise RuntimeError(f"Failed to load alerts.in.ua history ({details}).")

    combined = pd.concat(frames, ignore_index=True)
    duplicate_columns = [config.datetime_column, config.region_column or "region"]
    combined = combined.drop_duplicates(subset=duplicate_columns, keep="first")
    return combined.sort_values(config.datetime_column).reset_index(drop=True)
