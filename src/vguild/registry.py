"""Registry for discovering agents and orchestrators from the catalog directory."""

from __future__ import annotations

from pathlib import Path

from vguild.models import AgentDefinition, OrchestratorDefinition
from vguild.prompt_loader import load_agent, load_orchestrator

# Default catalog relative to the project root (two levels above this file)
_DEFAULT_CATALOG = Path(__file__).parent.parent.parent / "catalog"


class Registry:
    """Discovers and caches agent and orchestrator definitions from a catalog directory."""

    def __init__(self, catalog_dir: Path | str | None = None) -> None:
        self.catalog_dir = Path(catalog_dir) if catalog_dir else _DEFAULT_CATALOG
        self._agents: dict[str, AgentDefinition] | None = None
        self._orchestrators: dict[str, OrchestratorDefinition] | None = None

    @property
    def agents_dir(self) -> Path:
        return self.catalog_dir / "agents"

    @property
    def orchestrators_dir(self) -> Path:
        return self.catalog_dir / "orchestrators"

    def load_agents(self, *, reload: bool = False) -> dict[str, AgentDefinition]:
        """Return all agents, loading from disk if needed."""
        if self._agents is None or reload:
            self._agents = {}
            if self.agents_dir.exists():
                for path in sorted(self.agents_dir.glob("*.md")):
                    agent = load_agent(path)
                    self._agents[agent.name] = agent
        return self._agents

    def load_orchestrators(
        self, *, reload: bool = False
    ) -> dict[str, OrchestratorDefinition]:
        """Return all orchestrators, loading from disk if needed."""
        if self._orchestrators is None or reload:
            self._orchestrators = {}
            if self.orchestrators_dir.exists():
                for path in sorted(self.orchestrators_dir.glob("*.md")):
                    orch = load_orchestrator(path)
                    self._orchestrators[orch.name] = orch
        return self._orchestrators

    def get_agent(self, name: str) -> AgentDefinition:
        agents = self.load_agents()
        if name not in agents:
            available = sorted(agents)
            raise KeyError(f"Agent {name!r} not found. Available: {available}")
        return agents[name]

    def get_orchestrator(self, name: str) -> OrchestratorDefinition:
        orchestrators = self.load_orchestrators()
        if name not in orchestrators:
            available = sorted(orchestrators)
            raise KeyError(f"Orchestrator {name!r} not found. Available: {available}")
        return orchestrators[name]

    def validate_all(self) -> list[str]:
        """Validate all catalog entries cross-referenced. Returns a list of errors."""
        errors: list[str] = []

        # Validate agents individually
        for path in sorted(self.agents_dir.glob("*.md")):
            try:
                load_agent(path)
            except Exception as exc:
                errors.append(f"Agent {path.name}: {exc}")

        # Validate orchestrators and cross-check agent references
        for path in sorted(self.orchestrators_dir.glob("*.md")):
            try:
                orch = load_orchestrator(path)
            except Exception as exc:
                errors.append(f"Orchestrator {path.name}: {exc}")
                continue

            try:
                agents = self.load_agents()
            except Exception:
                agents = {}

            if orch.entry_agent not in agents:
                errors.append(
                    f"Orchestrator {orch.name!r}: entry_agent {orch.entry_agent!r} not in catalog"
                )
            for terminal in orch.terminal_agents:
                if terminal not in agents:
                    errors.append(
                        f"Orchestrator {orch.name!r}: terminal_agent {terminal!r} not in catalog"
                    )
            for from_agent, targets in orch.allowed_handoffs.items():
                if from_agent not in agents:
                    errors.append(
                        f"Orchestrator {orch.name!r}: handoff source {from_agent!r} not in catalog"
                    )
                for target in targets:
                    if target not in agents:
                        errors.append(
                            f"Orchestrator {orch.name!r}: handoff target {target!r} not in catalog"
                        )

        return errors
