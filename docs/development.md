# Development Guide

## Setup

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and set up
git clone <repo-url> vguild
cd vguild
uv sync --dev
```

## Running Commands

```bash
# Show help
uv run vguild --help

# List agents
uv run vguild agents list

# Validate catalog
uv run vguild agents validate

# Run a dry-run orchestrator (no API calls)
uv run vguild orchestrators run hotfix \
  --task "Fix the login bug" \
  --dry-run

# Run with the real API
export ANTHROPIC_API_KEY=sk-ant-...
uv run vguild orchestrators run hotfix \
  --task-file examples/tasks/hotfix.md
```

## Testing

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_gating.py -v

# Run with coverage
uv run pytest --cov=vguild --cov-report=term-missing
```

## Linting

```bash
# Check
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check . --fix

# Format
uv run ruff format .
```

## Adding an Agent

1. Create `catalog/agents/<name>.md` with YAML frontmatter
2. Write the system prompt in the Markdown body
3. Validate: `uv run vguild agents validate`
4. Preview: `uv run vguild agents show <name>`
5. Test with dry-run: `uv run vguild agents run <name> --task "..." --dry-run`

## Adding an Orchestrator

1. Create `catalog/orchestrators/<name>.md`
2. Ensure all referenced agents exist
3. Validate: `uv run vguild agents validate`
4. Preview: `uv run vguild orchestrators show <name>`
5. Test: `uv run vguild orchestrators run <name> --task "..." --dry-run`

## Project Layout

```
src/vguild/
  __init__.py          Package version
  cli.py               Typer CLI
  config.py            GatingConfig, VGuildConfig
  models.py            AgentOutcome, GateDecision, RunSummary, ...
  prompt_loader.py     YAML frontmatter parsing
  registry.py          Catalog discovery
  sdk_adapter.py       Anthropic API adapter
  gating.py            Quality gate logic
  run_store.py         Run artifact persistence
  logging_utils.py     Rich logging setup
  deploy.py            Workspace deployment
  orchestrators/
    __init__.py
    base.py            OrchestratorRunner (pipeline loop)
    hotfix.py          Hotfix factory
    new_feature.py     New-feature factory
    infra_change.py    Infra-change factory
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Required for real API calls |

## Architecture Decision Records

### Why tool_choice for structured output?

Anthropic's `tool_choice={"type": "tool", "name": "submit_outcome"}` forces the model to
call a specific tool, which guarantees the response is structured JSON matching the schema.
This is more reliable than asking the model to output JSON in text form.

### Why separate `config.min_quality` from `orchestrator.quality_threshold`?

`quality_threshold` is the orchestrator's design intent (e.g. infra-change needs 9/10).
`min_quality` is a runtime override via CLI (e.g. `--min-quality 10` for extra-careful run).
The gate uses `max(orchestrator.quality_threshold, config.min_quality)`.

### Why Markdown for prompt files?

- Human-readable and version-controllable
- Compatible with Claude Code's native `.claude/agents/` format
- YAML frontmatter is a well-understood convention
- Easy to preview in any Markdown editor
