# vguild — CLAUDE.md

This file provides context for AI assistants working in this repository.

## What This Is

`vguild` is a Python package implementing an **agent guild system**. It coordinates
specialized AI agents to solve software engineering tasks (bugs, features, infra changes).

## Key Commands

```bash
uv sync --dev            # Install all dependencies
uv run vguild --help     # Show CLI
uv run pytest            # Run tests
uv run ruff check .      # Lint
uv run ruff format .     # Format
uv run vguild doctor     # Health check
```

## Architecture

- **`catalog/`** — Agent and orchestrator definitions (Markdown + YAML frontmatter)
- **`src/vguild/`** — Python source code
  - `models.py` — All Pydantic models (`AgentOutcome`, `GateDecision`, `RunSummary`, …)
  - `registry.py` — Discovers agents/orchestrators from `catalog/`
  - `sdk_adapter.py` — Calls Anthropic API, forces structured output via tool_use
  - `gating.py` — Quality gate logic (pure Python)
  - `orchestrators/base.py` — Pipeline loop (`OrchestratorRunner`)
  - `cli.py` — Typer CLI
  - `run_store.py` — Persists run artifacts to `runs/`
  - `deploy.py` — Copies prompts into workspace `.claude/agents/`

## Coding Conventions

- Python 3.11+ with full type hints
- Pydantic v2 for all data models
- `from __future__ import annotations` at top of every module
- `uv` for dependency management (no pip)
- `ruff` for linting and formatting (line length 100)
- `pytest` for tests — no `unittest`
- No magic: explicit Python orchestration, no auto-delegation

## Structured Output Pattern

Agents are forced to call `submit_outcome` tool (schema = `AgentOutcome.model_json_schema()`).
This is more reliable than asking for inline JSON. See `sdk_adapter.py`.

## Quality Gate Rules (summary)

```
needs_human → fail immediately
stop status → fail immediately
blocked + fail_on_blocked → fail
quality_score < threshold → fail
no next agent (non-terminal) → fail
otherwise → pass, next_agent = resolved handoff
```

Threshold = `max(orchestrator.quality_threshold, config.min_quality)`, default 8.

## Stopping Criteria

| Condition | Stop Reason |
|-----------|------------|
| Terminal agent passes | `terminal_agent_passed` → success |
| Round limit | `max_rounds_reached` → failed |
| Quality plateau | `no_progress` → failed |
| Repeated block | `repeated_block` → blocked |
| Human needed | `needs_human` → blocked |
| Stop signal | `stop_signal` → failed |
| JSON validation ×2 | `validation_failure` → failed |

## File Conventions

Agent files: `catalog/agents/<name>.md`
Orchestrator files: `catalog/orchestrators/<name>.md`
Run artifacts: `runs/<timestamp>_<name>/`

## Tests

Tests are in `tests/`. Key test files:
- `test_gating.py` — gate logic (no mocking)
- `test_orchestrator.py` — full pipeline with `MockAdapter`
- `test_cli.py` — CLI via `typer.testing.CliRunner`
- `test_prompt_loader.py` — frontmatter parsing
- `test_registry.py` — catalog discovery

## Environment

- `ANTHROPIC_API_KEY` — required for real API runs
- `--dry-run` flag bypasses API calls (returns mock outcomes)
