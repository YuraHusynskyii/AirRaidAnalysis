# API Key Rotation

Zero-downtime rotation accepts both **current** and **previous** keys during rollout.

## Rotate locally

```bash
./scripts/rotate_api_key.sh
# writes configs/api_keys.rotation.json
```

Or:

```bash
python -m src.rotate_secrets --rotation-file configs/api_keys.rotation.json
```

Rotation file format:

```json
{
  "current": "new-key",
  "previous": "old-key",
  "rotated_at_utc": "2026-06-20T12:00:00+00:00"
}
```

## Enable on serve

```bash
export AIRRAID_SERVING_API_KEY_ENABLED=true
export AIRRAID_SERVING_API_KEYS_ROTATION_FILE=configs/api_keys.rotation.json
python -m src.serving
```

Optional env override:

```bash
export AIRRAID_SERVING_API_KEY=manual-current-key
export AIRRAID_SERVING_API_KEY_PREVIOUS=manual-previous-key
```

## Kubernetes rollout

1. Run rotation script in CI or locally.
2. Update secret `airraid-secrets/inference-api-key` with new current key.
3. Keep previous key in secret `inference-api-key-previous` (or rotation file mounted as ConfigMap/Secret).
4. Rolling restart Deployment `airraid-serve`.
5. After clients migrate, rotate again to drop old previous key.
