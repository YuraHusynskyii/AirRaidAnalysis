"""Tests for feature drift detection."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.config import AppConfig
from src.monitoring import (
    compute_feature_statistics,
    detect_feature_drift,
    run_drift_check,
)


def test_detect_feature_drift_flags_relative_change() -> None:
    """Drift alert triggers when mean deviates beyond threshold."""
    alerts = detect_feature_drift(
        current_stats={"alert_count": 2.0},
        reference_stats={"alert_count": 1.0},
        threshold=0.25,
    )
    assert len(alerts) == 1
    assert alerts[0].feature == "alert_count"


def test_run_drift_check_creates_reference_baseline(tmp_path: Path) -> None:
    """First drift run writes reference statistics when baseline is missing."""
    index = pd.date_range("2024-01-01", periods=24, freq="h")
    featured = pd.DataFrame(
        {
            "alert_count": [1] * 24,
            "hour": index.hour,
            "day_of_week": index.dayofweek,
            "is_weekend": 0,
        },
        index=index,
    )
    config = AppConfig(
        monitoring_drift_reference_path=tmp_path / "drift_reference.json",
        monitoring_drift_alerts_path=tmp_path / "drift_alerts.json",
    )

    result = run_drift_check(
        featured_df=featured,
        target_column="alert_count",
        config=config,
    )

    assert result.alerts == []
    assert config.monitoring_drift_reference_path.exists()


def test_run_drift_check_detects_shift(tmp_path: Path) -> None:
    """Subsequent drift run compares against saved reference baseline."""
    reference_path = tmp_path / "drift_reference.json"
    reference_path.write_text(
        json.dumps({"reference_stats": {"alert_count": 1.0}}),
        encoding="utf-8",
    )
    index = pd.date_range("2024-01-01", periods=24, freq="h")
    featured = pd.DataFrame(
        {
            "alert_count": [5] * 24,
            "hour": index.hour,
        },
        index=index,
    )
    config = AppConfig(
        monitoring_drift_reference_path=reference_path,
        monitoring_drift_alerts_path=tmp_path / "drift_alerts.json",
        monitoring_drift_threshold=0.25,
    )

    result = run_drift_check(
        featured_df=featured,
        target_column="alert_count",
        config=config,
    )
    assert len(result.alerts) == 1


def test_compute_feature_statistics_skips_missing_columns() -> None:
    """Statistics helper ignores columns not present in dataframe."""
    df = pd.DataFrame({"alert_count": [1, 2, 3]})
    stats = compute_feature_statistics(df, ["alert_count", "hour"])
    assert stats == {"alert_count": 2.0}
