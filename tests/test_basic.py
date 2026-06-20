"""Basic tests for scaffold validation."""

from __future__ import annotations

import numpy as np
import pytest

from src.config import AppConfig, get_config
from src.evaluation import compute_regression_metrics


def test_import_and_metrics_smoke() -> None:
    """Ensure core modules are importable and metric output is valid."""
    y_true = np.array([1.0, 2.0, 3.0], dtype=float)
    y_pred = np.array([1.0, 2.0, 4.0], dtype=float)

    metrics = compute_regression_metrics(y_true=y_true, y_pred=y_pred)

    assert {"mae", "rmse", "mape"} == set(metrics.keys())
    assert metrics["mae"] >= 0.0
    assert metrics["rmse"] >= 0.0
    assert metrics["mape"] >= 0.0


def test_config_defaults() -> None:
    """Ensure default configuration loads with expected values."""
    config = get_config()

    assert isinstance(config, AppConfig)
    assert config.project_name == "AirRaidAnalysis"
    assert config.timezone == "Europe/Kyiv"
    assert 0.05 <= config.test_size <= 0.5


def test_metrics_length_mismatch_raises() -> None:
    """Ensure metric function rejects mismatched input lengths."""
    with pytest.raises(ValueError, match="equal length"):
        compute_regression_metrics(
            y_true=np.array([1.0, 2.0]),
            y_pred=np.array([1.0]),
        )
