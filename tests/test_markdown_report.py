"""Tests for markdown evaluation report."""

from __future__ import annotations

from pathlib import Path

from src.evaluation import build_markdown_report, save_markdown_report


def test_build_markdown_report_contains_sections() -> None:
    """Markdown report includes global and regional sections."""
    metrics = {
        "global": {
            "seasonal_naive": {"mae": 0.0, "rmse": 0.0, "mape": 0.0},
            "arima": {"mae": 0.1, "rmse": 0.2, "mape": 5.0},
        },
        "regional": {
            "Kyiv": {"seasonal_naive": {"mae": 0.3, "rmse": 0.4, "mape": 6.0}},
        },
    }
    report = build_markdown_report(metrics=metrics, project_name="TestProject")

    assert "# TestProject" in report
    assert "## Global Baselines" in report
    assert "## Regional seasonal_naive (Holdout)" in report
    assert "| seasonal_naive |" in report
    assert "| Kyiv |" in report


def test_save_markdown_report_writes_file(tmp_path: Path) -> None:
    """Markdown report is written to disk."""
    metrics = {
        "global": {
            "seasonal_naive": {"mae": 1.0, "rmse": 1.5, "mape": 10.0},
        },
        "regional": {},
    }
    output_path = tmp_path / "evaluation_summary.md"

    saved_path = save_markdown_report(
        metrics=metrics,
        output_path=output_path,
        project_name="AirRaidAnalysis",
    )

    assert saved_path.exists()
    assert "Global Baselines" in saved_path.read_text(encoding="utf-8")
