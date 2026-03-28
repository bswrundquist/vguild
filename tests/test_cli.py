"""Tests for CLI commands using Typer's test runner."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from vguild.cli import app

runner = CliRunner()


class TestAgentsList:
    def test_agents_list(self, tmp_catalog: Path) -> None:
        result = runner.invoke(app, ["agents", "list", "--catalog", str(tmp_catalog)])
        assert result.exit_code == 0
        assert "planner" in result.output

    def test_agents_list_json(self, tmp_catalog: Path) -> None:
        result = runner.invoke(app, ["agents", "list", "--json", "--catalog", str(tmp_catalog)])
        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert isinstance(data, list)
        names = [d["name"] for d in data]
        assert "planner" in names


class TestAgentsShow:
    def test_show_existing_agent(self, tmp_catalog: Path) -> None:
        result = runner.invoke(app, ["agents", "show", "planner", "--catalog", str(tmp_catalog)])
        assert result.exit_code == 0
        assert "planner" in result.output

    def test_show_missing_agent(self, tmp_catalog: Path) -> None:
        result = runner.invoke(
            app, ["agents", "show", "nonexistent", "--catalog", str(tmp_catalog)]
        )
        assert result.exit_code != 0


class TestAgentsValidate:
    def test_validate_clean_catalog(self, tmp_catalog: Path) -> None:
        result = runner.invoke(app, ["agents", "validate", "--catalog", str(tmp_catalog)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_validate_broken_catalog(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / "agents"
        orchs_dir = tmp_path / "orchestrators"
        agents_dir.mkdir()
        orchs_dir.mkdir()
        # Orchestrator references non-existent agent
        (orchs_dir / "bad.md").write_text(
            "---\nname: bad\ndescription: x\nentry_agent: ghost\nterminal_agents: []\n---\n"
        )
        result = runner.invoke(app, ["agents", "validate", "--catalog", str(tmp_path)])
        assert result.exit_code != 0


class TestOrchestratorsList:
    def test_orchestrators_list(self, tmp_catalog: Path) -> None:
        result = runner.invoke(app, ["orchestrators", "list", "--catalog", str(tmp_catalog)])
        assert result.exit_code == 0
        assert "hotfix" in result.output

    def test_orchestrators_list_json(self, tmp_catalog: Path) -> None:
        result = runner.invoke(
            app, ["orchestrators", "list", "--json", "--catalog", str(tmp_catalog)]
        )
        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert any(d["name"] == "hotfix" for d in data)


class TestOrchestratorsShow:
    def test_show_hotfix(self, tmp_catalog: Path) -> None:
        result = runner.invoke(
            app, ["orchestrators", "show", "hotfix", "--catalog", str(tmp_catalog)]
        )
        assert result.exit_code == 0
        assert "hotfix" in result.output
        assert "planner" in result.output


class TestDeployCommands:
    def test_deploy_agent(self, tmp_catalog: Path, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        result = runner.invoke(
            app,
            [
                "deploy",
                "agent",
                "planner",
                "--workspace",
                str(workspace),
                "--catalog",
                str(tmp_catalog),
            ],
        )
        assert result.exit_code == 0
        assert (workspace / ".claude" / "agents" / "planner.md").exists()

    def test_deploy_orchestrator_with_agents(self, tmp_catalog: Path, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        result = runner.invoke(
            app,
            [
                "deploy",
                "orchestrator",
                "hotfix",
                "--workspace",
                str(workspace),
                "--with-agents",
                "--catalog",
                str(tmp_catalog),
            ],
        )
        assert result.exit_code == 0
        assert (workspace / ".agent-orchestrators" / "hotfix.md").exists()


class TestVersion:
    def test_version(self) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "vguild" in result.output


class TestDoctor:
    def test_doctor_with_valid_catalog(self, tmp_catalog: Path, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        result = runner.invoke(app, ["doctor", "--catalog", str(tmp_catalog)])
        # May exit 0 or 1 depending on Python version, but should not crash
        assert result.exit_code in (0, 1)
        assert "catalog" in result.output.lower() or "valid" in result.output.lower()


class TestOrchestratorsRun:
    def test_run_dry_run(self, tmp_catalog: Path, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "orchestrators",
                "run",
                "hotfix",
                "--task",
                "Fix the bug",
                "--dry-run",
                "--catalog",
                str(tmp_catalog),
                "--runs-dir",
                str(tmp_path / "runs"),
            ],
        )
        # dry-run should succeed
        assert result.exit_code == 0

    def test_run_requires_task_or_task_file(self, tmp_catalog: Path, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "orchestrators",
                "run",
                "hotfix",
                "--catalog",
                str(tmp_catalog),
                "--runs-dir",
                str(tmp_path / "runs"),
            ],
        )
        assert result.exit_code != 0

    def test_run_with_doc(self, tmp_catalog: Path, tmp_path: Path) -> None:
        doc_file = tmp_path / "prd.md"
        doc_file.write_text("# PRD\n\nBuild feature X.")
        result = runner.invoke(
            app,
            [
                "orchestrators",
                "run",
                "hotfix",
                "--task",
                "Fix the bug",
                "--doc",
                str(doc_file),
                "--dry-run",
                "--catalog",
                str(tmp_catalog),
                "--runs-dir",
                str(tmp_path / "runs"),
            ],
        )
        assert result.exit_code == 0

    def test_run_with_multiple_docs(self, tmp_catalog: Path, tmp_path: Path) -> None:
        doc1 = tmp_path / "prd.md"
        doc2 = tmp_path / "jira.json"
        doc1.write_text("Requirements")
        doc2.write_text('{"issue": "BUG-123"}')
        result = runner.invoke(
            app,
            [
                "orchestrators",
                "run",
                "hotfix",
                "--task",
                "Fix bug",
                "--doc",
                str(doc1),
                "--doc",
                str(doc2),
                "--dry-run",
                "--catalog",
                str(tmp_catalog),
                "--runs-dir",
                str(tmp_path / "runs"),
            ],
        )
        assert result.exit_code == 0


class TestAgentsRunWithDoc:
    def test_run_with_doc(self, tmp_catalog: Path, tmp_path: Path) -> None:
        doc_file = tmp_path / "context.md"
        doc_file.write_text("Background context.")
        result = runner.invoke(
            app,
            [
                "agents",
                "run",
                "planner",
                "--task",
                "Analyze issue",
                "--doc",
                str(doc_file),
                "--dry-run",
                "--catalog",
                str(tmp_catalog),
            ],
        )
        assert result.exit_code == 0
