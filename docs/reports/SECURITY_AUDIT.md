# Security Audit

## Checklist

- Authentication and authorization:
  - JWT token issuing and verification implemented.
  - RBAC enforcement for privileged endpoints.
- Input validation:
  - Sanitization applied for text and symbols.
  - Pydantic validation enforced on request models.
- API key protection:
  - API credentials encrypted at rest.
- Rate limiting:
  - Token bucket middleware for API traffic.
- Monitoring:
  - Failed auth tracking and temporary IP blocking.
- HTTPS hardening:
  - HTTPS redirect support and security headers.

## Dependency Scan

- Recommended command: `pip-audit`.
- Integrate into CI as a scheduled workflow step.

## Residual Risks

- JWT secret/bootstrap values must be managed in secure runtime secrets store.
- Production TLS certificate lifecycle must be automated.
