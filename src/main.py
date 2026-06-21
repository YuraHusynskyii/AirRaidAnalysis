"""Entrypoint for basic project pipeline smoke run."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from typing import Any, Dict, Optional, Tuple

import pandas as pd

from src.baseline import evaluate_all_baselines
from src.config import AppConfig, get_config
from src.data_source import load_alerts_from_source
from src.evaluation import save_markdown_report, save_metrics_report
from src.features import build_features
from src.preprocessing import (
    ensure_datetime_index,
    resample_alert_counts,
    resample_regional_alert_counts,
)
from src.tuning import run_tuning, save_tuning_report


def run_pipeline(
    config: Optional[AppConfig] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run ingestion, preprocessing and feature engineering flow.

    Args:
        config: Optional settings override for tests or custom runs.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
            Processed hourly counts, features and regional hourly counts.

    Raises:
        RuntimeError: If the pipeline fails at any stage.
    """
    active_config = config or get_config()
    try:
        raw_df = load_alerts_from_source(config=active_config)
        indexed_df = ensure_datetime_index(
            df=raw_df,
            datetime_column=active_config.datetime_column,
            timezone=active_config.timezone,
        )
        processed_df = resample_alert_counts(indexed_df, rule="1h")
        featured_df = build_features(
            df=processed_df,
            target_column=active_config.target_column,
            lags=active_config.lag_periods,
        )
        regional_df = pd.DataFrame()
        if active_config.region_column:
            regional_df = resample_regional_alert_counts(
                df=indexed_df,
                region_column=active_config.region_column,
                rule="1h",
            )

        active_config.processed_data_path.parent.mkdir(parents=True, exist_ok=True)
        processed_df.to_csv(active_config.processed_data_path, index=True)
        featured_df.to_csv(active_config.features_data_path, index=True)

        print(
            f"Pipeline completed. Processed rows={len(processed_df)}, "
            f"feature rows={len(featured_df)}, "
            f"regions={len(regional_df.columns)}. "
            f"Saved to {active_config.processed_data_path} and "
            f"{active_config.features_data_path}"
        )
        return processed_df, featured_df, regional_df
    except Exception as exc:
        raise RuntimeError("Pipeline execution failed.") from exc


def run_baseline_evaluation(
    processed_df: pd.DataFrame,
    featured_df: pd.DataFrame,
    regional_df: pd.DataFrame,
    config: Optional[AppConfig] = None,
) -> Dict[str, Any]:
    """Run baseline models, save JSON/markdown reports and print summary.

    Args:
        processed_df: Hourly processed dataframe.
        featured_df: Feature-enriched dataframe.
        regional_df: Hourly counts per region.
        config: Optional settings override.

    Returns:
        Dict[str, Any]: Nested metrics with global and regional sections.

    Raises:
        RuntimeError: If baseline evaluation fails.
    """
    active_config = config or get_config()
    try:
        metrics = evaluate_all_baselines(
            processed_df=processed_df,
            featured_df=featured_df,
            regional_df=regional_df,
            target_column=active_config.target_column,
            test_size=active_config.test_size,
            season_period=active_config.season_period,
            arima_order=active_config.arima_order,
            seasonal_order=active_config.seasonal_order,
            sarimax_seasonal_order=active_config.sarimax_seasonal_order,
            datetime_column=active_config.datetime_column,
            timezone=active_config.timezone,
            region_column=active_config.region_column,
            extended_raw_data_path=active_config.extended_raw_data_path,
            random_seed=active_config.random_seed,
            lag_periods=active_config.lag_periods,
            boosting_n_estimators=active_config.boosting_n_estimators,
        )
        json_path = save_metrics_report(
            metrics=metrics,
            output_path=active_config.baseline_metrics_path,
        )
        markdown_path = save_markdown_report(
            metrics=metrics,
            output_path=active_config.summary_report_path,
            project_name=active_config.project_name,
        )

        for model_name, model_metrics in metrics["global"].items():
            print(
                f"Baseline ({model_name}) metrics: "
                f"MAE={model_metrics['mae']:.3f}, "
                f"RMSE={model_metrics['rmse']:.3f}, "
                f"MAPE={model_metrics['mape']:.3f}%"
            )
        print(f"Evaluated {len(metrics['regional'])} regions.")
        print(f"Saved baseline report to {json_path}")
        print(f"Saved markdown summary to {markdown_path}")
        return metrics
    except Exception as exc:
        raise RuntimeError("Baseline evaluation failed.") from exc


def run_optional_tuning(
    processed_df: pd.DataFrame,
    featured_df: pd.DataFrame,
    config: Optional[AppConfig] = None,
) -> Optional[Dict[str, Any]]:
    """Run Optuna tuning when enabled in configuration.

    Args:
        processed_df: Hourly processed dataframe.
        featured_df: Feature-enriched dataframe.
        config: Optional settings override.

    Returns:
        Optional[Dict[str, Any]]: Tuning results when enabled, else ``None``.

    Raises:
        RuntimeError: If tuning fails.
    """
    active_config = config or get_config()
    if not active_config.enable_tuning:
        return None

    try:
        results = run_tuning(
            featured_df=featured_df,
            processed_series=processed_df[active_config.target_column],
            target_column=active_config.target_column,
            test_size=active_config.test_size,
            random_seed=active_config.random_seed,
            season_period=active_config.season_period,
            n_trials=active_config.tuning_trials,
        )
        report_path = save_tuning_report(
            results=results,
            output_path=active_config.tuning_results_path,
        )
        print(
            "Tuning completed. "
            f"XGBoost best MAE={results['xgboost']['best_mae']:.3f}, "
            f"SARIMAX="
            f"{results['sarimax'].get('best_mae', 'skipped')}. "
            f"Saved to {report_path}"
        )
        return results
    except Exception as exc:
        raise RuntimeError("Optional tuning step failed.") from exc


def main(config: Optional[AppConfig] = None) -> Path:
    """CLI entrypoint that runs the pipeline and baseline evaluation.

    Args:
        config: Optional settings override for CLI flags or tests.

    Returns:
        Path: Path to processed CSV artifact.
    """
    active_config = config or get_config()
    processed_df, featured_df, regional_df = run_pipeline(config=active_config)
    run_baseline_evaluation(
        processed_df=processed_df,
        featured_df=featured_df,
        regional_df=regional_df,
        config=active_config,
    )
    run_optional_tuning(
        processed_df=processed_df,
        featured_df=featured_df,
        config=active_config,
    )
    return active_config.processed_data_path


def _build_cli_config() -> AppConfig:
    """Parse CLI flags and merge them into application settings."""
    import argparse

    parser = argparse.ArgumentParser(description="Run the AirRaidAnalysis pipeline.")
    parser.add_argument(
        "--input",
        type=Path,
        help="Path to raw alerts CSV input file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Directory where processed data and reports are written.",
    )
    args = parser.parse_args()

    config = get_config()
    updates: dict[str, Path] = {}
    if args.input is not None:
        updates["raw_data_path"] = args.input
    if args.output is not None:
        output_dir = args.output
        output_dir.mkdir(parents=True, exist_ok=True)
        updates.update(
            {
                "processed_data_path": output_dir / "alerts_processed.csv",
                "features_data_path": output_dir / "alerts_features.csv",
                "baseline_metrics_path": output_dir / "baseline_metrics.json",
                "summary_report_path": output_dir / "evaluation_summary.md",
            }
        )

    if not updates:
        return config
    return config.model_copy(update=updates)


if __name__ == "__main__":
    main(config=_build_cli_config())
