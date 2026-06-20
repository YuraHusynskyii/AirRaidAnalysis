"""Configurable data source loaders for alert datasets."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Literal
from urllib.error import URLError
from urllib.request import urlopen

import pandas as pd

from src.api_client import (
    load_alerts_from_alerts_in_ua,
    load_alerts_history_from_alerts_in_ua,
)
from src.config import AppConfig
from src.ingestion import load_alerts_csv, validate_raw_alerts

DataSourceType = Literal[
    "local_csv",
    "remote_csv",
    "alerts_in_ua_api",
    "alerts_in_ua_history",
]


def _apply_column_mapping(
    df: pd.DataFrame, column_map: dict[str, str]
) -> pd.DataFrame:
    """Rename source columns to project schema names.

    Args:
        df: Raw dataframe from external source.
        column_map: Mapping ``source_column -> target_column``.

    Returns:
        pd.DataFrame: Dataframe with renamed columns.
    """
    if not column_map:
        return df
    return df.rename(columns=column_map)


def fetch_remote_csv(url: str, timeout_seconds: int = 30) -> pd.DataFrame:
    """Download CSV content from a remote URL.

    Args:
        url: Remote CSV endpoint or ``file://`` URI.
        timeout_seconds: Network timeout in seconds.

    Returns:
        pd.DataFrame: Parsed CSV dataframe.

    Raises:
        RuntimeError: If download or parsing fails.
    """
    try:
        if url.startswith("file://"):
            local_path = Path(url.replace("file://", "", 1))
            return pd.read_csv(local_path)
        with urlopen(url, timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8")
        return pd.read_csv(StringIO(payload))
    except (URLError, OSError, ValueError, pd.errors.ParserError) as exc:
        raise RuntimeError(f"Failed to fetch remote CSV from {url}") from exc


def cache_raw_dataframe(df: pd.DataFrame, cache_path: Path) -> Path:
    """Persist fetched raw dataframe to local cache path.

    Args:
        df: Raw alerts dataframe.
        cache_path: Destination CSV path.

    Returns:
        Path: Written cache file path.

    Raises:
        RuntimeError: If cache write fails.
    """
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache_path, index=False)
    except Exception as exc:
        raise RuntimeError(f"Failed to cache raw dataset to {cache_path}") from exc
    return cache_path


def load_alerts_from_source(
    config: AppConfig,
    validate: bool = True,
) -> pd.DataFrame:
    """Load alerts using configured local or remote data source.

    Args:
        config: Application settings with data source configuration.
        validate: Whether to run data contract validation.

    Returns:
        pd.DataFrame: Loaded alerts dataframe.

    Raises:
        ValueError: If source configuration is invalid.
        RuntimeError: If loading or validation fails.
    """
    source_type: DataSourceType = config.data_source_type  # type: ignore[assignment]
    column_map = config.data_source_column_map or {}

    try:
        if source_type == "local_csv":
            return load_alerts_csv(
                file_path=config.raw_data_path,
                datetime_column=config.datetime_column,
                region_column=config.region_column,
                validate=validate,
            )

        if source_type == "remote_csv":
            if not config.data_source_url:
                raise ValueError("data_source_url must be set for remote_csv source.")
            raw_df = fetch_remote_csv(config.data_source_url)
            raw_df = _apply_column_mapping(raw_df, column_map)
            cache_raw_dataframe(raw_df, config.raw_data_path)
            raw_df[config.datetime_column] = pd.to_datetime(
                raw_df[config.datetime_column], errors="raise"
            )
            if validate:
                raw_df = validate_raw_alerts(
                    df=raw_df,
                    datetime_column=config.datetime_column,
                    region_column=config.region_column,
                )
            return raw_df

        if source_type == "alerts_in_ua_api":
            raw_df = load_alerts_from_alerts_in_ua(config=config)
            cache_raw_dataframe(raw_df, config.raw_data_path)
            if validate:
                raw_df = validate_raw_alerts(
                    df=raw_df,
                    datetime_column=config.datetime_column,
                    region_column=config.region_column,
                )
            return raw_df

        if source_type == "alerts_in_ua_history":
            raw_df = load_alerts_history_from_alerts_in_ua(config=config)
            cache_raw_dataframe(raw_df, config.raw_data_path)
            if validate:
                raw_df = validate_raw_alerts(
                    df=raw_df,
                    datetime_column=config.datetime_column,
                    region_column=config.region_column,
                )
            return raw_df

        raise ValueError(f"Unsupported data source type: {source_type}")
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Failed to load alerts from configured source.") from exc
