"""Tests for Registry — catalog discovery and cross-reference validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from vguild.registry import Registry


class TestRegistry:
    def test_loads_agents(self, registry: Registry) -> None:
        agents = registry.load_agents()
        assert "planner" in agents
        assert "implementer" in agents

    def test_loads_orchestrators(self, registry: Registry) -> None:
        orchs = registry.load_orchestrators()
        assert "hotfix" in orchs

    def test_get_agent_found(self, registry: Registry) -> None:
        agent = registry.get_agent("planner")
        assert agent.name == "planner"

    def test_get_agent_missing_raises(self, registry: Registry) -> None:
        with pytest.raises(KeyError, match="planner999"):
            registry.get_agent("planner999")

    def test_get_orchestrator_found(self, registry: Registry) -> None:
        orch = registry.get_orchestrator("hotfix")
        assert orch.name == "hotfix"
        assert orch.entry_agent == "planner"

    def test_get_orchestrator_missing_raises(self, registry: Registry) -> None:
        with pytest.raises(KeyError, match="no-such"):
            registry.get_orchestrator("no-such")

    def test_caching(self, registry: Registry) -> None:
        a1 = registry.load_agents()
        a2 = registry.load_agents()
        assert a1 is a2  # same dict object

    def test_reload_reloads(self, registry: Registry) -> None:
        a1 = registry.load_agents()
        a2 = registry.load_agents(reload=True)
        assert a1 is not a2  # fresh load

    def test_validate_all_clean_catalog(self, registry: Registry) -> None:
        errors = registry.validate_all()
        assert errors == []

    def test_validate_all_missing_agent_reference(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / "agents"
        orchs_dir = tmp_path / "orchestrators"
        agents_dir.mkdir()
        orchs_dir.mkdir()

        (agents_dir / "planner.md").write_text(
            "---\nname: planner\ndescription: x\n---\nbody\n"
        )
        # Orchestrator references 'missing-agent' which doesn't exist
        (orchs_dir / "test.md").write_text(
            "---\n"
            "name: test\n"
            "description: test orch\n"
            "entry_agent: planner\n"
            "terminal_agents:\n"
            "  - missing-agent\n"
            "quality_threshold: 8\n"
            "allowed_handoffs: {}\n"
            "---\nbody\n"
        )
        reg = Registry(catalog_dir=tmp_path)
        errors = reg.validate_all()
        assert any("missing-agent" in e for e in errors)

    def test_empty_catalog_returns_empty(self, tmp_path: Path) -> None:
        (tmp_path / "agents").mkdir()
        (tmp_path / "orchestrators").mkdir()
        reg = Registry(catalog_dir=tmp_path)
        assert reg.load_agents() == {}
        assert reg.load_orchestrators() == {}

    def test_nonexistent_catalog_dir(self, tmp_path: Path) -> None:
        reg = Registry(catalog_dir=tmp_path / "no-such-dir")
        assert reg.load_agents() == {}
        assert reg.load_orchestrators() == {}
