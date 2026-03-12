"""Shared fixtures for vguild tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from vguild.models import AgentDefinition, AgentOutcome, OrchestratorDefinition
from vguild.registry import Registry

# ---------------------------------------------------------------------------
# Catalog fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_catalog(tmp_path: Path) -> Path:
    """Create a minimal catalog directory tree for tests."""
    agents_dir = tmp_path / "agents"
    orchs_dir = tmp_path / "orchestrators"
    agents_dir.mkdir()
    orchs_dir.mkdir()

    (agents_dir / "planner.md").write_text(
        "---\n"
        "name: planner\n"
        "description: Planning agent\n"
        "model: sonnet\n"
        "tools:\n"
        "  - Read\n"
        "max_turns: 3\n"
        "tags:\n"
        "  - planning\n"
        "---\n"
        "You are the planner. Analyse and plan.\n"
    )
    (agents_dir / "implementer.md").write_text(
        "---\n"
        "name: implementer\n"
        "description: Implementation agent\n"
        "model: sonnet\n"
        "tools:\n"
        "  - Write\n"
        "max_turns: 10\n"
        "tags:\n"
        "  - coding\n"
        "---\n"
        "You are the implementer. Write code.\n"
    )
    (agents_dir / "reviewer.md").write_text(
        "---\n"
        "name: reviewer\n"
        "description: Review agent\n"
        "model: sonnet\n"
        "tools: []\n"
        "max_turns: 5\n"
        "tags: []\n"
        "---\n"
        "You are the reviewer.\n"
    )
    (agents_dir / "release-manager.md").write_text(
        "---\n"
        "name: release-manager\n"
        "description: Release manager agent\n"
        "model: sonnet\n"
        "tools: []\n"
        "max_turns: 5\n"
        "tags: []\n"
        "---\n"
        "You are the release manager.\n"
    )

    (orchs_dir / "hotfix.md").write_text(
        "---\n"
        "name: hotfix\n"
        "description: Hotfix pipeline\n"
        "entry_agent: planner\n"
        "terminal_agents:\n"
        "  - release-manager\n"
        "quality_threshold: 8\n"
        "max_rounds: 6\n"
        "max_no_progress: 2\n"
        "allowed_handoffs:\n"
        "  planner:\n"
        "    - implementer\n"
        "  implementer:\n"
        "    - reviewer\n"
        "  reviewer:\n"
        "    - release-manager\n"
        "---\n"
        "Hotfix orchestrator.\n"
    )

    return tmp_path


@pytest.fixture()
def registry(tmp_catalog: Path) -> Registry:
    return Registry(catalog_dir=tmp_catalog)


# ---------------------------------------------------------------------------
# Model fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def pass_outcome() -> AgentOutcome:
    return AgentOutcome(
        agent_name="planner",
        status="pass",
        quality_score=9,
        confidence_score=8,
        summary="Completed planning successfully.",
        findings=["Issue is in src/auth.py line 42"],
        artifacts_changed=["src/auth.py"],
        tests_run=["tests/test_auth.py"],
        recommended_next_agent="implementer",
        needs_human=False,
        stop_reason=None,
        notes_for_next_agent=["Fix null check on line 42"],
    )


@pytest.fixture()
def low_quality_outcome() -> AgentOutcome:
    return AgentOutcome(
        agent_name="planner",
        status="revise",
        quality_score=5,
        confidence_score=4,
        summary="Partial analysis only.",
        findings=[],
        artifacts_changed=[],
        tests_run=[],
        recommended_next_agent=None,
        needs_human=False,
        stop_reason=None,
        notes_for_next_agent=[],
    )


@pytest.fixture()
def blocked_outcome() -> AgentOutcome:
    return AgentOutcome(
        agent_name="planner",
        status="blocked",
        quality_score=3,
        confidence_score=2,
        summary="Cannot proceed — missing codebase access.",
        findings=["Repository not cloned"],
        artifacts_changed=[],
        tests_run=[],
        recommended_next_agent=None,
        needs_human=False,
        stop_reason=None,
        notes_for_next_agent=[],
    )


@pytest.fixture()
def human_escalation_outcome() -> AgentOutcome:
    return AgentOutcome(
        agent_name="security",
        status="stop",
        quality_score=10,
        confidence_score=10,
        summary="Critical security vulnerability found.",
        findings=["SQL injection in user input handler"],
        artifacts_changed=[],
        tests_run=[],
        recommended_next_agent=None,
        needs_human=True,
        stop_reason="Critical security issue requires human review",
        notes_for_next_agent=[],
    )


@pytest.fixture()
def hotfix_orchestrator(registry: Registry) -> OrchestratorDefinition:
    return registry.get_orchestrator("hotfix")


@pytest.fixture()
def planner_agent(registry: Registry) -> AgentDefinition:
    return registry.get_agent("planner")
