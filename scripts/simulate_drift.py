#!/usr/bin/env python3
"""Simulate data drift and optional metric degradation for monitoring audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd  # noqa: E402

from src.config import get_config  # noqa: E402
from src.monitoring import run_drift_check, run_monitoring_check  # noqa: E402


def _load_feature_frame(source: Path) -> pd.DataFrame:
    """Load processed feature CSV used as drift simulation input."""
    if not source.exists():
        raise FileNotFoundError(f"Feature source not found: {source}")
    frame = pd.read_csv(source, parse_dates=["timestamp"])
    frame = frame.set_index("timestamp")
    return frame


def _build_drifted_frame(baseline: pd.DataFrame, multiplier: float) -> pd.DataFrame:
    """Create an anomalous copy by scaling alert_count."""
    drifted = baseline.copy()
    drifted["alert_count"] = drifted["alert_count"] * multiplier
    return drifted


def simulate_data_drift(
    *,
    source_path: Path,
    multiplier: float,
    config,
) -> dict:
    """Run drift check on anomalous data and persist drift alerts."""
    baseline = _load_feature_frame(source_path)
    drifted = _build_drifted_frame(baseline, multiplier=multiplier)

    # Seed reference baseline from normal data if missing.
    run_drift_check(
        featured_df=baseline,
        target_column=config.target_column,
        config=config,
    )

    result = run_drift_check(
        featured_df=drifted,
        target_column=config.target_column,
        config=config,
    )

    payload = json.loads(result.alerts_path.read_text(encoding="utf-8"))
    return {
        "alert_count": payload["alert_count"],
        "alerts_path": str(result.alerts_path),
        "reference_path": str(result.reference_path),
        "alerts": payload["alerts"],
    }


def simulate_metric_degradation(config) -> dict:
    """Simulate post-retrain metric regression into monitoring_alerts.json."""
    previous_metadata = {
        "version": "audit-previous",
        "metrics": {"mae": 0.10, "rmse": 0.20, "mape": 1.0},
    }
    current_metadata = {
        "version": "audit-current",
        "metrics": {"mae": 0.50, "rmse": 0.60, "mape": 5.0},
    }
    result = run_monitoring_check(
        model_name=config.production_model_name,
        current_metadata=current_metadata,
        previous_metadata=previous_metadata,
        config=config,
    )
    payload = json.loads(result.alerts_path.read_text(encoding="utf-8"))
    return {
        "alert_count": payload["alert_count"],
        "alerts_path": str(result.alerts_path),
        "alerts": payload["alerts"],
    }


def main() -> int:
    """CLI entrypoint for drift/monitoring simulation."""
    parser = argparse.ArgumentParser(description="Simulate drift and monitoring alerts.")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/processed/alerts_features.csv"),
        help="Baseline feature CSV path.",
    )
    parser.add_argument(
        "--multiplier",
        type=float,
        default=5.0,
        help="Scale factor applied to alert_count for drift simulation.",
    )
    parser.add_argument(
        "--skip-metric-alert",
        action="store_true",
        help="Skip metric degradation simulation (monitoring_alerts.json).",
    )
    args = parser.parse_args()

    config = get_config()
    drift_summary = simulate_data_drift(
        source_path=args.source,
        multiplier=args.multiplier,
        config=config,
    )
    print(
        "Drift simulation complete: "
        f"alerts={drift_summary['alert_count']} "
        f"path={drift_summary['alerts_path']}"
    )

    if drift_summary["alert_count"] == 0:
        print("ERROR: expected at least one drift alert.", file=sys.stderr)
        return 1

    if not args.skip_metric_alert:
        metric_summary = simulate_metric_degradation(config)
        print(
            "Metric degradation simulation complete: "
            f"alerts={metric_summary['alert_count']} "
            f"path={metric_summary['alerts_path']}"
        )
        if metric_summary["alert_count"] == 0:
            print("ERROR: expected at least one monitoring alert.", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
