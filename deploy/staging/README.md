# Staging Environment Setup

## Deploy

```bash
kubectl apply -f k8s/
kubectl apply -f k8s/monitoring/
kubectl apply -f k8s/logging/
```

## Staging Configuration

- Use `config/staging.yaml`.
- Use staging API keys and sandbox exchange credentials.
- Run smoke checks with `scripts/smoke_staging.py`.
