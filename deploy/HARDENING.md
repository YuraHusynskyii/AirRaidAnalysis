# Production Hardening (TLS + NetworkPolicy)

## TLS termination

`deploy/k8s-ingress-tls.yaml` exposes the inference API via Ingress with TLS.

Before apply:

1. Replace `inference.example.com` with your domain.
2. Ensure cert-manager `ClusterIssuer` `letsencrypt-prod` exists (or change annotation).
3. Install ingress-nginx (or adjust `ingressClassName`).

```bash
kubectl apply -f deploy/k8s-ingress-tls.yaml
```

External clients hit HTTPS on Ingress; serve pod still listens HTTP on port 8000 inside the cluster.

Recommended headers at Ingress:

- `X-Forwarded-For` — used by rate limiter for client IP behind proxy
- TLS 1.2+ only at ingress controller level

## NetworkPolicy

`deploy/k8s-networkpolicy.yaml` restricts pod ingress to:

- `ingress-nginx` namespace — public API traffic
- `monitoring` namespace — Prometheus scrape of `/metrics`

Adjust namespace labels to match your cluster:

```bash
kubectl label namespace ingress-nginx kubernetes.io/metadata.name=ingress-nginx
kubectl label namespace monitoring kubernetes.io/metadata.name=monitoring
kubectl apply -f deploy/k8s-networkpolicy.yaml
```

`/metrics` is not exposed publicly when only monitoring namespace can reach port 8000 directly. Public clients use Ingress paths you configure (exclude `/metrics` from Ingress rules in production).

## Multi-replica rate limiting

Set Redis backend so all serve replicas share counters:

```yaml
serving:
  rate_limit:
    backend: redis
    redis_url: redis://airraid-redis:6379/0
```

See `docker-compose.yml` for local Redis + serve example.
