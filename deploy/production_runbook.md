# Production Deployment Runbook — AirRaidAnalysis

Операційний посібник для деплою inference + retrain pipeline у production та відкату при інцидентах.

## 1. Prerequisites

| Компонент | Вимога |
|---|---|
| Python | 3.11+ (Docker image: 3.12) |
| Container registry | Docker image `airraidanalysis:latest` |
| Kubernetes | 1.25+ (optional, recommended) |
| Storage | PVC для `models/`, `reports/` |
| Secrets | `AIRRAID_ALERTS_IN_UA_TOKEN`, `AIRRAID_SERVING_API_KEY` |
| Observability | Prometheus scrape `/metrics`, optional OTLP collector |

Перевірка локально перед prod:

```bash
python -m pytest -q
python -m src.main
python -m src.retrain
python -m src.serving
curl http://127.0.0.1:8000/health
```

---

## 2. Deploy (Kubernetes)

### 2.1 Build & push image

```bash
docker build -t airraidanalysis:latest .
docker tag airraidanalysis:latest <registry>/airraidanalysis:latest
docker push <registry>/airraidanalysis:latest
```

Оновіть image tag у `deploy/k8s-deployment.yaml` та `deploy/k8s-cronjob.yaml`, якщо використовуєте registry tag замість `latest`.

### 2.2 Configure secrets (до rollout pod-ів)

```bash
kubectl create secret generic airraid-secrets \
  --from-literal=alerts-in-ua-token="$AIRRAID_ALERTS_IN_UA_TOKEN" \
  --from-literal=inference-api-key="$AIRRAID_SERVING_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -
```

> **Важливо:** secret має існувати **до** запуску `airraid-serve` і `airraid-retrain`, інакше pod-и не піднімуться.

### 2.3 Apply manifests (order matters)

```bash
kubectl apply -f deploy/k8s-pvc.yaml
kubectl apply -f deploy/k8s-redis.yaml
kubectl apply -f deploy/k8s-cronjob.yaml
kubectl apply -f deploy/k8s-deployment.yaml
# Optional hardening (production only):
kubectl apply -f deploy/k8s-networkpolicy.yaml
kubectl apply -f deploy/k8s-ingress-tls.yaml
```

### 2.4 Initial model registration

```bash
kubectl create job --from=cronjob/airraid-retrain airraid-retrain-initial
kubectl wait --for=condition=complete job/airraid-retrain-initial --timeout=30m
kubectl logs job/airraid-retrain-initial
```

Очікуваний результат: artifact у PVC `models/xgboost_global/<version>/` та `models/xgboost_global/latest.json`.

### 2.5 Verify deployment

```bash
kubectl rollout status deployment/airraid-serve
kubectl port-forward svc/airraid-serve 8000:8000
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/metrics
curl -H "X-API-Key: $AIRRAID_SERVING_API_KEY" \
  http://127.0.0.1:8000/v1/models/xgboost_global
./scripts/load_test_serve.sh --requests 50
python -m pytest tests/api_verification.py -q
```

---

## 3. Deploy (Docker Compose — staging)

```bash
docker compose build
docker compose run --rm pipeline
docker compose run --rm retrain
docker compose up -d serve redis
curl http://127.0.0.1:8000/health
```

---

## 4. Rollback

### 4.1 Rollback inference model (registry)

1. Identify previous artifact version:

```bash
ls -1 models/xgboost_global/
cat models/xgboost_global/latest.json
# Example output: {"version": "20260620_153045_123456", ...}
```

2. Point `latest.json` to previous version (manual rollback):

```bash
PREVIOUS_VERSION="<PREVIOUS_VERSION>"
cat > models/xgboost_global/latest.json <<EOF
{
  "model_name": "xgboost_global",
  "version": "${PREVIOUS_VERSION}",
  "artifact_dir": "models/xgboost_global/${PREVIOUS_VERSION}"
}
EOF
```

3. Restart serve pods:

```bash
kubectl rollout restart deployment/airraid-serve
kubectl rollout status deployment/airraid-serve
# або для Docker Compose:
docker compose restart serve
```

4. Verify:

```bash
curl -H "X-API-Key: $AIRRAID_SERVING_API_KEY" \
  http://127.0.0.1:8000/v1/models/xgboost_global
```

### 4.2 Rollback application release

```bash
kubectl rollout history deployment/airraid-serve
kubectl rollout undo deployment/airraid-serve
kubectl rollout status deployment/airraid-serve
```

For CronJob image rollback:

```bash
# 1) Restore previous image tag in deploy/k8s-cronjob.yaml
# 2) Re-apply manifest
kubectl apply -f deploy/k8s-cronjob.yaml
```

### 4.3 Rollback after bad retrain

Symptoms:

| Alert file | Meaning |
|---|---|
| `reports/monitoring_alerts.json` | Model metric degradation (MAE/RMSE/MAPE) |
| `reports/drift_alerts.json` | Input feature drift vs reference baseline |

Actions:

1. Do **not** promote new artifact — rollback registry as in **4.1**.
2. Review `reports/ab_evaluation.json` — confirm previous model was better.
3. Inspect drift reference: `reports/drift_reference.json`.
4. Re-run retrain after fixing upstream data source:

```bash
python -m src.retrain
# або в K8s:
kubectl create job --from=cronjob/airraid-retrain airraid-retrain-manual
```

### 4.4 Rollback API key rotation

```bash
# Restore previous key as current (dual-key window keeps old key valid temporarily)
./scripts/rotate_api_key.sh --new-key "<PREVIOUS_KEY>"
kubectl rollout restart deployment/airraid-serve
kubectl rollout status deployment/airraid-serve
```

See `deploy/SECRETS.md` for dual-key rotation window.

---

## 5. Post-deploy checklist

- [ ] `/health` returns 200 (exempt from rate limit)
- [ ] `/metrics` scraped by Prometheus
- [ ] Inference predict endpoint returns valid response with valid API key
- [ ] Missing API key returns HTTP 401
- [ ] Rate limit returns HTTP 429 on protected routes
- [ ] CronJob retrain schedule active (`15 3 * * *`)
- [ ] `reports/monitoring_alerts.json` empty after healthy retrain
- [ ] Grafana dashboard imported (`deploy/grafana/dashboard.json`)
- [ ] Load test SLO pass (`./scripts/load_test_serve.sh`)
- [ ] Drift simulation smoke: `python scripts/simulate_drift.py --skip-metric-alert`

---

## 6. Related docs

| Document | Purpose |
|---|---|
| `deploy/STORAGE.md` | RWO vs RWX PVC |
| `deploy/HARDENING.md` | TLS + NetworkPolicy |
| `deploy/SECRETS.md` | API key rotation |
| `deploy/slo.md` | Latency/error SLO |
| `deploy/grafana/README.md` | Dashboards & alerts |
| `deploy/audit_report.md` | Production readiness audit |
