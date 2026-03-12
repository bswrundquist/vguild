# vguild

**Agent guild system for collaborative software task solving.**

`vguild` models an engineering organization as a team of specialized AI agents.
Each agent is a specialist (planner, implementer, reviewer, etc.) that handles one
concern. Orchestrators coordinate them through quality-gated pipelines to resolve
issues, build features, and ship infrastructure changes.

---

## How It Works

### Agents

Each agent is defined as a Markdown file with YAML frontmatter:

```markdown
---
name: planner
description: Breaks tasks into implementation steps
model: sonnet
tools: [Read, Grep, Glob]
max_turns: 5
tags: [planning]
---

You are the Planner. Analyse the task and produce a step-by-step plan...
```

Agents return structured JSON (`AgentOutcome`) with quality scores, findings,
and notes for the next agent.

### Orchestrators

An orchestrator wires agents into a pipeline with explicit handoff rules:

```markdown
---
name: hotfix
entry_agent: planner
terminal_agents: [release-manager]
quality_threshold: 8
allowed_handoffs:
  planner: [implementer]
  implementer: [reviewer]
  reviewer: [qa]
  qa: [release-manager]
---
```

### Quality Gates

Every agent handoff is controlled by a quality gate. Agents must score **≥ 8/10**
to advance (configurable per orchestrator and via CLI). If quality is insufficient
the same agent is retried with revision context.

### Stopping Criteria

Pipelines stop when:
- The terminal agent passes ✅
- Max rounds reached ⏱
- Quality stops improving 📉
- Agent is repeatedly blocked 🚫
- Human intervention required 🙋
- Validation fails twice ❌

All stop conditions are logged and persisted in the run summary.

---

## Quick Start

```bash
# Install
pip install uv
git clone <repo> vguild && cd vguild
uv sync

# Check system health
uv run vguild doctor

# List available agents and orchestrators
uv run vguild agents list
uv run vguild orchestrators list

# Dry-run a pipeline (no API calls)
uv run vguild orchestrators run hotfix \
  --task "Fix the NullPointerException in auth.login()" \
  --dry-run

# Real run (requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=sk-ant-...
uv run vguild orchestrators run hotfix \
  --task-file examples/tasks/hotfix.md
```

---

## CLI Reference

```
vguild agents list                    List all agents in the catalog
vguild agents show <name>             Show agent details and system prompt
vguild agents validate                Validate all catalog entries
vguild agents run <name> --task "..."  Run a single agent

vguild orchestrators list             List all orchestrators
vguild orchestrators show <name>      Show orchestrator pipeline
vguild orchestrators run <name> \
  --task "..." \
  --task-file path/to/task.md \
  --min-quality 9 \                   Override quality threshold
  --max-rounds 5 \                    Limit total rounds
  --max-no-progress 1 \               Fail faster on stall
  --fail-on-blocked \                 Treat blocked as hard failure
  --dry-run \                         No API calls
  --json                              JSON output

vguild deploy agent <name> \
  --workspace /path/to/project        Deploy to .claude/agents/
vguild deploy orchestrator <name> \
  --workspace /path/to/project \
  --with-agents                       Deploy orchestrator + all agents

vguild doctor                         Health check
vguild version                        Print version
```

---

## Built-in Agents

| Agent | Responsibility |
|-------|---------------|
| `planner` | Task analysis and implementation planning |
| `implementer` | Code changes and test writing |
| `maintainer` | Documentation, refactoring, tech debt |
| `reviewer` | Code review: correctness, security, performance |
| `qa` | Verification, test execution, acceptance criteria |
| `release-manager` | Versioning, changelog, deployment checks |
| `infra-gcp` | GCP Terraform infrastructure changes |
| `security` | Security audit against OWASP Top 10 and cloud best practices |

## Built-in Orchestrators

| Orchestrator | Pipeline | Use Case |
|-------------|----------|----------|
| `hotfix` | planner → implementer → reviewer → qa → release-manager | Production bug fix |
| `new-feature` | planner → implementer → maintainer → reviewer → qa → release-manager | New feature |
| `infra-change` | planner → infra-gcp → security → reviewer → qa → release-manager | GCP infra change |

---

## Adding Agents

1. Create `catalog/agents/<name>.md`
2. Add YAML frontmatter (name, description, model, tools, max_turns, tags)
3. Write the system prompt in the Markdown body
4. Run `vguild agents validate`

See [docs/prompt-format.md](docs/prompt-format.md) for full field reference.

## Adding Orchestrators

1. Create `catalog/orchestrators/<name>.md`
2. Define the pipeline in frontmatter (`entry_agent`, `terminal_agents`, `allowed_handoffs`)
3. Ensure all referenced agents exist in the catalog
4. Run `vguild agents validate`

See [docs/orchestrators.md](docs/orchestrators.md) for full pipeline reference.

---

## Run Artifacts

Each run stores artifacts in `runs/<timestamp>_<orchestrator>/`:

```
runs/20240115T143022_hotfix/
  steps/
    001_planner.json
    002_implementer.json
    003_reviewer.json
    004_qa.json
    005_release-manager.json
  summary.json      ← Complete RunSummary (Pydantic)
  report.md         ← Human-readable Markdown report
```

---

## Development

```bash
uv sync --dev
uv run pytest              # Run tests
uv run ruff check .        # Lint
uv run ruff format .       # Format
```

See [docs/development.md](docs/development.md) for full developer guide.

---

## Documentation

- [Architecture](docs/architecture.md) — system design and data flow
- [Prompt Format](docs/prompt-format.md) — agent/orchestrator file format
- [Orchestrators](docs/orchestrators.md) — pipeline logic and configuration
- [Quality Gates](docs/quality-gates.md) — gate rules and stopping criteria
- [Deploy](docs/deploy.md) — deploying to workspaces
- [Development](docs/development.md) — setup, testing, contributing
