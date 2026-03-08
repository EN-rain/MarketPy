# Production Environment Setup

## Deploy

1. Build and publish images from CI.
2. Apply manifests:
   - `kubectl apply -f k8s/`
   - `kubectl apply -f k8s/monitoring/`
   - `kubectl apply -f k8s/logging/`
3. Verify ingress TLS and DNS.

## Production Configuration

- Use `config/prod.yaml`.
- Set all secrets through secret manager.
- Enable auth and HTTPS:
  - `SECURITY_ENABLE_AUTH=true`
  - `SECURITY_REQUIRE_HTTPS=true`

## Post-Deployment Verification

- API health endpoint
- dashboard metrics visibility
- alert routing and log indexing
