"""Scheduled retraining entrypoint for production workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.baseline import fit_xgboost_production_model
from src.config import AppConfig, get_config
from src.evaluation import compare_registry_model_versions, save_ab_evaluation_report
from src.main import run_baseline_evaluation, run_optional_tuning, run_pipeline
from src.monitoring import run_drift_check, run_monitoring_check
from src.registry import (
    load_latest_model_artifact,
    load_previous_model_metadata,
    save_model_artifact,
)
from src.tracing import setup_tracing, trace_span
from src.tuning import register_tuned_xgboost_model


def run_retrain(config: Optional[AppConfig] = None) -> Path:
    """Run full retraining workflow and register production model artifact.

    Workflow:
    1. Ingest + preprocess + feature engineering
    2. Evaluate baselines and save reports
    3. Optionally run Optuna tuning and register tuned model
    4. Otherwise register default production XGBoost model

    Args:
        config: Optional settings override.

    Returns:
        Path: Saved artifact directory for registered production model.

    Raises:
        RuntimeError: If retraining workflow fails.
    """
    active_config = config or get_config()
    setup_tracing(
        enabled=active_config.otel_enabled,
        service_name=f"{active_config.otel_service_name}-retrain",
        exporter_endpoint=active_config.otel_exporter_endpoint,
    )
    try:
        with trace_span("retrain.workflow"):
            previous_metadata = None
            if active_config.monitoring_enabled:
                previous_metadata = load_previous_model_metadata(
                    model_name=active_config.production_model_name,
                    registry_dir=active_config.model_registry_dir,
                )

            with trace_span("retrain.pipeline"):
                processed_df, featured_df, regional_df = run_pipeline(config=active_config)

            if active_config.monitoring_drift_enabled:
                with trace_span("retrain.drift"):
                    drift_result = run_drift_check(
                        featured_df=featured_df,
                        target_column=active_config.target_column,
                        config=active_config,
                    )
                if drift_result.alerts:
                    print(
                        "Drift alerts detected: "
                        f"{len(drift_result.alerts)} ({drift_result.alerts_path})"
                    )

            with trace_span("retrain.evaluate"):
                run_baseline_evaluation(
                    processed_df=processed_df,
                    featured_df=featured_df,
                    regional_df=regional_df,
                    config=active_config,
                )

            tuning_results = run_optional_tuning(
                processed_df=processed_df,
                featured_df=featured_df,
                config=active_config,
            )

            with trace_span("retrain.register"):
                if (
                    tuning_results is not None
                    and active_config.auto_register_tuned_model
                ):
                    artifact_dir = register_tuned_xgboost_model(
                        featured_df=featured_df,
                        target_column=active_config.target_column,
                        test_size=active_config.test_size,
                        random_seed=active_config.random_seed,
                        tuning_results=tuning_results,
                        model_name=active_config.production_model_name,
                        registry_dir=active_config.model_registry_dir,
                    )
                    metrics = tuning_results["xgboost"]
                    model_source = "optuna_tuned"
                else:
                    model, metrics, feature_columns = fit_xgboost_production_model(
                        featured_df=featured_df,
                        target_column=active_config.target_column,
                        test_size=active_config.test_size,
                        random_seed=active_config.random_seed,
                        n_estimators=active_config.boosting_n_estimators,
                    )
                    artifact_dir = save_model_artifact(
                        model=model,
                        model_name=active_config.production_model_name,
                        registry_dir=active_config.model_registry_dir,
                        metrics=metrics,
                        feature_columns=feature_columns,
                        metadata={
                            "source_type": active_config.data_source_type,
                            "rows_processed": len(processed_df),
                            "rows_features": len(featured_df),
                            "tuned": False,
                        },
                    )
                    model_source = "default_xgboost"

            loaded_model, metadata = load_latest_model_artifact(
                model_name=active_config.production_model_name,
                registry_dir=active_config.model_registry_dir,
            )
            if metadata["version"] not in str(artifact_dir):
                raise RuntimeError("Registered artifact failed verification load step.")

            monitoring_summary = ""
            if active_config.monitoring_enabled:
                with trace_span("retrain.monitoring"):
                    monitoring_result = run_monitoring_check(
                        model_name=active_config.production_model_name,
                        current_metadata=metadata,
                        previous_metadata=previous_metadata,
                        config=active_config,
                    )
                if monitoring_result.alerts:
                    monitoring_summary = (
                        f", alerts={len(monitoring_result.alerts)} "
                        f"({monitoring_result.alerts_path})"
                    )
                else:
                    monitoring_summary = ", monitoring=ok"

            if previous_metadata is not None:
                ab_report = compare_registry_model_versions(
                    model_name=active_config.production_model_name,
                    version_a=str(metadata["version"]),
                    version_b=str(previous_metadata["version"]),
                    registry_dir=active_config.model_registry_dir,
                )
                save_ab_evaluation_report(
                    comparison=ab_report,
                    output_path=active_config.ab_evaluation_report_path,
                )

            mae = metrics["best_mae"] if isinstance(metrics, dict) and "best_mae" in metrics else metrics["mae"]
            print(
                "Retrain completed. "
                f"Registered model={active_config.production_model_name}, "
                f"source={model_source}, MAE={mae:.3f}, artifact={artifact_dir}, "
                f"verified_load={type(loaded_model).__name__}"
                f"{monitoring_summary}"
            )
            return artifact_dir
    except Exception as exc:
        raise RuntimeError("Retraining workflow failed.") from exc


def main() -> Path:
    """CLI entrypoint for scheduled retraining jobs."""
    return run_retrain()


if __name__ == "__main__":
    main()
