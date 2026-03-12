# Infrastructure Change: Add Cloud Armor to Public API Gateway

## Summary

Our public API gateway (`api.example.com`) is receiving DDoS attacks and credential
stuffing attempts. We need to add Google Cloud Armor to rate-limit requests and block
known malicious IP ranges.

## Current State

- Load balancer: Global HTTPS Load Balancer (Terraform: `modules/networking/lb.tf`)
- Backend: Cloud Run service `api-service`
- No WAF or rate limiting currently

## Desired State

- Cloud Armor security policy attached to the load balancer backend service
- Rate limiting: 100 requests/minute per IP globally
- Rate limiting: 20 requests/minute per IP for `/api/v1/auth/*` endpoints
- Block OWASP CRS common attack signatures (managed rule set)
- Alert on blocked requests > 100/minute

## Terraform Scope

- `modules/networking/cloud_armor.tf` — new file
- `modules/networking/lb.tf` — attach security policy to backend service
- `modules/monitoring/alerts.tf` — new alert policy

## Constraints

- Must not interrupt existing traffic
- Must not block legitimate high-volume API clients (whitelist via `var.trusted_cidrs`)
- All changes must be applied to `staging` environment first and validated

## Acceptance Criteria

- [ ] Terraform plan shows only the expected resource changes
- [ ] Cloud Armor policy attached in staging; no legitimate traffic blocked
- [ ] Rate limiting verified with load test
- [ ] OWASP managed rule set enabled
- [ ] Alert fires correctly in staging

## Security Requirements

- IAM: no new IAM bindings beyond what Cloud Armor requires
- All variables read from Secret Manager / Terraform variables (no hardcoding)
- Rollback plan: detach security policy (no data loss risk)
