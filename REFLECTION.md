# Engineering Reflection: Building AirRaidAnalysis with AI as a Partner

AirRaidAnalysis is a production-oriented ML system for forecasting Ukrainian air raid alert time series. I used AI as an accelerator — Gemini for architecture exploration, Cursor for implementation — but retained ownership of system design, trade-offs, and quality. The goal was not faster code; it was a system that could survive real operations.

## Intentionality: Design Before Generation

AI's default ML output is a linear script: load, train, print metrics. I rejected that shape. I defined an explicit pipeline: **ingestion → preprocessing → features → evaluation → registry → serve → monitor**.

Concrete decisions followed:
- **Data contracts** at ingestion — schema validation before models touch raw alerts.
- **Versioned model registry** — artifacts, metadata, and rollback via `latest.json`, not ad-hoc pickles.
- **Operational monitoring** — metric degradation alerts, feature drift vs. a reference baseline, A/B comparison between registry versions.
- **Production serving** — FastAPI with API key auth, Redis rate limiting, Prometheus, and OpenTelemetry.

AI implemented these boundaries; it did not define them.

## QA & Drift: Trust, But Verify

AI-generated code was untrusted until proven. The project ships **89+ automated tests** (pytest + ruff in CI), API integrity checks in `tests/api_verification.py` (401, 429, `/health` exempt from rate limit), and `scripts/simulate_drift.py` to inject anomalous distributions and verify alerts in `reports/drift_alerts.json`. A Production Readiness Audit (`deploy/audit_report.md`) validated runbook accuracy and secrets hygiene.

## Adaptability: Time Series Is Not Tabular ML

When AI suggested random splits or notebook-only workflows, I redirected toward time-series semantics: **chronological holdout** (no temporal leakage), hourly resampling, calendar/lag features, and baselines matched to the domain — seasonal naive, SARIMAX, XGBoost/LightGBM — with global and regional evaluation. Retrain and rollback paths live in `deploy/production_runbook.md`, because models degrade in production, not only in notebooks.

## Process: Reproducible Decision Trail

Every major step is recorded in **`LOG.md`** across 20 iterations: Context → Writer → QA → Why. That journal turns AI-assisted development into an auditable process — not a black box of prompts.

The result is a repository a technical director can inspect: clear architecture, verified behavior, operational docs, and a path from idea to deployable system. I did not outsource judgment to AI. I used it to accelerate execution while keeping architectural control in human hands.
