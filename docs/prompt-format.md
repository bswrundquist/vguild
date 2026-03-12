# Prompt File Format

Agent and orchestrator definitions are plain Markdown files with YAML frontmatter.
This format is fully compatible with Claude Code's `.claude/agents/` deployment.

## Agent File (`catalog/agents/<name>.md`)

```markdown
---
name: planner
description: Breaks issues into clear implementation steps
model: sonnet
tools:
  - Read
  - Grep
  - Glob
max_turns: 5
tags:
  - planning
  - architecture
---

# Agent System Prompt

Full Markdown body is used as the agent's system prompt.
```

### Frontmatter Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | No | file stem | Agent identifier |
| `description` | string | No | `""` | Short description |
| `model` | string | No | `sonnet` | `sonnet`, `opus`, `haiku`, or full model ID |
| `tools` | list[string] | No | `[]` | Claude Code tools to enable |
| `max_turns` | int | No | `5` | Maximum conversation turns |
| `tags` | list[string] | No | `[]` | Metadata tags |

### Model Aliases

| Alias | Resolved Model |
|-------|---------------|
| `sonnet` | `claude-sonnet-4-6` |
| `opus` | `claude-opus-4-6` |
| `haiku` | `claude-haiku-4-5-20251001` |

## Orchestrator File (`catalog/orchestrators/<name>.md`)

```markdown
---
name: hotfix
description: Fast-track production bug fix pipeline
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
    - release-manager
---

# Optional orchestrator-level context
```

### Frontmatter Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | No | file stem | Orchestrator identifier |
| `description` | string | No | `""` | Short description |
| `entry_agent` | string | **Yes** | — | First agent to run |
| `terminal_agents` | list[string] | No | `[]` | Agents that end the pipeline when they pass |
| `quality_threshold` | int | No | `8` | Minimum quality score to advance (0–10) |
| `max_rounds` | int | No | `10` | Maximum total rounds before stopping |
| `max_no_progress` | int | No | `2` | Max rounds without quality improvement |
| `allowed_handoffs` | dict | No | `{}` | Maps agent → list of valid next agents |

## AgentOutcome JSON Schema

Every agent **must** return a JSON object matching this shape:

```json
{
  "agent_name": "planner",
  "status": "pass",
  "quality_score": 9,
  "confidence_score": 8,
  "summary": "Completed analysis...",
  "findings": ["Issue found in src/auth.py"],
  "artifacts_changed": ["src/auth.py"],
  "tests_run": ["tests/test_auth.py"],
  "recommended_next_agent": "implementer",
  "needs_human": false,
  "stop_reason": null,
  "notes_for_next_agent": ["Fix null check on line 42"]
}
```

### Status Values

| Status | Meaning |
|--------|---------|
| `pass` | Work is complete and quality is sufficient |
| `revise` | Work needs improvement — will be retried |
| `blocked` | Cannot proceed (missing info, broken env) |
| `stop` | Halt the pipeline immediately (set `stop_reason`) |

## Claude Code Compatibility

Agent files in `catalog/agents/` can be deployed directly to `.claude/agents/` using:

```bash
vguild deploy agent planner --workspace /path/to/project
```

This makes the agent available as a subagent in Claude Code's native orchestration.
