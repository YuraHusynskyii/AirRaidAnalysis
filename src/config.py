"""Project configuration models and defaults."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Application settings for local development and experiments.

    Attributes:
        project_name: Human-readable project identifier.
        raw_data_path: Path to raw source data.
        processed_data_path: Path to processed datasets.
        target_column: Target column name used in modeling.
        datetime_column: Datetime column name used for indexing.
        timezone: IANA timezone string for datetime normalization.
        random_seed: Seed for deterministic operations.
        test_size: Validation split ratio for simple experiments.
        season_period: Seasonal lag for naive baseline (hourly data default: 24).
        lag_periods: Lag steps for feature engineering.
        features_data_path: Path to feature-enriched dataset.
        baseline_metrics_path: Path to baseline comparison report (JSON).
        summary_report_path: Path to markdown evaluation summary.
        arima_order: ARIMA (p, d, q) order for statsmodels baseline.
        seasonal_order: Seasonal ARIMA (P, D, Q, s) order for non-seasonal ARIMA key.
        sarimax_seasonal_order: Seasonal SARIMAX (P, D, Q, s) with ``s=24``.
        extended_raw_data_path: Optional larger dataset for seasonal SARIMAX tuning.
        boosting_n_estimators: Number of trees for XGBoost/LightGBM baselines.
        data_source_type: Data source mode: ``local_csv`` or ``remote_csv``.
        data_source_url: Remote CSV URL when ``data_source_type=remote_csv``.
        data_source_column_map: Optional source->schema column mapping.
        enable_tuning: Whether to run Optuna tuning after baseline evaluation.
        tuning_trials: Number of Optuna trials per tuned model.
        tuning_results_path: Path to JSON tuning report.
        alerts_in_ua_token: API token for alerts.in.ua production API.
        alerts_in_ua_api_url: alerts.in.ua endpoint URL.
        model_registry_dir: Directory for saved model artifacts.
        production_model_name: Default registered production model name.
        alerts_in_ua_history_base_url: Base URL for regional history API.
        alerts_in_ua_history_period: History period slug (e.g. month_ago).
        alerts_in_ua_region_uids: Region UIDs to pull history for.
        auto_register_tuned_model: Register Optuna-tuned model in registry.
        api_max_retries: Retry count for alerts.in.ua HTTP/network failures.
        api_retry_backoff_seconds: Base backoff delay between API retries.
        api_rate_limit_seconds: Pause between multi-region history requests.
        serving_host: Host for FastAPI inference server.
        serving_port: Port for FastAPI inference server.
        monitoring_enabled: Whether to run post-retrain degradation checks.
        monitoring_degradation_threshold: Relative metric increase alert threshold.
        monitoring_history_path: JSON file storing retrain metric history.
        monitoring_alerts_path: JSON file with latest degradation alerts.
        monitoring_webhook_url: Optional webhook URL for degradation alerts.
        serving_rate_limit_enabled: Enable inference API rate limiting middleware.
        serving_rate_limit_requests: Max requests per client per window.
        serving_rate_limit_window_seconds: Rate limit sliding window in seconds.
        serving_rate_limit_exempt_paths: Paths excluded from rate limiting.
        serving_api_key_enabled: Enable API key auth on inference endpoints.
        serving_api_key: Expected API key for protected inference routes.
        serving_api_key_exempt_paths: Paths excluded from API key auth.
        serving_metrics_enabled: Enable Prometheus `/metrics` endpoint.
        serving_rate_limit_backend: Rate limit backend: ``memory`` or ``redis``.
        serving_redis_url: Redis URL for shared rate limiting across replicas.
        serving_redis_key_prefix: Redis key prefix for rate limit sorted sets.
        monitoring_drift_enabled: Enable feature drift checks during retrain.
        monitoring_drift_threshold: Relative mean drift threshold for features.
        monitoring_drift_reference_path: Baseline feature stats JSON path.
        monitoring_drift_alerts_path: Drift alerts JSON output path.
        ab_evaluation_report_path: JSON report path for model A/B comparisons.
        otel_enabled: Enable OpenTelemetry tracing export.
        otel_service_name: OpenTelemetry service name.
        otel_exporter_endpoint: OTLP HTTP traces endpoint.
        serving_api_key_previous: Previous API key accepted during rotation window.
        serving_api_keys_rotation_file: JSON file storing current/previous API keys.
        slo_inference_p95_seconds: SLO target for inference p95 latency.
        slo_inference_error_rate_max: SLO target for max inference error rate.
    """

    model_config = SettingsConfigDict(
        env_prefix="AIRRAID_",
        env_file=".env",
        extra="ignore",
    )

    project_name: str = "AirRaidAnalysis"
    raw_data_path: Path = Path("data/raw/alerts.csv")
    processed_data_path: Path = Path("data/processed/alerts_processed.csv")
    features_data_path: Path = Path("data/processed/alerts_features.csv")
    baseline_metrics_path: Path = Path("reports/baseline_metrics.json")
    summary_report_path: Path = Path("reports/evaluation_summary.md")
    target_column: str = "alert_count"
    datetime_column: str = "timestamp"
    timezone: str = "Europe/Kyiv"
    random_seed: int = 42
    test_size: float = Field(default=0.2, ge=0.05, le=0.5)
    season_period: int = Field(default=24, ge=1)
    lag_periods: list[int] = Field(default_factory=lambda: [1, 24])
    arima_order: list[int] = Field(default_factory=lambda: [1, 0, 0])
    seasonal_order: list[int] = Field(default_factory=lambda: [0, 0, 0, 0])
    sarimax_seasonal_order: list[int] = Field(default_factory=lambda: [1, 0, 0, 24])
    extended_raw_data_path: Optional[Path] = Path("data/raw/alerts_extended.csv")
    boosting_n_estimators: int = Field(default=100, ge=10, le=1000)
    data_source_type: str = Field(default="local_csv")
    data_source_url: Optional[str] = None
    data_source_column_map: Optional[dict[str, str]] = None
    enable_tuning: bool = False
    tuning_trials: int = Field(default=10, ge=2, le=100)
    tuning_results_path: Path = Path("reports/tuning_results.json")
    alerts_in_ua_token: Optional[str] = None
    alerts_in_ua_api_url: str = "https://api.alerts.in.ua/v1/alerts/active.json"
    alerts_in_ua_history_base_url: str = "https://api.alerts.in.ua/v1/regions"
    alerts_in_ua_history_period: str = "month_ago"
    alerts_in_ua_region_uids: list[int] = Field(default_factory=lambda: [16])
    model_registry_dir: Path = Path("models")
    production_model_name: str = "xgboost_global"
    auto_register_tuned_model: bool = True
    api_max_retries: int = Field(default=3, ge=0, le=10)
    api_retry_backoff_seconds: float = Field(default=1.0, ge=0.0, le=60.0)
    api_rate_limit_seconds: float = Field(default=0.5, ge=0.0, le=60.0)
    serving_host: str = "0.0.0.0"
    serving_port: int = Field(default=8000, ge=1024, le=65535)
    monitoring_enabled: bool = True
    monitoring_degradation_threshold: float = Field(default=0.15, ge=0.0, le=5.0)
    monitoring_history_path: Path = Path("reports/metrics_history.json")
    monitoring_alerts_path: Path = Path("reports/monitoring_alerts.json")
    monitoring_webhook_url: Optional[str] = None
    serving_rate_limit_enabled: bool = True
    serving_rate_limit_requests: int = Field(default=60, ge=1, le=10000)
    serving_rate_limit_window_seconds: float = Field(default=60.0, ge=1.0, le=3600.0)
    serving_rate_limit_exempt_paths: list[str] = Field(
        default_factory=lambda: ["/health", "/metrics"]
    )
    serving_api_key_enabled: bool = False
    serving_api_key: Optional[str] = None
    serving_api_key_exempt_paths: list[str] = Field(
        default_factory=lambda: ["/health", "/metrics"]
    )
    serving_metrics_enabled: bool = True
    serving_rate_limit_backend: str = Field(default="memory")
    serving_redis_url: Optional[str] = "redis://localhost:6379/0"
    serving_redis_key_prefix: str = "airraid:ratelimit"
    otel_enabled: bool = False
    otel_service_name: str = "airraidanalysis-serve"
    otel_exporter_endpoint: Optional[str] = "http://localhost:4318/v1/traces"
    serving_api_key_previous: Optional[str] = None
    serving_api_keys_rotation_file: Path = Path("configs/api_keys.rotation.json")
    slo_inference_p95_seconds: float = Field(default=0.5, ge=0.01, le=30.0)
    slo_inference_error_rate_max: float = Field(default=0.01, ge=0.0, le=1.0)
    monitoring_drift_enabled: bool = True
    monitoring_drift_threshold: float = Field(default=0.25, ge=0.0, le=5.0)
    monitoring_drift_reference_path: Path = Path("reports/drift_reference.json")
    monitoring_drift_alerts_path: Path = Path("reports/drift_alerts.json")
    ab_evaluation_report_path: Path = Path("reports/ab_evaluation.json")
    region_column: Optional[str] = "region"


def _flatten_experiment_yaml(payload: dict[str, Any]) -> dict[str, Any]:
    """Map nested experiment YAML structure to ``AppConfig`` field names.

    Args:
        payload: Parsed YAML dictionary.

    Returns:
        dict[str, Any]: Flat kwargs for ``AppConfig``.
    """
    paths = payload.get("paths", {})
    columns = payload.get("columns", {})
    time_section = payload.get("time", {})
    modeling = payload.get("modeling", {})
    data_source = payload.get("data_source", {})
    tuning = payload.get("tuning", {})
    api_section = payload.get("api", {})
    registry = payload.get("registry", {})
    monitoring = payload.get("monitoring", {})
    serving = payload.get("serving", {})
    rate_limit = serving.get("rate_limit", {})
    auth = serving.get("auth", {})
    metrics_section = serving.get("metrics", {})
    tracing = payload.get("tracing", {})
    slo = payload.get("slo", {})

    return {
        "project_name": payload.get("project_name", "AirRaidAnalysis"),
        "raw_data_path": Path(paths.get("raw_data", "data/raw/alerts.csv")),
        "processed_data_path": Path(
            paths.get("processed_data", "data/processed/alerts_processed.csv")
        ),
        "features_data_path": Path(
            paths.get("features_data", "data/processed/alerts_features.csv")
        ),
        "baseline_metrics_path": Path(
            paths.get("baseline_metrics", "reports/baseline_metrics.json")
        ),
        "summary_report_path": Path(
            paths.get("summary_report", "reports/evaluation_summary.md")
        ),
        "target_column": columns.get("target", "alert_count"),
        "datetime_column": columns.get("datetime", "timestamp"),
        "region_column": columns.get("region", "region"),
        "timezone": time_section.get("timezone", "Europe/Kyiv"),
        "test_size": modeling.get("test_size", 0.2),
        "season_period": modeling.get("season_period", 24),
        "lag_periods": modeling.get("lag_periods", [1, 24]),
        "random_seed": modeling.get("random_seed", 42),
        "arima_order": payload.get("arima", {}).get("order", [1, 0, 0]),
        "seasonal_order": payload.get("arima", {}).get("seasonal_order", [0, 0, 0, 0]),
        "sarimax_seasonal_order": payload.get("arima", {}).get(
            "sarimax_seasonal_order", [1, 0, 0, 24]
        ),
        "extended_raw_data_path": Path(
            paths.get("extended_raw_data", "data/raw/alerts_extended.csv")
        ),
        "boosting_n_estimators": payload.get("boosting", {}).get("n_estimators", 100),
        "data_source_type": data_source.get("type", "local_csv"),
        "data_source_url": data_source.get("url"),
        "data_source_column_map": data_source.get("column_map"),
        "enable_tuning": tuning.get("enabled", False),
        "tuning_trials": tuning.get("trials", 10),
        "tuning_results_path": Path(
            paths.get("tuning_results", "reports/tuning_results.json")
        ),
        "alerts_in_ua_token": api_section.get("token"),
        "alerts_in_ua_api_url": api_section.get(
            "alerts_in_ua_url",
            "https://api.alerts.in.ua/v1/alerts/active.json",
        ),
        "alerts_in_ua_history_base_url": api_section.get(
            "history_base_url",
            "https://api.alerts.in.ua/v1/regions",
        ),
        "alerts_in_ua_history_period": api_section.get("history_period", "month_ago"),
        "alerts_in_ua_region_uids": api_section.get("region_uids", [16]),
        "api_max_retries": api_section.get("max_retries", 3),
        "api_retry_backoff_seconds": api_section.get("retry_backoff_seconds", 1.0),
        "api_rate_limit_seconds": api_section.get("rate_limit_seconds", 0.5),
        "serving_host": serving.get("host", api_section.get("serving_host", "0.0.0.0")),
        "serving_port": serving.get("port", api_section.get("serving_port", 8000)),
        "serving_rate_limit_enabled": rate_limit.get(
            "enabled",
            serving.get("rate_limit_enabled", True),
        ),
        "serving_rate_limit_requests": rate_limit.get("requests", 60),
        "serving_rate_limit_window_seconds": rate_limit.get("window_seconds", 60.0),
        "serving_rate_limit_backend": rate_limit.get("backend", "memory"),
        "serving_redis_url": rate_limit.get("redis_url", "redis://localhost:6379/0"),
        "serving_redis_key_prefix": rate_limit.get(
            "redis_key_prefix",
            "airraid:ratelimit",
        ),
        "serving_rate_limit_exempt_paths": rate_limit.get(
            "exempt_paths",
            ["/health", "/metrics"],
        ),
        "serving_api_key_enabled": auth.get("enabled", False),
        "serving_api_key": auth.get("api_key"),
        "serving_api_key_previous": auth.get("api_key_previous"),
        "serving_api_keys_rotation_file": Path(
            auth.get("rotation_file", "configs/api_keys.rotation.json")
        ),
        "serving_api_key_exempt_paths": auth.get(
            "exempt_paths",
            ["/health", "/metrics"],
        ),
        "serving_metrics_enabled": metrics_section.get("enabled", True),
        "otel_enabled": tracing.get("enabled", False),
        "otel_service_name": tracing.get("service_name", "airraidanalysis-serve"),
        "otel_exporter_endpoint": tracing.get(
            "exporter_endpoint",
            "http://localhost:4318/v1/traces",
        ),
        "slo_inference_p95_seconds": slo.get("inference_p95_seconds", 0.5),
        "slo_inference_error_rate_max": slo.get("inference_error_rate_max", 0.01),
        "monitoring_enabled": monitoring.get("enabled", True),
        "monitoring_degradation_threshold": monitoring.get(
            "degradation_threshold", 0.15
        ),
        "monitoring_webhook_url": monitoring.get("webhook_url"),
        "monitoring_history_path": Path(
            paths.get("metrics_history", "reports/metrics_history.json")
        ),
        "monitoring_alerts_path": Path(
            paths.get("monitoring_alerts", "reports/monitoring_alerts.json")
        ),
        "monitoring_drift_reference_path": Path(
            paths.get("drift_reference", "reports/drift_reference.json")
        ),
        "monitoring_drift_alerts_path": Path(
            paths.get("drift_alerts", "reports/drift_alerts.json")
        ),
        "ab_evaluation_report_path": Path(
            paths.get("ab_evaluation", "reports/ab_evaluation.json")
        ),
        "monitoring_drift_enabled": monitoring.get("drift_enabled", True),
        "monitoring_drift_threshold": monitoring.get("drift_threshold", 0.25),
        "model_registry_dir": Path(registry.get("dir", "models")),
        "production_model_name": registry.get("production_model", "xgboost_global"),
        "auto_register_tuned_model": tuning.get("auto_register", True),
    }


def load_config_from_yaml(path: Path | str) -> AppConfig:
    """Load validated settings from an experiment YAML file.

    Args:
        path: Path to YAML experiment configuration.

    Returns:
        AppConfig: Validated config object.

    Raises:
        FileNotFoundError: If YAML file does not exist.
        RuntimeError: If parsing or validation fails.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Experiment config not found: {config_path}")

    try:
        with config_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return AppConfig(**_flatten_experiment_yaml(payload))
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load experiment config: {config_path}"
        ) from exc


def get_config(
    experiment_path: Optional[Path | str] = None,
) -> AppConfig:
    """Build and return validated application settings.

    Args:
        experiment_path: Optional YAML experiment config path. When omitted,
            defaults from ``AppConfig`` and environment variables are used.

    Returns:
        AppConfig: Validated config object.

    Raises:
        RuntimeError: If settings validation fails.
    """
    try:
        if experiment_path is not None:
            return load_config_from_yaml(experiment_path)
        return AppConfig()
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise RuntimeError("Failed to initialize application configuration.") from exc

