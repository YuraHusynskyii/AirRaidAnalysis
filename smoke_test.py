#!/usr/bin/env python3
"""End-to-end smoke test for the AirRaidAnalysis pipeline."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
INPUT_CSV = PROJECT_ROOT / "data" / "samples" / "sample_alerts.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "results"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"

EXPECTED_OUTPUTS = [
    OUTPUT_DIR / "alerts_processed.csv",
    OUTPUT_DIR / "alerts_features.csv",
    OUTPUT_DIR / "baseline_metrics.json",
    OUTPUT_DIR / "evaluation_summary.md",
]


def _fail(message: str) -> None:
    print(f"❌ СМОК-ТЕСТ НЕ ПРОЙДЕНО: {message}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    if not INPUT_CSV.is_file() or INPUT_CSV.stat().st_size == 0:
        _fail(f"вхідний файл відсутній або порожній: {INPUT_CSV}")

    if not VENV_PYTHON.is_file():
        _fail(f"не знайдено Python у віртуальному середовищі: {VENV_PYTHON}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(VENV_PYTHON),
        str(PROJECT_ROOT / "src" / "main.py"),
        "--input",
        str(INPUT_CSV),
        "--output",
        str(OUTPUT_DIR),
    ]

    print(f"Запуск пайплайну: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    if result.returncode != 0:
        _fail(f"пайплайн завершився з кодом {result.returncode}")

    missing = [path for path in EXPECTED_OUTPUTS if not path.is_file() or path.stat().st_size == 0]
    if missing:
        names = ", ".join(path.name for path in missing)
        _fail(f"очікувані файли результатів відсутні або порожні: {names}")

    print("✅ СМОК-ТЕСТ УСПІШНО ПРОЙДЕНО: Пайплайн працює, файли збережено!")
    for path in EXPECTED_OUTPUTS:
        print(f"  • {path.relative_to(PROJECT_ROOT)} ({path.stat().st_size} байт)")


if __name__ == "__main__":
    main()
