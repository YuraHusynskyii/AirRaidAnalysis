"""Tests for configurable data source loading."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.config import AppConfig
from src.data_source import cache_raw_dataframe, load_alerts_from_source


def test_load_alerts_from_local_source() -> None:
    """Local CSV source loads fixture dataset."""
    config = AppConfig(
        data_source_type="local_csv",
        raw_data_path=Path("data/samples/sample_alerts.csv"),
    )
    df = load_alerts_from_source(config=config)
    assert len(df) == 55
    assert {"timestamp", "region"}.issubset(df.columns)


def test_load_alerts_from_remote_file_uri(tmp_path: Path) -> None:
    """Remote source can load from file:// URI and cache locally."""
    source_path = tmp_path / "remote_alerts.csv"
    cache_path = tmp_path / "cache_alerts.csv"
    pd.DataFrame(
        {
            "timestamp": ["2024-06-01 10:00:00", "2024-06-01 11:00:00"],
            "region": ["Kyiv", "Lviv"],
        }
    ).to_csv(source_path, index=False)

    config = AppConfig(
        data_source_type="remote_csv",
        data_source_url=f"file://{source_path}",
        raw_data_path=cache_path,
    )
    df = load_alerts_from_source(config=config)

    assert len(df) == 2
    assert cache_path.exists()


def test_remote_source_without_url_raises() -> None:
    """Remote source without URL raises ValueError."""
    config = AppConfig(data_source_type="remote_csv", data_source_url=None)
    with pytest.raises(ValueError, match="data_source_url"):
        load_alerts_from_source(config=config)


def test_cache_raw_dataframe_writes_file(tmp_path: Path) -> None:
    """Cache helper writes CSV to destination path."""
    df = pd.DataFrame({"timestamp": ["2024-06-01"], "region": ["Kyiv"]})
    output = cache_raw_dataframe(df, tmp_path / "cached.csv")
    assert output.exists()
