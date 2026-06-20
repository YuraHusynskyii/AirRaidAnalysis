"""Tests for API key rotation helpers."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sklearn.linear_model import LinearRegression

from src.auth import is_valid_api_key
from src.config import AppConfig
from src.registry import save_model_artifact
from src.secrets import collect_valid_api_keys, rotate_api_keys
from src.serving import create_app


def test_is_valid_api_key_supports_rotation_set() -> None:
    """Previous and current keys are both accepted during rotation."""
    valid = collect_valid_api_keys(
        primary_key="current-key",
        previous_key="previous-key",
        rotation_file=None,
    )
    assert is_valid_api_key("current-key", valid)
    assert is_valid_api_key("previous-key", valid)
    assert not is_valid_api_key("invalid", valid)


def test_rotate_api_keys_writes_current_and_previous(tmp_path: Path) -> None:
    """Rotation promotes new key and keeps old key as previous."""
    rotation_file = tmp_path / "api_keys.rotation.json"
    rotation_file.write_text(
        json.dumps({"current": "old-current", "previous": None}),
        encoding="utf-8",
    )

    payload = rotate_api_keys(rotation_file=rotation_file, new_key="new-current")

    assert payload["current"] == "new-current"
    assert payload["previous"] == "old-current"


def test_auth_middleware_accepts_previous_key_from_rotation_file(tmp_path: Path) -> None:
    """Serve accepts previous API key from rotation file during rollout."""
    model = LinearRegression()
    model.fit([[1.0], [2.0]], [1.0, 2.0])
    save_model_artifact(
        model=model,
        model_name="test_model",
        registry_dir=tmp_path,
        metrics={"mae": 0.1, "rmse": 0.2, "mape": 1.0},
        feature_columns=["hour"],
    )

    rotation_file = tmp_path / "rotation.json"
    rotation_file.write_text(
        json.dumps({"current": "new-key", "previous": "old-key"}),
        encoding="utf-8",
    )

    config = AppConfig(
        model_registry_dir=tmp_path,
        production_model_name="test_model",
        serving_api_key_enabled=True,
        serving_api_keys_rotation_file=rotation_file,
        serving_rate_limit_enabled=False,
    )
    client = TestClient(create_app(config=config))

    old_key_response = client.get(
        "/v1/models/test_model",
        headers={"X-API-Key": "old-key"},
    )
    new_key_response = client.get(
        "/v1/models/test_model",
        headers={"X-API-Key": "new-key"},
    )

    assert old_key_response.status_code == 200
    assert new_key_response.status_code == 200
