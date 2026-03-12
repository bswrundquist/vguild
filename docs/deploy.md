# Deployment

`vguild` agents and orchestrators are portable Markdown files that can be deployed
into any project workspace for use with Claude Code's native subagent system.

## Deploy an Agent

```bash
vguild deploy agent planner --workspace /path/to/my-project
```

Copies `catalog/agents/planner.md` to:
```
/path/to/my-project/.claude/agents/planner.md
```

This makes `planner` available as a subagent in Claude Code.

## Deploy an Orchestrator (with all agents)

```bash
vguild deploy orchestrator hotfix --workspace /path/to/my-project --with-agents
```

Deploys:
- `catalog/orchestrators/hotfix.md` → `.agent-orchestrators/hotfix.md`
- All agents referenced by the hotfix orchestrator → `.claude/agents/`

## Deploy Only the Orchestrator File

```bash
vguild deploy orchestrator hotfix --workspace . --orchestrator-only
```

## Symlink Instead of Copy

Use `--symlink` to create symlinks instead of copies. Changes to the catalog will
be reflected immediately in the workspace.

```bash
vguild deploy agent planner --workspace . --symlink
```

## Workspace Layout After Deployment

```
my-project/
  .claude/
    agents/
      planner.md          ← deployed agent
      implementer.md      ← deployed agent
      reviewer.md         ← deployed agent
      ...
  .agent-orchestrators/
    hotfix.md             ← deployed orchestrator
```

## Deploying to Multiple Projects

```bash
for project in ../project-a ../project-b ../project-c; do
  vguild deploy orchestrator new-feature --workspace "$project" --with-agents
done
```

## CI/CD Integration

In your CI pipeline:

```yaml
- name: Deploy vguild agents
  run: |
    pip install vguild
    vguild deploy orchestrator new-feature --workspace . --with-agents
```
