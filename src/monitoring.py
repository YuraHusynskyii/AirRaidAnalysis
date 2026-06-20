"""Monitoring helpers for detecting metric degradation between retrain jobs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

import pandas as pd

from src.config import AppConfig


@dataclass(frozen=True)
class MetricAlert:
    """Single metric degradation alert."""

    metric: str
    previous: float
    current: float
    relative_change: float
    threshold: float
    message: str


@dataclass(frozen=True)
class MonitoringResult:
    """Outcome of a post-retrain monitoring check."""

    model_name: str
    current_version: str
    previous_version: Optional[str]
    alerts: List[MetricAlert]
    history_path: Path
    alerts_path: Path


@dataclass(frozen=True)
class DriftAlert:
    """Single feature drift alert against static/reference thresholds."""

    feature: str
    observed: float
    reference: float
    relative_change: float
    threshold: float
    message: str


@dataclass(frozen=True)
class DriftCheckResult:
    """Outcome of a feature drift check."""

    alerts: List[DriftAlert]
    reference_path: Path
    alerts_path: Path


def normalize_artifact_metrics(metrics: Mapping[str, float]) -> Dict[str, float]:
    """Normalize artifact or tuning metrics to mae/rmse/mape keys.

    Args:
        metrics: Raw metrics dictionary from registry or tuning output.

    Returns:
        Dict[str, float]: Normalized metric mapping.
    """
    if "best_mae" in metrics:
        return {
            "mae": float(metrics["best_mae"]),
            "rmse": float(metrics.get("best_rmse", metrics["best_mae"])),
            "mape": float(metrics.get("best_mape", 0.0)),
        }
    return {
        "mae": float(metrics["mae"]),
        "rmse": float(metrics["rmse"]),
        "mape": float(metrics["mape"]),
    }


def _relative_increase(previous: float, current: float) -> float:
    """Compute relative increase; zero baseline treated as absolute delta."""
    if previous == 0:
        return current
    return (current - previous) / abs(previous)


def detect_metric_degradation(
    previous_metrics: Mapping[str, float],
    current_metrics: Mapping[str, float],
    threshold: float,
) -> List[MetricAlert]:
    """Detect metric regressions above a relative threshold.

    Args:
        previous_metrics: Metrics from the previous registered artifact.
        current_metrics: Metrics from the newly registered artifact.
        threshold: Relative increase threshold (e.g. 0.15 = 15%).

    Returns:
        List[MetricAlert]: Alerts for degraded metrics.
    """
    alerts: List[MetricAlert] = []
    for metric_name in ("mae", "rmse", "mape"):
        previous_value = float(previous_metrics[metric_name])
        current_value = float(current_metrics[metric_name])
        relative_change = _relative_increase(previous_value, current_value)
        if relative_change > threshold:
            alerts.append(
                MetricAlert(
                    metric=metric_name,
                    previous=previous_value,
                    current=current_value,
                    relative_change=relative_change,
                    threshold=threshold,
                    message=(
                        f"{metric_name.upper()} degraded: "
                        f"{previous_value:.4f} -> {current_value:.4f} "
                        f"(+{relative_change * 100:.1f}%)"
                    ),
                )
            )
    return alerts


def compute_feature_statistics(
    dataframe: pd.DataFrame,
    columns: list[str],
) -> Dict[str, float]:
    """Compute mean statistics for drift monitoring on selected columns.

    Args:
        dataframe: Input feature dataframe.
        columns: Numeric columns to summarize.

    Returns:
        Dict[str, float]: Feature -> mean mapping for columns present in data.
    """
    stats: Dict[str, float] = {}
    for column in columns:
        if column not in dataframe.columns:
            continue
        series = pd.to_numeric(dataframe[column], errors="coerce").dropna()
        if series.empty:
            continue
        stats[column] = float(series.mean())
    return stats


def detect_feature_drift(
    current_stats: Mapping[str, float],
    reference_stats: Mapping[str, float],
    threshold: float,
) -> List[DriftAlert]:
    """Detect drift when feature means deviate beyond a relative threshold.

    Args:
        current_stats: Current batch feature means.
        reference_stats: Baseline/reference feature means.
        threshold: Relative deviation threshold (e.g. 0.25 = 25%).

    Returns:
        List[DriftAlert]: Drift alerts for breached features.
    """
    alerts: List[DriftAlert] = []
    for feature, reference_value in reference_stats.items():
        if feature not in current_stats:
            continue
        current_value = float(current_stats[feature])
        relative_change = _relative_increase(reference_value, current_value)
        if relative_change > threshold:
            alerts.append(
                DriftAlert(
                    feature=feature,
                    observed=current_value,
                    reference=reference_value,
                    relative_change=relative_change,
                    threshold=threshold,
                    message=(
                        f"Drift on {feature}: {reference_value:.4f} -> "
                        f"{current_value:.4f} (+{relative_change * 100:.1f}%)"
                    ),
                )
            )
    return alerts


def save_drift_reference(
    reference_stats: Mapping[str, float],
    output_path: Path | str,
) -> Path:
    """Persist baseline feature statistics used for drift checks."""
    destination = Path(output_path)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "reference_stats": dict(reference_stats),
    }
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
    except Exception as exc:
        raise RuntimeError(f"Failed to save drift reference: {destination}") from exc
    return destination


def load_drift_reference(path: Path | str) -> Dict[str, float]:
    """Load baseline feature statistics from drift reference JSON."""
    reference_path = Path(path)
    if not reference_path.exists():
        return {}
    try:
        payload = json.loads(reference_path.read_text(encoding="utf-8"))
        stats = payload.get("reference_stats", {})
        return {str(key): float(value) for key, value in stats.items()}
    except Exception as exc:
        raise RuntimeError(f"Failed to load drift reference: {reference_path}") from exc


def save_drift_alerts(
    alerts: List[DriftAlert],
    output_path: Path | str,
) -> Path:
    """Persist drift alerts as JSON."""
    destination = Path(output_path)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "alert_count": len(alerts),
        "alerts": [
            {
                "feature": alert.feature,
                "observed": alert.observed,
                "reference": alert.reference,
                "relative_change": alert.relative_change,
                "threshold": alert.threshold,
                "message": alert.message,
            }
            for alert in alerts
        ],
    }
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
    except Exception as exc:
        raise RuntimeError(f"Failed to save drift alerts: {destination}") from exc
    return destination


def run_drift_check(
    featured_df: pd.DataFrame,
    target_column: str,
    config: AppConfig,
) -> DriftCheckResult:
    """Run baseline drift detection on feature means vs static reference file.

    If reference file is missing, current statistics are saved as baseline.
    """
    monitored_columns = [
        target_column,
        "hour",
        "day_of_week",
        "is_weekend",
    ]
    current_stats = compute_feature_statistics(featured_df, monitored_columns)
    reference_path = config.monitoring_drift_reference_path
    alerts_path = config.monitoring_drift_alerts_path

    reference_stats = load_drift_reference(reference_path)
    if not reference_stats:
        save_drift_reference(current_stats, reference_path)
        save_drift_alerts([], alerts_path)
        return DriftCheckResult(
            alerts=[],
            reference_path=reference_path,
            alerts_path=alerts_path,
        )

    alerts = detect_feature_drift(
        current_stats=current_stats,
        reference_stats=reference_stats,
        threshold=config.monitoring_drift_threshold,
    )
    save_drift_alerts(alerts, alerts_path)
    return DriftCheckResult(
        alerts=alerts,
        reference_path=reference_path,
        alerts_path=alerts_path,
    )


def load_metrics_history(path: Path | str) -> list[dict[str, Any]]:
    """Load persisted retrain metrics history.

    Args:
        path: JSON history file path.

    Returns:
        list[dict[str, Any]]: Historical entries, oldest first.
    """
    history_path = Path(path)
    if not history_path.exists():
        return []
    try:
        payload = json.loads(history_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Failed to load metrics history: {history_path}") from exc
    if not isinstance(payload, list):
        raise RuntimeError(f"Invalid metrics history format: {history_path}")
    return payload


def append_metrics_history(
    path: Path | str,
    entry: Mapping[str, Any],
) -> Path:
    """Append one retrain metrics entry to history JSON.

    Args:
        path: JSON history file path.
        entry: Serializable history record.

    Returns:
        Path: Updated history file path.
    """
    history_path = Path(path)
    history = load_metrics_history(history_path)
    history.append(dict(entry))
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("w", encoding="utf-8") as handle:
            json.dump(history, handle, indent=2)
    except Exception as exc:
        raise RuntimeError(f"Failed to append metrics history: {history_path}") from exc
    return history_path


def save_monitoring_alerts(
    alerts: List[MetricAlert],
    output_path: Path | str,
    model_name: str,
    current_version: str,
    previous_version: Optional[str],
) -> Path:
    """Persist monitoring alerts as JSON for downstream notification hooks.

    Args:
        alerts: Detected degradation alerts.
        output_path: Destination JSON path.
        model_name: Registered model name.
        current_version: New artifact version id.
        previous_version: Previous artifact version id, if any.

    Returns:
        Path: Written alerts file path.
    """
    destination = Path(output_path)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_name": model_name,
        "current_version": current_version,
        "previous_version": previous_version,
        "alert_count": len(alerts),
        "alerts": [
            {
                "metric": alert.metric,
                "previous": alert.previous,
                "current": alert.current,
                "relative_change": alert.relative_change,
                "threshold": alert.threshold,
                "message": alert.message,
            }
            for alert in alerts
        ],
    }
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
    except Exception as exc:
        raise RuntimeError(f"Failed to save monitoring alerts: {destination}") from exc
    return destination


def dispatch_monitoring_webhook(
    webhook_url: str,
    payload: Mapping[str, Any],
    timeout_seconds: int = 10,
) -> None:
    """POST monitoring alert payload to an optional webhook endpoint.

    Args:
        webhook_url: Destination webhook URL.
        payload: JSON-serializable alert payload.
        timeout_seconds: Network timeout in seconds.

    Raises:
        RuntimeError: If webhook delivery fails.
    """
    if not webhook_url:
        return

    body = json.dumps(payload).encode("utf-8")
    request = Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status_code = response.getcode()
            if status_code >= 400:
                raise RuntimeError(
                    f"Monitoring webhook returned HTTP {status_code}."
                )
    except (URLError, OSError, ValueError) as exc:
        raise RuntimeError(f"Failed to dispatch monitoring webhook: {webhook_url}") from exc


def run_monitoring_check(
    model_name: str,
    current_metadata: Mapping[str, Any],
    previous_metadata: Optional[Mapping[str, Any]],
    config: AppConfig,
) -> MonitoringResult:
    """Compare current artifact metrics against previous retrain and persist alerts.

    Args:
        model_name: Registered production model name.
        current_metadata: Metadata for the newly registered artifact.
        previous_metadata: Metadata for the previous artifact, if available.
        config: Application settings with monitoring thresholds/paths.

    Returns:
        MonitoringResult: Monitoring outcome with any degradation alerts.
    """
    current_metrics = normalize_artifact_metrics(current_metadata["metrics"])
    current_version = str(current_metadata["version"])
    previous_version = (
        str(previous_metadata["version"]) if previous_metadata is not None else None
    )

    alerts: List[MetricAlert] = []
    if previous_metadata is not None:
        previous_metrics = normalize_artifact_metrics(previous_metadata["metrics"])
        alerts = detect_metric_degradation(
            previous_metrics=previous_metrics,
            current_metrics=current_metrics,
            threshold=config.monitoring_degradation_threshold,
        )

    history_entry = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_name": model_name,
        "version": current_version,
        "previous_version": previous_version,
        "metrics": current_metrics,
        "alerts": [alert.message for alert in alerts],
    }
    append_metrics_history(config.monitoring_history_path, history_entry)
    alerts_path = save_monitoring_alerts(
        alerts=alerts,
        output_path=config.monitoring_alerts_path,
        model_name=model_name,
        current_version=current_version,
        previous_version=previous_version,
    )

    if alerts and config.monitoring_webhook_url:
        webhook_payload = json.loads(alerts_path.read_text(encoding="utf-8"))
        dispatch_monitoring_webhook(
            webhook_url=config.monitoring_webhook_url,
            payload=webhook_payload,
        )

    return MonitoringResult(
        model_name=model_name,
        current_version=current_version,
        previous_version=previous_version,
        alerts=alerts,
        history_path=config.monitoring_history_path,
        alerts_path=config.monitoring_alerts_path,
    )
