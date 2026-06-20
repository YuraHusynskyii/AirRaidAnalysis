"""Evaluation helpers for time-series model outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error


def compute_regression_metrics(
    y_true: np.ndarray, y_pred: np.ndarray
) -> Dict[str, float]:
    """Compute core regression metrics for forecast evaluation.

    Args:
        y_true: Ground truth target values.
        y_pred: Predicted target values.

    Returns:
        Dict[str, float]: Mapping with mae, rmse and mape.

    Raises:
        ValueError: If input lengths do not match.
        RuntimeError: If metric computation fails.
    """
    if y_true.shape[0] != y_pred.shape[0]:
        raise ValueError("Input arrays must have equal length.")

    try:
        mae = float(mean_absolute_error(y_true, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        denominator = np.where(y_true == 0, 1.0, y_true)
        mape = float(np.mean(np.abs((y_true - y_pred) / denominator)) * 100)
    except Exception as exc:
        raise RuntimeError("Failed to compute regression metrics.") from exc

    return {"mae": mae, "rmse": rmse, "mape": mape}


def save_metrics_report(
    metrics: Mapping[str, Mapping[str, float]], output_path: Path | str
) -> Path:
    """Persist nested model metrics to a JSON report file.

    Args:
        metrics: Mapping of model name to metric dictionary.
        output_path: Destination JSON file path.

    Returns:
        Path: Written report path.

    Raises:
        RuntimeError: If report serialization or file write fails.
    """
    destination = Path(output_path)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2)
    except Exception as exc:
        raise RuntimeError(f"Failed to save metrics report: {destination}") from exc

    return destination


def _format_metric_row(model_name: str, metrics: Mapping[str, float]) -> str:
    """Format one model metrics row for markdown tables."""
    return (
        f"| {model_name} | {metrics['mae']:.3f} | "
        f"{metrics['rmse']:.3f} | {metrics['mape']:.3f} |"
    )


def build_markdown_report(
    metrics: Mapping[str, Any],
    project_name: str = "AirRaidAnalysis",
) -> str:
    """Build a human-readable markdown summary from evaluation metrics.

    Args:
        metrics: Nested metrics payload with ``global`` and ``regional`` sections.
        project_name: Project title for report header.

    Returns:
        str: Markdown report content.

    Raises:
        ValueError: If required metric sections are missing.
        RuntimeError: If report generation fails unexpectedly.
    """
    if "global" not in metrics:
        raise ValueError("Metrics payload must include a 'global' section.")

    try:
        lines = [
            f"# {project_name} — Evaluation Summary",
            "",
            "## Global Baselines",
            "",
            "| Model | MAE | RMSE | MAPE (%) |",
            "|---|---:|---:|---:|",
        ]
        for model_name, model_metrics in metrics["global"].items():
            lines.append(_format_metric_row(model_name, model_metrics))

        regional_metrics = metrics.get("regional", {})
        if regional_metrics:
            model_names = sorted(
                {
                    model_name
                    for region_models in regional_metrics.values()
                    for model_name in region_models.keys()
                }
            )
            for model_name in model_names:
                lines.extend(
                    [
                        "",
                        f"## Regional {model_name} (Holdout)",
                        "",
                        "| Region | MAE | RMSE | MAPE (%) |",
                        "|---|---:|---:|---:|",
                    ]
                )
                for region_name, region_model_metrics in regional_metrics.items():
                    model_metrics = region_model_metrics.get(model_name, {})
                    if model_metrics:
                        lines.append(_format_metric_row(region_name, model_metrics))

        lines.extend(
            [
                "",
                "## Notes",
                "",
                "- Split: chronological holdout (no shuffle).",
                "- Regional metrics use hourly counts per region.",
                "- `sarimax_s24` is tuned on extended dataset when available.",
                "- Boosting models: XGBoost and LightGBM on global feature matrix.",
            ]
        )
        return "\n".join(lines) + "\n"
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Failed to build markdown evaluation report.") from exc


def save_markdown_report(
    metrics: Mapping[str, Any],
    output_path: Path | str,
    project_name: str = "AirRaidAnalysis",
) -> Path:
    """Persist markdown evaluation summary to disk.

    Args:
        metrics: Nested metrics payload.
        output_path: Destination markdown file path.
        project_name: Project title for report header.

    Returns:
        Path: Written report path.

    Raises:
        RuntimeError: If report writing fails.
    """
    destination = Path(output_path)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        report_content = build_markdown_report(
            metrics=metrics,
            project_name=project_name,
        )
        destination.write_text(report_content, encoding="utf-8")
    except Exception as exc:
        raise RuntimeError(f"Failed to save markdown report: {destination}") from exc

    return destination


def compare_model_metrics(
    metrics_a: Mapping[str, float],
    metrics_b: Mapping[str, float],
    label_a: str,
    label_b: str,
    primary_metric: str = "mae",
) -> Dict[str, Any]:
    """Compare two model metric payloads and pick a winner.

    Args:
        metrics_a: Metrics for candidate A.
        metrics_b: Metrics for candidate B.
        label_a: Display label for candidate A.
        label_b: Display label for candidate B.
        primary_metric: Metric used for winner selection (lower is better).

    Returns:
        Dict[str, Any]: Structured A/B comparison report.

    Raises:
        ValueError: If primary metric is missing from either payload.
    """
    if primary_metric not in metrics_a or primary_metric not in metrics_b:
        raise ValueError(f"Primary metric '{primary_metric}' missing from comparison payload.")

    value_a = float(metrics_a[primary_metric])
    value_b = float(metrics_b[primary_metric])
    if value_a < value_b:
        winner = label_a
    elif value_b < value_a:
        winner = label_b
    else:
        winner = "tie"

    delta = value_b - value_a
    relative_delta = (delta / value_b) if value_b != 0 else delta

    return {
        "label_a": label_a,
        "label_b": label_b,
        "primary_metric": primary_metric,
        "metrics_a": dict(metrics_a),
        "metrics_b": dict(metrics_b),
        "winner": winner,
        "delta": delta,
        "relative_delta": relative_delta,
    }


def evaluate_models_ab_on_holdout(
    featured_df: Any,
    model_a: Any,
    model_b: Any,
    feature_columns: list[str],
    target_column: str,
    test_size: float,
    label_a: str = "model_a",
    label_b: str = "model_b",
    primary_metric: str = "mae",
) -> Dict[str, Any]:
    """Run A/B evaluation for two models on the same chronological holdout.

    Args:
        featured_df: Feature-enriched dataframe.
        model_a: First fitted model.
        model_b: Second fitted model.
        feature_columns: Feature columns used for prediction.
        target_column: Target column name.
        test_size: Holdout fraction.
        label_a: Label for model A in the report.
        label_b: Label for model B in the report.
        primary_metric: Metric used to declare winner.

    Returns:
        Dict[str, Any]: A/B comparison report with holdout metrics.

    Raises:
        RuntimeError: If evaluation fails unexpectedly.
    """
    from src.baseline import split_feature_matrix

    try:
        _x_train, _y_train, x_test, y_test = split_feature_matrix(
            featured_df=featured_df,
            target_column=target_column,
            test_size=test_size,
        )
        x_holdout = x_test[feature_columns]
        metrics_a = compute_regression_metrics(
            y_true=y_test.to_numpy(dtype=float),
            y_pred=model_a.predict(x_holdout),
        )
        metrics_b = compute_regression_metrics(
            y_true=y_test.to_numpy(dtype=float),
            y_pred=model_b.predict(x_holdout),
        )
        comparison = compare_model_metrics(
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            label_a=label_a,
            label_b=label_b,
            primary_metric=primary_metric,
        )
        comparison["evaluation_type"] = "holdout_ab"
        return comparison
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Failed to evaluate models A/B on holdout.") from exc


def compare_registry_model_versions(
    model_name: str,
    version_a: str,
    version_b: str,
    registry_dir: Path | str,
    primary_metric: str = "mae",
) -> Dict[str, Any]:
    """Compare two registered model versions using stored validation metrics.

    Args:
        model_name: Logical model name in registry.
        version_a: Candidate A version id.
        version_b: Candidate B version id.
        registry_dir: Registry root directory.
        primary_metric: Metric used to declare winner.

    Returns:
        Dict[str, Any]: Structured A/B comparison report.
    """
    from src.monitoring import normalize_artifact_metrics
    from src.registry import load_model_metadata

    metadata_a = load_model_metadata(model_name, version_a, registry_dir)
    metadata_b = load_model_metadata(model_name, version_b, registry_dir)
    comparison = compare_model_metrics(
        metrics_a=normalize_artifact_metrics(metadata_a["metrics"]),
        metrics_b=normalize_artifact_metrics(metadata_b["metrics"]),
        label_a=f"{model_name}@{version_a}",
        label_b=f"{model_name}@{version_b}",
        primary_metric=primary_metric,
    )
    comparison["evaluation_type"] = "registry_metadata_ab"
    return comparison


def save_ab_evaluation_report(
    comparison: Mapping[str, Any],
    output_path: Path | str,
) -> Path:
    """Persist A/B model comparison report to JSON.

    Args:
        comparison: Comparison payload from A/B helpers.
        output_path: Destination JSON path.

    Returns:
        Path: Written report path.
    """
    destination = Path(output_path)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as handle:
            json.dump(dict(comparison), handle, indent=2)
    except Exception as exc:
        raise RuntimeError(f"Failed to save A/B evaluation report: {destination}") from exc
    return destination

