# Inference API SLO

## Targets

| SLO | Target | Config key |
|---|---|---|
| p95 latency | ≤ 500 ms | `slo.inference_p95_seconds: 0.5` |
| Error rate | ≤ 1% | `slo.inference_error_rate_max: 0.01` |

Environment overrides:

```bash
export AIRRAID_SLO_INFERENCE_P95_SECONDS=0.5
export AIRRAID_SLO_INFERENCE_ERROR_RATE_MAX=0.01
```

## Load test

```bash
python -m src.load_test_cli --base-url http://localhost:8000 --path /health --requests 100
```

Exit code `0` = SLO met, `1` = SLO breached.

Example against predict endpoint (requires registered model + features):

```bash
python -m src.load_test_cli \
  --base-url http://localhost:8000 \
  --path /v1/predict \
  --requests 50 \
  --api-key "$AIRRAID_SERVING_API_KEY"
```

## Prometheus alignment

Grafana alert `AirRaidHighRequestLatencyP95` in `deploy/grafana/alerts.yaml` mirrors the latency SLO (1s warning threshold for prod tuning).
