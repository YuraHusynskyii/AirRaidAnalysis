"""Tests for monitoring webhook dispatch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from sklearn.linear_model import LinearRegression

from src.config import AppConfig
from src.monitoring import dispatch_monitoring_webhook, run_monitoring_check
from src.registry import (
    list_model_versions,
    load_model_metadata,
    load_previous_model_metadata,
    save_model_artifact,
)


@patch("src.monitoring.urlopen")
def test_dispatch_monitoring_webhook_posts_json(mock_urlopen) -> None:
    """Webhook dispatch sends JSON payload via HTTP POST."""

    class _Response:
        def getcode(self) -> int:
            return 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    mock_urlopen.return_value = _Response()
    dispatch_monitoring_webhook(
        webhook_url="https://example.com/hook",
        payload={"alert_count": 1},
    )

    request = mock_urlopen.call_args.args[0]
    assert request.full_url == "https://example.com/hook"
    assert request.method == "POST"


@patch("src.monitoring.dispatch_monitoring_webhook")
def test_run_monitoring_check_dispatches_webhook_on_alerts(
    mock_dispatch,
    tmp_path: Path,
) -> None:
    """Monitoring check posts webhook payload when degradation alerts exist."""
    model = LinearRegression()
    model.fit([[1.0], [2.0]], [1.0, 2.0])
    save_model_artifact(
        model=model,
        model_name="prod_model",
        registry_dir=tmp_path,
        metrics={"mae": 0.10, "rmse": 0.12, "mape": 1.0},
        feature_columns=["hour"],
    )
    save_model_artifact(
        model=model,
        model_name="prod_model",
        registry_dir=tmp_path,
        metrics={"mae": 0.20, "rmse": 0.12, "mape": 1.0},
        feature_columns=["hour"],
    )

    config = AppConfig(
        monitoring_history_path=tmp_path / "history.json",
        monitoring_alerts_path=tmp_path / "alerts.json",
        monitoring_webhook_url="https://example.com/hook",
        monitoring_degradation_threshold=0.15,
    )
    run_monitoring_check(
        model_name="prod_model",
        current_metadata=load_model_metadata(
            "prod_model",
            list_model_versions("prod_model", tmp_path)[0],
            tmp_path,
        ),
        previous_metadata=load_previous_model_metadata("prod_model", tmp_path),
        config=config,
    )

    mock_dispatch.assert_called_once()
