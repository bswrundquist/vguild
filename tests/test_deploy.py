"""Tests for deploy — copying agent/orchestrator prompts to workspaces."""

from __future__ import annotations

from pathlib import Path

import pytest

from vguild.deploy import deploy_agent, deploy_orchestrator, deploy_orchestrator_with_agents
from vguild.registry import Registry


class TestDeployAgent:
    def test_copy_agent_to_workspace(self, tmp_path: Path, registry: Registry) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        dest = deploy_agent("planner", workspace, registry)

        expected = workspace / ".claude" / "agents" / "planner.md"
        assert dest == expected
        assert dest.exists()
        assert "planner" in dest.read_text(encoding="utf-8").lower()

    def test_deploy_creates_directory(self, tmp_path: Path, registry: Registry) -> None:
        workspace = tmp_path / "workspace"
        # Don't mkdir — deploy should create it
        dest = deploy_agent("planner", workspace, registry)
        assert dest.exists()

    def test_deploy_missing_agent_raises(self, tmp_path: Path, registry: Registry) -> None:
        workspace = tmp_path / "workspace"
        with pytest.raises(KeyError, match="nonexistent"):
            deploy_agent("nonexistent", workspace, registry)

    def test_symlink_creates_symlink(self, tmp_path: Path, registry: Registry) -> None:
        workspace = tmp_path / "workspace"
        dest = deploy_agent("planner", workspace, registry, symlink=True)
        assert dest.is_symlink()

    def test_overwrite_existing(self, tmp_path: Path, registry: Registry) -> None:
        workspace = tmp_path / "workspace"
        deploy_agent("planner", workspace, registry)
        # Deploy again should not raise
        dest = deploy_agent("planner", workspace, registry)
        assert dest.exists()


class TestDeployOrchestrator:
    def test_copy_orchestrator_to_workspace(
        self, tmp_path: Path, registry: Registry
    ) -> None:
        workspace = tmp_path / "workspace"
        dest = deploy_orchestrator("hotfix", workspace, registry)

        expected = workspace / ".agent-orchestrators" / "hotfix.md"
        assert dest == expected
        assert dest.exists()

    def test_deploy_missing_orchestrator_raises(
        self, tmp_path: Path, registry: Registry
    ) -> None:
        workspace = tmp_path / "workspace"
        with pytest.raises(KeyError, match="no-such"):
            deploy_orchestrator("no-such", workspace, registry)


class TestDeployOrchestratorWithAgents:
    def test_deploys_all_referenced_agents(
        self, tmp_path: Path, registry: Registry
    ) -> None:
        workspace = tmp_path / "workspace"
        deployed = deploy_orchestrator_with_agents("hotfix", workspace, registry)

        # Orchestrator itself
        assert "hotfix" in deployed
        assert deployed["hotfix"].exists()

        # Agents referenced in the hotfix orchestrator
        assert "planner" in deployed
        assert "implementer" in deployed
        assert deployed["planner"].exists()
        assert deployed["implementer"].exists()

    def test_returns_mapping_of_paths(
        self, tmp_path: Path, registry: Registry
    ) -> None:
        workspace = tmp_path / "workspace"
        deployed = deploy_orchestrator_with_agents("hotfix", workspace, registry)
        for path in deployed.values():
            assert path.exists()
