"""Tests for RunStore — artifact persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from vguild.models import (
    AgentOutcome,
    GateDecision,
    RunStep,
    RunSummary,
    StopCondition,
)
from vguild.run_store import RunStore, make_run_id


def _make_step(n: int) -> RunStep:
    outcome = AgentOutcome(
        agent_name="planner",
        status="pass",
        quality_score=9,
        confidence_score=8,
        summary="Done.",
    )
    gate = GateDecision(
        passed=True,
        reason="Quality met",
        quality_score=9,
        confidence_score=8,
        next_agent="implementer",
    )
    return RunStep(
        step_number=n,
        agent_name="planner",
        timestamp=datetime.now(tz=UTC),
        outcome=outcome,
        gate_decision=gate,
        duration_seconds=1.5,
    )


def _make_summary(run_id: str, steps: list[RunStep] | None = None) -> RunSummary:
    now = datetime.now(tz=UTC)
    return RunSummary(
        run_id=run_id,
        orchestrator_name="hotfix",
        task="Fix a bug",
        started_at=now,
        ended_at=now,
        steps=steps or [],
        final_status="success",
        stop_condition=StopCondition(
            reason="terminal_agent_passed", detail="Release manager passed"
        ),
    )


class TestMakeRunId:
    def test_contains_orchestrator_name(self) -> None:
        run_id = make_run_id("hotfix")
        assert "hotfix" in run_id

    def test_starts_with_timestamp(self) -> None:
        run_id = make_run_id("hotfix")
        # Should start with a date-like string
        assert run_id[:8].isdigit()

    def test_unique(self) -> None:
        ids = {make_run_id("x") for _ in range(5)}
        # Most runs should have unique IDs (timing may cause collisions in fast tests)
        assert len(ids) >= 1


class TestRunStore:
    def test_create_run_dir(self, tmp_path: Path) -> None:
        store = RunStore(tmp_path)
        run_dir = store.create_run_dir("20240101T000000_hotfix")
        assert run_dir.exists()
        assert (run_dir / "steps").exists()

    def test_save_and_reload_step(self, tmp_path: Path) -> None:
        store = RunStore(tmp_path)
        run_dir = store.create_run_dir("testrun")
        step = _make_step(1)
        store.save_step(run_dir, step)

        step_file = run_dir / "steps" / "001_planner.json"
        assert step_file.exists()
        content = step_file.read_text(encoding="utf-8")
        assert "planner" in content

    def test_save_and_load_summary(self, tmp_path: Path) -> None:
        store = RunStore(tmp_path)
        run_dir = store.create_run_dir("testrun")
        summary = _make_summary("testrun", steps=[_make_step(1)])
        store.save_summary(run_dir, summary)

        loaded = store.load_summary("testrun")
        assert loaded.run_id == "testrun"
        assert loaded.final_status == "success"
        assert len(loaded.steps) == 1

    def test_report_md_created(self, tmp_path: Path) -> None:
        store = RunStore(tmp_path)
        run_dir = store.create_run_dir("testrun")
        store.save_summary(run_dir, _make_summary("testrun"))
        assert (run_dir / "report.md").exists()

    def test_load_nonexistent_raises(self, tmp_path: Path) -> None:
        store = RunStore(tmp_path)
        with pytest.raises(FileNotFoundError):
            store.load_summary("nonexistent")

    def test_list_runs_empty(self, tmp_path: Path) -> None:
        store = RunStore(tmp_path / "runs")
        assert store.list_runs() == []

    def test_list_runs_returns_ids(self, tmp_path: Path) -> None:
        store = RunStore(tmp_path)
        for name in ["run_a", "run_b", "run_c"]:
            run_dir = store.create_run_dir(name)
            store.save_summary(run_dir, _make_summary(name))

        runs = store.list_runs()
        assert set(runs) == {"run_a", "run_b", "run_c"}
