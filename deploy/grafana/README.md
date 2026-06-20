# Grafana Observability

## Dashboard

Import `deploy/grafana/dashboard.json` into Grafana:

1. Grafana → Dashboards → Import
2. Upload JSON or paste file contents
3. Select Prometheus datasource named `Prometheus`

Panels:

- HTTP requests by status
- Predictions per model
- Rate-limit 429 rejections
- Auth failures
- Request latency p95

## Alert rules

Prometheus rule file: `deploy/grafana/alerts.yaml`

Example Prometheus config snippet:

```yaml
rule_files:
  - /etc/prometheus/rules/airraid-alerts.yaml

scrape_configs:
  - job_name: airraid-serve
    metrics_path: /metrics
    static_configs:
      - targets: ["airraid-serve:8000"]
```

Alerts:

| Alert | Condition |
|---|---|
| `AirRaidHighRateLimitRejections` | >10 HTTP 429 in 5m |
| `AirRaidAuthFailuresSpike` | >5 auth failures in 5m |
| `AirRaidHighRequestLatencyP95` | p95 latency > 1s for 10m |
| `AirRaidNoPredictions` | zero predictions for 1h |
