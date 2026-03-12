# Orchestrators

An orchestrator defines a multi-agent pipeline: which agents run, in what order, and under
what conditions the pipeline advances, retries, or stops.

## Built-in Orchestrators

### `hotfix`

Fast-track pipeline for production bug fixes.

```
planner → implementer → reviewer → qa → release-manager
```

- Quality threshold: **8/10**
- Max rounds: 12
- Use when: urgent production incident

### `new-feature`

Full development pipeline including a maintainability review step.

```
planner → implementer → maintainer → reviewer → qa → release-manager
```

- Quality threshold: **8/10**
- Max rounds: 16
- Use when: adding new functionality

### `infra-change`

Infrastructure change pipeline with mandatory security audit.

```
planner → infra-gcp → security → reviewer → qa → release-manager
```

- Quality threshold: **9/10** (higher bar for infra)
- Max rounds: 14
- Use when: modifying GCP infrastructure

## Pipeline Loop

```python
while True:
    # 1. Run current agent
    outcome = adapter.run_agent(agent, task, context)

    # 2. Evaluate gate
    gate = evaluate_gate(outcome, orchestrator, config, current_agent)

    # 3. Check stopping criteria
    if terminal_agent_passed:  break → success
    if max_rounds_exceeded:    break → failed
    if no_progress:            break → failed
    if needs_human:            break → blocked
    if stop_signal:            break → failed

    # 4. Advance or retry
    if gate.passed:   current_agent = gate.next_agent
    else:             retry current_agent with revision context
```

## Adding an Orchestrator

1. Create `catalog/orchestrators/<name>.md` with YAML frontmatter
2. Reference agents that already exist in `catalog/agents/`
3. Run `vguild agents validate` to check cross-references
4. Run `vguild orchestrators show <name>` to verify

## Handoff Context

When an agent passes the gate, its output is passed as context to the next agent:

```python
context = {
    "previous_agent": outcome.agent_name,
    "notes_for_next_agent": outcome.notes_for_next_agent,
    "findings": outcome.findings,
    "artifacts_changed": outcome.artifacts_changed,
    "summary": outcome.summary,
}
```

The receiving agent sees this context prepended to their task prompt.

## Retry Context

When an agent fails the gate, it is retried with additional context:

```python
context["needs_revision"] = True
context["gate_reason"] = gate.reason  # e.g. "Quality score 6/10 below threshold 8"
```
