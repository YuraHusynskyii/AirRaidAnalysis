"""FastAPI inference service for registered production models."""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from src.auth import ApiKeyAuthMiddleware
from src.config import AppConfig, get_config
from src.metrics import record_prediction, render_prometheus_metrics
from src.metrics_middleware import PrometheusMetricsMiddleware
from src.rate_limit import RateLimitMiddleware, create_rate_limiter
from src.registry import load_latest_model_artifact
from src.secrets import collect_valid_api_keys
from src.tracing import setup_tracing, trace_span
from src.tracing_middleware import TracingMiddleware


class PredictRequest(BaseModel):
    """Request body for model inference."""

    model_name: Optional[str] = Field(
        default=None,
        description="Registered model name; defaults to production model.",
    )
    features: Dict[str, float] = Field(
        ...,
        description="Feature name -> value mapping matching training columns.",
    )


class PredictResponse(BaseModel):
    """Inference response with model metadata."""

    model_name: str
    version: str
    prediction: float


class BatchPredictItemRequest(BaseModel):
    """One regional or global batch inference row."""

    region: Optional[str] = Field(
        default=None,
        description="Optional region label echoed in the response.",
    )
    features: Dict[str, float] = Field(
        ...,
        description="Feature name -> value mapping matching training columns.",
    )


class BatchPredictRequest(BaseModel):
    """Batch inference request for multiple regional feature rows."""

    model_name: Optional[str] = Field(
        default=None,
        description="Registered model name; defaults to production model.",
    )
    items: list[BatchPredictItemRequest] = Field(
        ...,
        min_length=1,
        description="Batch of feature rows, optionally labeled by region.",
    )


class BatchPredictItemResponse(BaseModel):
    """Single batch inference result."""

    region: Optional[str] = None
    prediction: float


class BatchPredictResponse(BaseModel):
    """Batch inference response."""

    model_name: str
    version: str
    items: list[BatchPredictItemResponse]


class ModelMetadataResponse(BaseModel):
    """Latest registered model metadata."""

    model_name: str
    version: str
    metrics: Dict[str, float]
    feature_columns: list[str]
    metadata: Dict[str, Any]


def predict_from_features(
    model: Any,
    feature_columns: list[str],
    features: Dict[str, float],
) -> float:
    """Run a single-row prediction using ordered feature columns.

    Args:
        model: Fitted sklearn-compatible regressor.
        feature_columns: Column order used during training.
        features: Feature values keyed by column name.

    Returns:
        float: Point prediction.

    Raises:
        ValueError: If required feature columns are missing.
        RuntimeError: If prediction fails unexpectedly.
    """
    missing = [column for column in feature_columns if column not in features]
    if missing:
        raise ValueError(f"Missing feature columns: {missing}")

    row = pd.DataFrame(
        [[features[column] for column in feature_columns]],
        columns=feature_columns,
    )
    try:
        prediction = model.predict(row)[0]
        return float(prediction)
    except Exception as exc:
        raise RuntimeError("Model prediction failed.") from exc


def predict_batch_from_features(
    model: Any,
    feature_columns: list[str],
    feature_rows: list[Dict[str, float]],
) -> list[float]:
    """Run batch predictions for multiple feature rows.

    Args:
        model: Fitted sklearn-compatible regressor.
        feature_columns: Column order used during training.
        feature_rows: List of feature dictionaries.

    Returns:
        list[float]: Predictions aligned with input rows.

    Raises:
        ValueError: If required feature columns are missing in any row.
        RuntimeError: If batch prediction fails unexpectedly.
    """
    if not feature_rows:
        raise ValueError("At least one feature row is required.")

    matrix_rows: list[list[float]] = []
    for index, features in enumerate(feature_rows):
        missing = [column for column in feature_columns if column not in features]
        if missing:
            raise ValueError(f"Row {index} missing feature columns: {missing}")
        matrix_rows.append([features[column] for column in feature_columns])

    batch_frame = pd.DataFrame(matrix_rows, columns=feature_columns)
    try:
        predictions = model.predict(batch_frame)
        return [float(value) for value in predictions]
    except Exception as exc:
        raise RuntimeError("Batch model prediction failed.") from exc


def create_app(config: Optional[AppConfig] = None) -> FastAPI:
    """Build FastAPI application bound to project configuration.

    Args:
        config: Optional settings override (useful for tests).

    Returns:
        FastAPI: Configured inference application.
    """
    active_config = config or get_config()
    setup_tracing(
        enabled=active_config.otel_enabled,
        service_name=active_config.otel_service_name,
        exporter_endpoint=active_config.otel_exporter_endpoint,
    )
    valid_api_keys = collect_valid_api_keys(
        primary_key=active_config.serving_api_key,
        previous_key=active_config.serving_api_key_previous,
        rotation_file=active_config.serving_api_keys_rotation_file,
    )
    rate_limiter = None
    if active_config.serving_rate_limit_enabled:
        rate_limiter = create_rate_limiter(
            backend=active_config.serving_rate_limit_backend,
            max_requests=active_config.serving_rate_limit_requests,
            window_seconds=active_config.serving_rate_limit_window_seconds,
            redis_url=active_config.serving_redis_url,
            redis_key_prefix=active_config.serving_redis_key_prefix,
        )
    app = FastAPI(
        title="AirRaidAnalysis Inference API",
        version="1.0.0",
        description="Serve registered alert forecasting models from the local registry.",
    )
    app.add_middleware(
        RateLimitMiddleware,
        enabled=active_config.serving_rate_limit_enabled,
        max_requests=active_config.serving_rate_limit_requests,
        window_seconds=active_config.serving_rate_limit_window_seconds,
        exempt_paths=set(active_config.serving_rate_limit_exempt_paths),
        limiter=rate_limiter,
    )
    app.add_middleware(
        ApiKeyAuthMiddleware,
        enabled=active_config.serving_api_key_enabled,
        valid_api_keys=valid_api_keys,
        api_key=active_config.serving_api_key,
        exempt_paths=set(active_config.serving_api_key_exempt_paths),
    )
    app.add_middleware(
        TracingMiddleware,
        enabled=active_config.otel_enabled,
    )
    app.add_middleware(
        PrometheusMetricsMiddleware,
        enabled=active_config.serving_metrics_enabled,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        """Liveness probe endpoint."""
        return {
            "status": "ok",
            "project": active_config.project_name,
        }

    if active_config.serving_metrics_enabled:

        @app.get("/metrics")
        def metrics() -> Response:
            """Prometheus metrics exposition endpoint."""
            payload, content_type = render_prometheus_metrics()
            return Response(content=payload, media_type=content_type)

    @app.get("/v1/models/{model_name}", response_model=ModelMetadataResponse)
    def get_model_metadata(model_name: str) -> ModelMetadataResponse:
        """Return metadata for the latest registered model artifact."""
        try:
            _, metadata = load_latest_model_artifact(
                model_name=model_name,
                registry_dir=active_config.model_registry_dir,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return ModelMetadataResponse(
            model_name=metadata["model_name"],
            version=metadata["version"],
            metrics=metadata["metrics"],
            feature_columns=metadata["feature_columns"],
            metadata=metadata.get("metadata", {}),
        )

    @app.post("/v1/predict", response_model=PredictResponse)
    def predict(request: PredictRequest) -> PredictResponse:
        """Predict alert count from a feature vector."""
        model_name = request.model_name or active_config.production_model_name
        try:
            with trace_span(
                "inference.predict",
                attributes={"model.name": model_name},
            ):
                model, metadata = load_latest_model_artifact(
                    model_name=model_name,
                    registry_dir=active_config.model_registry_dir,
                )
                prediction = predict_from_features(
                    model=model,
                    feature_columns=metadata["feature_columns"],
                    features=request.features,
                )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        record_prediction(model_name=model_name, count=1)
        return PredictResponse(
            model_name=model_name,
            version=metadata["version"],
            prediction=prediction,
        )

    @app.post("/v1/predict/batch", response_model=BatchPredictResponse)
    def predict_batch(request: BatchPredictRequest) -> BatchPredictResponse:
        """Predict alert counts for a batch of regional feature rows."""
        model_name = request.model_name or active_config.production_model_name
        try:
            model, metadata = load_latest_model_artifact(
                model_name=model_name,
                registry_dir=active_config.model_registry_dir,
            )
            predictions = predict_batch_from_features(
                model=model,
                feature_columns=metadata["feature_columns"],
                feature_rows=[item.features for item in request.items],
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        record_prediction(model_name=model_name, count=len(predictions))
        return BatchPredictResponse(
            model_name=model_name,
            version=metadata["version"],
            items=[
                BatchPredictItemResponse(
                    region=item.region,
                    prediction=prediction,
                )
                for item, prediction in zip(request.items, predictions, strict=True)
            ],
        )

    return app


app = create_app()


def main() -> None:
    """CLI entrypoint for uvicorn server."""
    import uvicorn

    config = get_config()
    uvicorn.run(
        "src.serving:app",
        host=config.serving_host,
        port=config.serving_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
