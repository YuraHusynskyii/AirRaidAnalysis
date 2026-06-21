"""Tests for experiment configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import AppConfig, get_config, load_config_from_yaml


def test_load_config_from_yaml_defaults() -> None:
    """Default experiment YAML maps to expected AppConfig values."""
    config = load_config_from_yaml("configs/experiment_default.yaml")

    assert isinstance(config, AppConfig)
    assert config.project_name == "AirRaidAnalysis"
    assert config.raw_data_path == Path("data/samples/sample_alerts.csv")
    assert config.test_size == pytest.approx(0.2)
    assert config.lag_periods == [1, 24]
    assert config.timezone == "Europe/Kyiv"


def test_get_config_with_experiment_path() -> None:
    """get_config accepts optional YAML experiment path."""
    config = get_config(experiment_path="configs/experiment_default.yaml")
    assert config.baseline_metrics_path == Path("reports/baseline_metrics.json")
    assert config.arima_order == [1, 0, 0]
    assert config.sarimax_seasonal_order == [1, 0, 0, 24]
    assert config.data_source_type == "local_csv"
    assert config.enable_tuning is False


def test_load_config_from_yaml_missing_file_raises() -> None:
    """Missing YAML path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config_from_yaml("configs/does_not_exist.yaml")
