"""Tests for prompt_loader — YAML frontmatter parsing and model construction."""

from __future__ import annotations

from pathlib import Path

import pytest

from vguild.prompt_loader import load_agent, load_orchestrator, parse_frontmatter


class TestParseFrontmatter:
    def test_basic_frontmatter(self) -> None:
        content = "---\nname: foo\n---\nBody text here."
        meta, body = parse_frontmatter(content)
        assert meta == {"name": "foo"}
        assert body == "Body text here."

    def test_no_frontmatter(self) -> None:
        content = "Just a plain body."
        meta, body = parse_frontmatter(content)
        assert meta == {}
        assert body == "Just a plain body."

    def test_complex_frontmatter(self) -> None:
        content = (
            "---\n"
            "name: planner\n"
            "tools:\n"
            "  - Read\n"
            "  - Grep\n"
            "max_turns: 5\n"
            "---\n"
            "System prompt goes here.\n"
        )
        meta, body = parse_frontmatter(content)
        assert meta["name"] == "planner"
        assert meta["tools"] == ["Read", "Grep"]
        assert meta["max_turns"] == 5
        assert "System prompt" in body

    def test_invalid_yaml_raises(self) -> None:
        content = "---\n: bad: yaml: [\n---\nBody."
        with pytest.raises(ValueError, match="Invalid YAML"):
            parse_frontmatter(content)

    def test_empty_frontmatter(self) -> None:
        content = "---\n---\nBody."
        meta, body = parse_frontmatter(content)
        assert meta == {}
        assert body == "Body."


class TestLoadAgent:
    def test_load_basic_agent(self, tmp_path: Path) -> None:
        (tmp_path / "planner.md").write_text(
            "---\nname: planner\ndescription: Plans things\nmodel: sonnet\n"
            "tools:\n  - Read\nmax_turns: 3\ntags:\n  - planning\n---\n"
            "You are the planner.\n"
        )
        agent = load_agent(tmp_path / "planner.md")
        assert agent.name == "planner"
        assert agent.description == "Plans things"
        assert agent.model == "sonnet"
        assert agent.tools == ["Read"]
        assert agent.max_turns == 3
        assert agent.tags == ["planning"]
        assert "planner" in agent.system_prompt

    def test_defaults_applied(self, tmp_path: Path) -> None:
        (tmp_path / "minimal.md").write_text(
            "---\nentry_agent: x\n---\nJust a body."
        )
        # load_agent uses stem if name missing
        (tmp_path / "minimal2.md").write_text("---\n---\nJust body.")
        agent = load_agent(tmp_path / "minimal2.md")
        assert agent.name == "minimal2"
        assert agent.model == "sonnet"
        assert agent.max_turns == 5
        assert agent.tools == []

    def test_system_prompt_preserved(self, tmp_path: Path) -> None:
        body = "## Multi\n\nLine **body** with [links](http://example.com)."
        (tmp_path / "agent.md").write_text(f"---\nname: agent\n---\n{body}")
        agent = load_agent(tmp_path / "agent.md")
        assert agent.system_prompt == body


class TestLoadOrchestrator:
    def test_load_basic_orchestrator(self, tmp_path: Path) -> None:
        (tmp_path / "hotfix.md").write_text(
            "---\n"
            "name: hotfix\n"
            "description: Fast fix pipeline\n"
            "entry_agent: planner\n"
            "terminal_agents:\n"
            "  - release-manager\n"
            "quality_threshold: 8\n"
            "max_rounds: 10\n"
            "max_no_progress: 2\n"
            "allowed_handoffs:\n"
            "  planner:\n"
            "    - implementer\n"
            "---\n"
            "Orchestrator body.\n"
        )
        orch = load_orchestrator(tmp_path / "hotfix.md")
        assert orch.name == "hotfix"
        assert orch.entry_agent == "planner"
        assert orch.terminal_agents == ["release-manager"]
        assert orch.quality_threshold == 8
        assert orch.allowed_handoffs == {"planner": ["implementer"]}

    def test_missing_entry_agent_raises(self, tmp_path: Path) -> None:
        (tmp_path / "bad.md").write_text("---\nname: bad\n---\nNo entry agent.")
        with pytest.raises(ValueError, match="entry_agent"):
            load_orchestrator(tmp_path / "bad.md")

    def test_defaults_applied(self, tmp_path: Path) -> None:
        (tmp_path / "orch.md").write_text(
            "---\nentry_agent: planner\nterminal_agents: []\n---\nBody."
        )
        orch = load_orchestrator(tmp_path / "orch.md")
        assert orch.quality_threshold == 8
        assert orch.max_rounds == 10
        assert orch.max_no_progress == 2
        assert orch.allowed_handoffs == {}
