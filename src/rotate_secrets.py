"""CLI entrypoint for API key rotation."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.config import get_config
from src.secret_store import rotate_api_keys


def main() -> Path:
    """Rotate inference API keys and persist rotation state."""
    parser = argparse.ArgumentParser(description="Rotate AirRaidAnalysis inference API key.")
    parser.add_argument(
        "--rotation-file",
        type=Path,
        default=None,
        help="Rotation JSON path (defaults to config serving_api_keys_rotation_file).",
    )
    parser.add_argument(
        "--new-key",
        default=None,
        help="Optional explicit new API key (generated when omitted).",
    )
    args = parser.parse_args()

    config = get_config()
    rotation_file = args.rotation_file or config.serving_api_keys_rotation_file
    payload = rotate_api_keys(rotation_file=rotation_file, new_key=args.new_key)

    print(
        "API key rotated. "
        f"file={rotation_file}, "
        f"current={payload['current']}, "
        f"previous={'set' if payload.get('previous') else 'none'}"
    )
    return rotation_file


if __name__ == "__main__":
    main()
