"""Model registry for persisting and loading production artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import joblib


def _utc_version() -> str:
    """Return UTC timestamp used as artifact version id."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def save_model_artifact(
    model: Any,
    model_name: str,
    registry_dir: Path | str,
    metrics: Dict[str, float],
    feature_columns: list[str],
    metadata: Optional[Dict[str, Any]] = None,
) -> Path:
    """Persist a trained model and metadata to the registry.

    Args:
        model: Fitted model object.
        model_name: Logical model name, e.g. ``xgboost_global``.
        registry_dir: Root registry directory.
        metrics: Validation metrics for this artifact.
        feature_columns: Feature column names used for training.
        metadata: Optional extra metadata fields.

    Returns:
        Path: Directory containing saved artifact files.

    Raises:
        RuntimeError: If artifact persistence fails.
    """
    root = Path(registry_dir)
    version = _utc_version()
    artifact_dir = root / model_name / version

    payload = {
        "model_name": model_name,
        "version": version,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "feature_columns": feature_columns,
        "metadata": metadata or {},
    }

    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, artifact_dir / "model.joblib")
        with (artifact_dir / "metadata.json").open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

        latest_pointer = {
            "model_name": model_name,
            "version": version,
            "artifact_dir": str(artifact_dir),
        }
        model_root = root / model_name
        model_root.mkdir(parents=True, exist_ok=True)
        with (model_root / "latest.json").open("w", encoding="utf-8") as handle:
            json.dump(latest_pointer, handle, indent=2)
    except Exception as exc:
        raise RuntimeError(f"Failed to save model artifact: {model_name}") from exc

    return artifact_dir


def load_latest_model_artifact(
    model_name: str,
    registry_dir: Path | str,
) -> tuple[Any, Dict[str, Any]]:
    """Load latest registered model artifact by name.

    Args:
        model_name: Logical model name.
        registry_dir: Root registry directory.

    Returns:
        tuple[Any, Dict[str, Any]]: Loaded model and metadata dictionary.

    Raises:
        FileNotFoundError: If latest artifact pointer or files are missing.
        RuntimeError: If loading fails unexpectedly.
    """
    root = Path(registry_dir) / model_name
    latest_path = root / "latest.json"
    if not latest_path.exists():
        raise FileNotFoundError(f"Latest artifact pointer not found: {latest_path}")

    try:
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
        artifact_dir = Path(latest["artifact_dir"])
        metadata = json.loads((artifact_dir / "metadata.json").read_text(encoding="utf-8"))
        model = joblib.load(artifact_dir / "model.joblib")
        return model, metadata
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Failed to load latest model artifact: {model_name}") from exc


def list_model_versions(model_name: str, registry_dir: Path | str) -> list[str]:
    """List registered artifact versions sorted newest first.

    Args:
        model_name: Logical model name.
        registry_dir: Root registry directory.

    Returns:
        list[str]: Version directory names.
    """
    model_root = Path(registry_dir) / model_name
    if not model_root.exists():
        return []

    versions = [
        path.name
        for path in model_root.iterdir()
        if path.is_dir() and (path / "metadata.json").exists()
    ]
    return sorted(versions, reverse=True)


def load_model_metadata(
    model_name: str,
    version: str,
    registry_dir: Path | str,
) -> Dict[str, Any]:
    """Load metadata JSON for a specific artifact version.

    Args:
        model_name: Logical model name.
        version: Artifact version id.
        registry_dir: Root registry directory.

    Returns:
        Dict[str, Any]: Artifact metadata payload.

    Raises:
        FileNotFoundError: If metadata file is missing.
        RuntimeError: If metadata cannot be parsed.
    """
    metadata_path = Path(registry_dir) / model_name / version / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Model metadata not found: {metadata_path}")
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Failed to load model metadata: {metadata_path}") from exc


def load_previous_model_metadata(
    model_name: str,
    registry_dir: Path | str,
) -> Optional[Dict[str, Any]]:
    """Load metadata for the second-most-recent artifact version.

    Args:
        model_name: Logical model name.
        registry_dir: Root registry directory.

    Returns:
        Optional[Dict[str, Any]]: Previous artifact metadata or ``None``.
    """
    versions = list_model_versions(model_name=model_name, registry_dir=registry_dir)
    if len(versions) < 2:
        return None
    return load_model_metadata(
        model_name=model_name,
        version=versions[1],
        registry_dir=registry_dir,
    )


def load_model_artifact_by_version(
    model_name: str,
    version: str,
    registry_dir: Path | str,
) -> tuple[Any, Dict[str, Any]]:
    """Load a specific registered model artifact by version id.

    Args:
        model_name: Logical model name.
        version: Artifact version id.
        registry_dir: Root registry directory.

    Returns:
        tuple[Any, Dict[str, Any]]: Loaded model and metadata dictionary.

    Raises:
        FileNotFoundError: If artifact files are missing.
        RuntimeError: If loading fails unexpectedly.
    """
    artifact_dir = Path(registry_dir) / model_name / version
    try:
        metadata = json.loads((artifact_dir / "metadata.json").read_text(encoding="utf-8"))
        model = joblib.load(artifact_dir / "model.joblib")
        return model, metadata
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load model artifact: {model_name}@{version}"
        ) from exc
