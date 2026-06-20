# AirRaidAnalysis

## 📋 Description

**AirRaidAnalysis** is a Python-based data and ML platform for processing, analyzing, and forecasting Ukrainian air raid alert time series. The project transforms raw alert events into structured hourly signals, evaluates forecasting models, and exposes production-ready monitoring and inference capabilities.

Built for reliability and clarity — from sample data exploration to deployable pipelines.

---

## ✨ Features

- 📥 **Data ingestion** — load alerts from local CSV, remote sources, or the alerts.in.ua API with schema validation
- 🧹 **Data processing** — datetime normalization, hourly resampling, and regional aggregation
- 📊 **Feature engineering** — calendar, lag, and weekend features for time-series modeling
- 🤖 **Model evaluation** — seasonal naive, ARIMA/SARIMAX, XGBoost, and LightGBM baselines
- 📦 **Model registry** — versioned artifacts with metadata and retrain workflow
- 🚀 **Inference API** — FastAPI service with auth, rate limiting, and batch predictions
- 🔔 **Monitoring** — metric degradation alerts, data drift detection, and A/B model comparison
- ✅ **Quality assurance** — 89+ automated tests, CI pipeline, and production audit docs

---

## 📂 Sample Data

A demonstration dataset is included for quick exploration:

**`data/samples/sample_alerts.csv`**

It contains timestamped alert records across Ukrainian regions (Kyiv, Kharkiv, Lviv, Odesa, Dnipro). Use it to run the pipeline locally without external API access.

---

## 🛠 Technologies

- **Language:** Python 3.11+
- **Data & ML:** pandas, NumPy, scikit-learn, statsmodels, XGBoost, LightGBM, Optuna
- **API:** FastAPI, uvicorn, Redis
- **Observability:** Prometheus, OpenTelemetry, Grafana templates
- **Config:** Pydantic, YAML
- **DevOps:** Docker, Kubernetes, GitHub Actions
- **Quality:** pytest, ruff

---

## 🚀 How to Run

```bash
# 1. Clone and set up environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Run tests
python -m pytest -q

# 3. Run the pipeline with the sample dataset
export AIRRAID_RAW_DATA_PATH=data/samples/sample_alerts.csv
python -m src.main

# 4. (Optional) Register model and start the inference API
python -m src.retrain
python -m src.serving
```

Verify the API:

```bash
curl http://127.0.0.1:8000/health
```

---

## 📚 Additional Documentation

- [Engineering Reflection](docs/ENGINEERING_REFLECTION.md) — methodology and AI-assisted development process
- [Production Runbook](deploy/production_runbook.md) — deploy and rollback procedures
- [Development Log](LOG.md) — iteration history
