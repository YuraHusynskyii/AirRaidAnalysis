# PLAN: AirRaidAnalysis

## Мета
Побудувати надійний пайплайн аналізу часових рядів повітряних тривог в Україні: від підготовки даних до production deploy, monitoring та rollback.

## Статус проєкту: ✅ COMPLETE

Проєкт готовий до публічного рев'ю та production deployment.

| Етап | Статус |
|---|---|
| Scaffold + data contracts | ✅ |
| Ingestion / preprocessing / features | ✅ |
| Baseline + advanced ML models | ✅ |
| Evaluation (global + regional) | ✅ |
| Model registry + retrain | ✅ |
| Inference API (auth, rate limit, batch) | ✅ |
| Monitoring (degradation, drift, A/B) | ✅ |
| Observability (Prometheus, OTEL, Grafana) | ✅ |
| Production runbook + rollback | ✅ |
| CI (ruff, pytest, docker) | ✅ |
| Recruiter-ready README | ✅ |

## Definition of Done

| Критерій | Статус |
|---|---|
| Відтворюваний скрипт raw → model → inference | ✅ |
| Документований звіт з метриками та обмеженнями | ✅ |
| Тести для ключових перетворень і перевірок даних | ✅ (80+ tests) |
| Production deployment runbook | ✅ `deploy/production_runbook.md` |
| Monitoring + drift + A/B evaluation | ✅ |

## Technology Stack

pandas · numpy · scikit-learn · statsmodels · XGBoost · LightGBM · Optuna · FastAPI · Redis · Prometheus · OpenTelemetry · Docker · Kubernetes · pytest · ruff

## Ops Documentation

- [`deploy/production_runbook.md`](deploy/production_runbook.md) — deploy & rollback
- [`deploy/STORAGE.md`](deploy/STORAGE.md) — PVC strategies
- [`deploy/HARDENING.md`](deploy/HARDENING.md) — TLS + NetworkPolicy
- [`deploy/SECRETS.md`](deploy/SECRETS.md) — API key rotation
- [`deploy/slo.md`](deploy/slo.md) — inference SLO
- [`deploy/grafana/`](deploy/grafana/) — dashboards & alerts
