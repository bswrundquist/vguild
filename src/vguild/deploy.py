"""Deploy agent and orchestrator prompts to target workspaces."""

from __future__ import annotations

import contextlib
import shutil
from pathlib import Path

from vguild.registry import Registry


def deploy_agent(
    agent_name: str,
    workspace: Path,
    registry: Registry,
    *,
    symlink: bool = False,
) -> Path:
    """Copy (or symlink) an agent prompt into <workspace>/.claude/agents/.

    Returns the deployed file path.
    """
    registry.get_agent(agent_name)  # validate exists
    source = registry.agents_dir / f"{agent_name}.md"

    dest_dir = workspace / ".claude" / "agents"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{agent_name}.md"

    _write(source, dest, symlink=symlink)
    return dest


def deploy_orchestrator(
    orchestrator_name: str,
    workspace: Path,
    registry: Registry,
    *,
    symlink: bool = False,
) -> Path:
    """Copy (or symlink) an orchestrator prompt into <workspace>/.agent-orchestrators/.

    Returns the deployed file path.
    """
    registry.get_orchestrator(orchestrator_name)  # validate exists
    source = registry.orchestrators_dir / f"{orchestrator_name}.md"

    dest_dir = workspace / ".agent-orchestrators"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{orchestrator_name}.md"

    _write(source, dest, symlink=symlink)
    return dest


def deploy_orchestrator_with_agents(
    orchestrator_name: str,
    workspace: Path,
    registry: Registry,
    *,
    symlink: bool = False,
) -> dict[str, Path]:
    """Deploy an orchestrator and every agent it references.

    Returns a mapping of resource name → deployed path.
    """
    orch = registry.get_orchestrator(orchestrator_name)
    deployed: dict[str, Path] = {}

    # Orchestrator itself
    deployed[orchestrator_name] = deploy_orchestrator(
        orchestrator_name, workspace, registry, symlink=symlink
    )

    # Collect every agent mentioned in the orchestrator config
    agent_names: set[str] = {orch.entry_agent}
    agent_names.update(orch.terminal_agents)
    for from_agent, targets in orch.allowed_handoffs.items():
        agent_names.add(from_agent)
        agent_names.update(targets)

    for name in sorted(agent_names):
        with contextlib.suppress(KeyError):
            deployed[name] = deploy_agent(name, workspace, registry, symlink=symlink)

    return deployed


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _write(source: Path, dest: Path, *, symlink: bool) -> None:
    if symlink:
        if dest.exists() or dest.is_symlink():
            dest.unlink()
        dest.symlink_to(source.resolve())
    else:
        shutil.copy2(source, dest)
