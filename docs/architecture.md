# Architecture

## Overview

`vguild` implements an **agent guild** — a collection of specialized AI agents that collaborate
to solve software engineering tasks. Agents are coordinated by **orchestrators** which manage
pipeline flow, quality enforcement, and stopping conditions.

```
Task Input
    │
    ▼
Orchestrator (Python loop)
    │
    ├── Run Agent (via SDKAdapter → Anthropic API)
    │       └── Structured Output (AgentOutcome JSON)
    │
    ├── Quality Gate (gating.py)
    │       ├── PASS → advance to next agent
    │       └── FAIL → retry / stop
    │
    ├── Stopping Criteria Check
    │       ├── terminal_agent_passed → success
    │       ├── max_rounds_reached → stop
    │       ├── no_progress → stop
    │       ├── repeated_block → stop
    │       ├── needs_human → escalate
    │       └── validation_failure → stop
    │
    └── Run Storage (runs/<id>/)
            ├── steps/NNN_agent.json
            ├── summary.json
            └── report.md
```

## Component Map

| Component | File | Responsibility |
|-----------|------|---------------|
| Models | `models.py` | All Pydantic data structures |
| Prompt Loader | `prompt_loader.py` | Parse YAML frontmatter + body |
| Registry | `registry.py` | Discover catalog entries |
| SDK Adapter | `sdk_adapter.py` | Call Anthropic API, parse outcomes |
| Gating | `gating.py` | Quality gate evaluation |
| Orchestrators | `orchestrators/` | Pipeline loop implementations |
| Run Store | `run_store.py` | Persist run artifacts |
| Deploy | `deploy.py` | Copy prompts to workspaces |
| CLI | `cli.py` | Typer command interface |

## Data Flow

### Agent Execution

1. `OrchestratorRunner.run()` calls `SDKAdapter.run_agent()`
2. `SDKAdapter` builds a system prompt = agent body + output instructions
3. Anthropic API is called with `tool_choice=submit_outcome` to force structured output
4. Response `tool_use` block is validated as `AgentOutcome`
5. `evaluate_gate()` decides pass/fail and next agent
6. Step is recorded via `RunStore.save_step()`

### Structured Output

Agents are forced to call the `submit_outcome` tool, whose schema is the full
`AgentOutcome` JSON Schema. This guarantees Pydantic-valid structured data without
regex parsing.

### Quality Gate Logic

```python
effective_threshold = max(orchestrator.quality_threshold, config.min_quality)

if outcome.needs_human         → fail (needs_human)
if outcome.status == "stop"    → fail (stop_signal)
if blocked and fail_on_blocked → fail (blocked)
if quality < threshold         → fail (quality)
if no next agent defined       → fail (no_handoff)
else                           → pass → next_agent
```

## Directory Layout

```
vguild/
  catalog/           Agent and orchestrator Markdown prompt files
  src/vguild/        Python source package
    orchestrators/   Pipeline implementations
  tests/             pytest test suite
  examples/          Example task files
  runs/              Generated run artifacts (gitignored)
  docs/              This documentation
```
