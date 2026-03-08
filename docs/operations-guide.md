# Operations Guide

## Deployment Procedures

- Build images:
  - `docker build -f Dockerfile -t marketpy/backend:latest .`
  - `docker build -f Dockerfile.worker -t marketpy/worker:latest .`
- Deploy to Kubernetes:
  - `kubectl apply -f k8s/`
  - `kubectl apply -f k8s/monitoring/`
  - `kubectl apply -f k8s/logging/`

## Monitoring and Alerting

- Prometheus scrapes backend metrics.
- Grafana dashboards:
  - system metrics dashboard
  - business metrics dashboard
- Alertmanager handles critical/warning notifications.

## Backup and Recovery

- PostgreSQL backups: daily logical dump + WAL archiving.
- Redis snapshot + AOF enabled for fast recovery.
- InfluxDB retention policy:
  - high resolution: 30 days
  - downsampled: 1 year

## Troubleshooting

- API health: `GET /health`.
- WebSocket health: connect to `/ws/live` and send `ping`.
- Common checks:
  - verify blocked IPs under `/api/security/monitoring`
  - inspect pod logs via `kubectl logs`
  - validate ingress TLS secret `marketpy-tls`
