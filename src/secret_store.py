"""API key rotation helpers for zero-downtime secret rotation."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def load_api_key_rotation_file(path: Path | str) -> tuple[Optional[str], Optional[str]]:
    """Load current and previous API keys from a rotation JSON file.

    Args:
        path: Rotation file path.

    Returns:
        tuple[Optional[str], Optional[str]]: ``(current, previous)`` keys.

    Raises:
        RuntimeError: If file exists but cannot be parsed.
    """
    rotation_path = Path(path)
    if not rotation_path.exists():
        return None, None

    try:
        payload = json.loads(rotation_path.read_text(encoding="utf-8"))
        current = payload.get("current")
        previous = payload.get("previous")
        return (
            str(current) if current else None,
            str(previous) if previous else None,
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to load API key rotation file: {rotation_path}") from exc


def collect_valid_api_keys(
    primary_key: Optional[str],
    previous_key: Optional[str],
    rotation_file: Optional[Path | str] = None,
) -> set[str]:
    """Collect all currently valid API keys from env/config and rotation file.

    Args:
        primary_key: Primary configured API key.
        previous_key: Previous API key accepted during rotation window.
        rotation_file: Optional JSON file with ``current`` and ``previous`` keys.

    Returns:
        set[str]: Non-empty unique valid keys.
    """
    valid_keys: set[str] = set()
    if primary_key:
        valid_keys.add(primary_key)
    if previous_key:
        valid_keys.add(previous_key)

    if rotation_file is not None:
        file_current, file_previous = load_api_key_rotation_file(rotation_file)
        if file_current:
            valid_keys.add(file_current)
        if file_previous:
            valid_keys.add(file_previous)

    return valid_keys


def rotate_api_keys(
    rotation_file: Path | str,
    new_key: Optional[str] = None,
) -> dict[str, Optional[str]]:
    """Rotate API keys by promoting a new current key and demoting the old one.

    Args:
        rotation_file: Destination JSON file for rotation state.
        new_key: Optional explicit new key; generated when omitted.

    Returns:
        dict[str, Optional[str]]: Updated rotation payload.

    Raises:
        RuntimeError: If rotation file cannot be written.
    """
    rotation_path = Path(rotation_file)
    current_key, _previous_key = load_api_key_rotation_file(rotation_path)
    generated_key = new_key or secrets.token_urlsafe(32)
    payload = {
        "current": generated_key,
        "previous": current_key,
        "rotated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    try:
        rotation_path.parent.mkdir(parents=True, exist_ok=True)
        with rotation_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
    except Exception as exc:
        raise RuntimeError(f"Failed to write API key rotation file: {rotation_path}") from exc

    return payload
