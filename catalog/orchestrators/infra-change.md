---
name: infra-change
description: Infrastructure change pipeline with security audit
entry_agent: planner
terminal_agents:
  - release-manager
quality_threshold: 9
max_rounds: 14
max_no_progress: 2

allowed_handoffs:
  planner:
    - infra-gcp
  infra-gcp:
    - security
  security:
    - reviewer
  reviewer:
    - qa
  qa:
    - release-manager
---

# Infrastructure Change Orchestrator

This orchestrator manages infrastructure changes with a mandatory security audit.

## Pipeline

```
planner → infra-gcp → security → reviewer → qa → release-manager
```

## Intent

Infrastructure changes carry higher blast radius than application code. This pipeline:
1. Plans the change carefully (planner)
2. Implements it using GCP IaC best practices (infra-gcp)
3. Audits the change for security implications (security)
4. Reviews the IaC code for correctness and maintainability (reviewer)
5. Verifies the change in a test environment (qa)
6. Packages the change for controlled rollout (release-manager)

## Quality Requirements

The quality threshold is raised to **9/10** for infrastructure changes, reflecting the
higher risk of misconfiguration in production cloud environments.

## Hard Stops

The security agent MUST pass with no critical findings before the pipeline continues.
If the security agent sets `status: "stop"`, the pipeline halts unconditionally.

## Notes

- Always use a separate test/staging GCP project to verify changes
- Infrastructure changes must have a documented rollback procedure
- Any change to IAM roles or firewall rules requires explicit approval in the task
