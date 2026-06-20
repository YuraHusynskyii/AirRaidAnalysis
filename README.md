# AirRaidAnalysis

Production-oriented ML pipeline for forecasting Ukrainian air raid alert time series — from raw data ingestion to model registry, monitoring, and a secured inference API.

---

## Business Value

Air raid alerts directly affect public safety, logistics, and operational planning. Manual interpretation of alert patterns does not scale across regions and time windows.

**AirRaidAnalysis** solves the reliability gap in alert forecasting by providing:

- **Reproducible forecasting pipeline** — validated ingestion, hourly aggregation, feature engineering, and multiple baseline/ML models
- **Operational confidence** — post-retrain monitoring (metric degradation, data drift, A/B model comparison)
- **Production-ready serving** — FastAPI inference API with rate limiting (HTTP 429), API key auth, Prometheus metrics, and OpenTelemetry tracing
- **Deployability** — Docker, Kubernetes manifests, and a [production runbook](deploy/production_runbook.md)

The result: a system teams can **train, evaluate, deploy, monitor, and roll back** — not just a one-off notebook experiment.

---

## DEMO — Quick Start

Run the full local demo in under 5 minutes:

```bash
# 1. Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Verify quality gate
python -m pytest -q

# 3. Train & evaluate baselines
python -m src.main

# 4. Register production model
python -m src.retrain

# 5. Start inference API
python -m src.serving
```

In a second terminal:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/metrics
curl http://127.0.0.1:8000/v1/models/xgboost_global
```

Docker alternative:

```bash
docker compose build
docker compose run --rm pipeline
docker compose run --rm retrain
docker compose up serve redis
```

---

## Technology Stack

| Layer | Technologies |
|---|---|
| Data & ML | pandas, numpy, scikit-learn, statsmodels, XGBoost, LightGBM, Optuna |
| API & serving | FastAPI, uvicorn, Redis (shared rate limit) |
| Observability | Prometheus, OpenTelemetry (OTLP), Grafana templates |
| Config & validation | Pydantic, pydantic-settings, YAML |
| Production | Docker, Kubernetes, GitHub Actions CI |
| Quality | pytest, ruff |

---

## Production Readiness

| Capability | Status |
|---|---|
| Model registry + scheduled retrain | ✅ |
| Inference API (auth, rate limit, batch predict) | ✅ |
| Monitoring (degradation, drift, A/B) | ✅ |
| Observability (metrics, traces, Grafana) | ✅ |
| Deploy docs + rollback runbook | ✅ [`deploy/production_runbook.md`](deploy/production_runbook.md) |

Additional ops docs: [`deploy/STORAGE.md`](deploy/STORAGE.md), [`deploy/HARDENING.md`](deploy/HARDENING.md), [`deploy/SECRETS.md`](deploy/SECRETS.md), [`deploy/slo.md`](deploy/slo.md).

---

## Architecture Overview

```text
AirRaidAnalysis/
├── src/                     # Core pipeline, serving, monitoring
├── configs/                 # Experiment YAML
├── data/raw|processed/      # Datasets
├── models/                  # Model registry artifacts
├── reports/                 # Metrics, drift, A/B, monitoring
├── deploy/                  # K8s, Grafana, production runbook
├── scripts/                 # retrain, load test, key rotation
├── tests/                   # pytest suite (80+ tests)
├── notebooks/01_eda.ipynb   # EDA dashboard
├── PLAN.md                  # Roadmap
└── LOG.md                   # Development journal
```

**Pipeline flow:** `ingest → preprocess → features → evaluate → [optional tuning] → registry → serve`

---

## Key Commands

| Task | Command |
|---|---|
| Run tests | `python -m pytest -q` |
| Full pipeline | `python -m src.main` |
| Retrain + register | `python -m src.retrain` |
| Inference API | `python -m src.serving` |
| Load test + SLO | `./scripts/load_test_serve.sh --requests 100` |
| Rotate API key | `./scripts/rotate_api_key.sh` |

---

## Inference API

| Endpoint | Description |
|---|---|
| `GET /health` | Liveness probe |
| `GET /metrics` | Prometheus metrics |
| `GET /v1/models/{name}` | Model metadata |
| `POST /v1/predict` | Single prediction |
| `POST /v1/predict/batch` | Batch regional predictions |

Security: API key auth (401), rate limit (429), optional Redis backend for multi-replica deployments.

---

## Data Sources

| Source | Config |
|---|---|
| Local CSV | `AIRRAID_DATA_SOURCE_TYPE=local_csv` |
| Remote CSV | `data_source.type: remote_csv` |
| alerts.in.ua active API | `alerts_in_ua_api` + token |
| alerts.in.ua history API | `alerts_in_ua_history` + region UIDs |

Token: [alerts.in.ua/api-request](https://alerts.in.ua/api-request)

---

## Kubernetes Deploy

```bash
kubectl apply -f deploy/k8s-pvc.yaml
kubectl apply -f deploy/k8s-redis.yaml
kubectl apply -f deploy/k8s-cronjob.yaml
kubectl apply -f deploy/k8s-deployment.yaml
```

Full procedure: **[deploy/production_runbook.md](deploy/production_runbook.md)**

---

## CI

GitHub Actions: `.github/workflows/ci.yml` — ruff, pytest, Docker build smoke test.

---

## Module Reference

| Module | Purpose |
|---|---|
| `src/ingestion.py` | CSV loading + data contracts |
| `src/preprocessing.py` | Datetime index, resample |
| `src/features.py` | Calendar/lag features |
| `src/baseline.py` | Seasonal naive, ARIMA, XGBoost, LightGBM |
| `src/evaluation.py` | Metrics, A/B comparison, reports |
| `src/monitoring.py` | Degradation alerts, drift detection |
| `src/registry.py` | Model artifact versioning |
| `src/serving.py` | FastAPI inference API |
| `src/retrain.py` | Scheduled retraining workflow |
| `src/rate_limit.py` | HTTP 429 middleware |
| `src/auth.py` | API key authentication |
| `src/tracing.py` | OpenTelemetry helpers |
| `src/load_test.py` | Load test + SLO validation |

---

## Configuration

Default experiment: `configs/experiment_default.yaml`

Environment overrides use prefix `AIRRAID_`:

```bash
export AIRRAID_TEST_SIZE=0.2
export AIRRAID_ENABLE_TUNING=true
export AIRRAID_SERVING_API_KEY_ENABLED=true
```

---

## Project Status

**Ready for production deployment and public review.**

Detailed iteration history: [`LOG.md`](LOG.md) · Roadmap: [`PLAN.md`](PLAN.md)
