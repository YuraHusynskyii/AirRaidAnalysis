# Kubernetes Storage Notes

## Profiles

| Manifest | Access mode | Use case |
|---|---|---|
| `k8s-pvc.yaml` | `ReadWriteOnce` | Single-node / dev clusters |
| `k8s-pvc-rwx.yaml` | `ReadWriteMany` | Multi-node HA (NFS, EFS, CephFS, etc.) |

## ReadWriteOnce (default)

- CronJob retrain and Deployment serve must schedule on the **same node** to share `models/`.
- Simplest option for local clusters (`kind`, `minikube`, single-node prod).

Apply:

```bash
kubectl apply -f deploy/k8s-pvc.yaml
```

## ReadWriteMany (multi-node HA)

Use when retrain CronJob and serve Deployment may run on different nodes.

Requirements:

1. Cluster storage class that supports `ReadWriteMany` (e.g. NFS, AWS EFS, Azure Files).
2. Update `storageClassName` in `k8s-pvc-rwx.yaml` to match your cluster.
3. Point both manifests to the same claim name:

```yaml
persistentVolumeClaim:
  claimName: airraid-shared-rwx
```

Apply:

```bash
kubectl apply -f deploy/k8s-pvc-rwx.yaml
kubectl apply -f deploy/k8s-cronjob.yaml
kubectl apply -f deploy/k8s-deployment.yaml
```

## Prometheus scraping

Serve exposes `GET /metrics` (exempt from API key auth by default). Example pod annotation:

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/path: /metrics
    prometheus.io/port: "8000"
```

Protect `/metrics` with network policies in production if the endpoint is cluster-internal only.
