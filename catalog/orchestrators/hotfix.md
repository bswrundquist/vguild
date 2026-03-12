---
name: hotfix
description: Fast-track pipeline for resolving production bugs
entry_agent: planner
terminal_agents:
  - release-manager
quality_threshold: 8
max_rounds: 12
max_no_progress: 2

allowed_handoffs:
  planner:
    - implementer
  implementer:
    - reviewer
  reviewer:
    - qa
  qa:
    - release-manager
---

# Hotfix Orchestrator

This orchestrator runs a fast-track pipeline for fixing production bugs.

## Pipeline

```
planner → implementer → reviewer → qa → release-manager
```

## Intent

A hotfix represents an urgent, targeted fix to a production issue. The pipeline is intentionally
lean — no maintainer step — to minimise time to resolution. Quality standards are maintained via
the reviewer and QA gates.

## Quality Requirements

Each agent must score ≥ 8/10 to advance. The gate will retry the same agent (up to
`max_no_progress` times) if quality is insufficient before stopping.

## Escalation

If any agent sets `needs_human: true`, the pipeline halts and a human must intervene before
re-running. This is appropriate for security incidents, data loss risks, or ambiguous requirements
that cannot be resolved automatically.
