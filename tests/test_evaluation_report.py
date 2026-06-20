"""Tests for metrics report persistence."""

from __future__ import annotations

import json
from pathlib import Path

from src.evaluation import save_metrics_report


def test_save_metrics_report_writes_json(tmp_path: Path) -> None:
    """Metrics report is serialized to JSON on disk."""
    metrics = {
        "seasonal_naive": {"mae": 1.0, "rmse": 1.5, "mape": 10.0},
        "linear_regression": {"mae": 0.8, "rmse": 1.1, "mape": 8.0},
    }
    output_path = tmp_path / "reports" / "baseline_metrics.json"

    saved_path = save_metrics_report(metrics=metrics, output_path=output_path)

    assert saved_path.exists()
    loaded = json.loads(saved_path.read_text(encoding="utf-8"))
    assert loaded == metrics
