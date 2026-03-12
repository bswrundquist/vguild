---
name: new-feature
description: Full development pipeline for new features including maintainability review
entry_agent: planner
terminal_agents:
  - release-manager
quality_threshold: 8
max_rounds: 16
max_no_progress: 2

allowed_handoffs:
  planner:
    - implementer
  implementer:
    - maintainer
  maintainer:
    - reviewer
  reviewer:
    - qa
  qa:
    - release-manager
---

# New Feature Orchestrator

This orchestrator runs the full development pipeline for new features.

## Pipeline

```
planner → implementer → maintainer → reviewer → qa → release-manager
```

## Intent

New features require more rigorous treatment than hotfixes. The maintainer step ensures
that the implementation is sustainable — well-documented, properly structured, and free
of unnecessary tech debt — before it reaches review.

## Quality Requirements

Each agent must score ≥ 8/10 to advance. The pipeline allows up to 16 rounds total
to accommodate the extra maintainer step and potential revision cycles.

## Guidance for Each Agent

- **Planner**: Produce a thorough plan with acceptance criteria and architectural notes
- **Implementer**: Write complete, tested code following project conventions
- **Maintainer**: Add documentation, improve naming, clean up duplication
- **Reviewer**: Enforce code quality, security, and correctness standards
- **QA**: Verify all acceptance criteria and run the full test suite
- **Release Manager**: Bump version, write changelog, prepare for deployment
