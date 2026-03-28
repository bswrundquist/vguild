"""Tests for OrchestratorRunner — pipeline loop with mocked SDK adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vguild.config import GatingConfig
from vguild.models import AgentDefinition, AgentOutcome, Document
from vguild.orchestrators.base import OrchestratorRunner
from vguild.registry import Registry
from vguild.run_store import RunStore

# ---------------------------------------------------------------------------
# Mock adapter helpers
# ---------------------------------------------------------------------------


def _make_outcome(
    agent_name: str,
    status: str = "pass",
    quality: int = 9,
    recommended_next: str | None = None,
    needs_human: bool = False,
    stop_reason: str | None = None,
    notes: list[str] | None = None,
) -> AgentOutcome:
    return AgentOutcome(
        agent_name=agent_name,
        status=status,  # type: ignore[arg-type]
        quality_score=quality,
        confidence_score=8,
        summary=f"{agent_name} completed.",
        findings=[f"Finding from {agent_name}"],
        artifacts_changed=[],
        tests_run=[],
        recommended_next_agent=recommended_next,
        needs_human=needs_human,
        stop_reason=stop_reason,
        notes_for_next_agent=notes or [f"Notes from {agent_name}"],
    )


class MockAdapter:
    """Returns pre-configured outcomes for each agent in sequence."""

    def __init__(self, outcomes: dict[str, AgentOutcome | list[AgentOutcome]]) -> None:
        self._outcomes = {k: (v if isinstance(v, list) else [v]) for k, v in outcomes.items()}
        self._calls: dict[str, int] = {}

    def run_agent(
        self,
        agent: AgentDefinition,
        task: str,
        context: dict[str, Any] | None = None,
        documents: Any = None,
    ) -> AgentOutcome:
        name = agent.name
        idx = self._calls.get(name, 0)
        outcomes = self._outcomes.get(name, [_make_outcome(name)])
        result = outcomes[min(idx, len(outcomes) - 1)]
        self._calls[name] = idx + 1
        return result

    @property
    def call_counts(self) -> dict[str, int]:
        return dict(self._calls)


class ErrorAdapter:
    """Raises ValueError on every call."""

    def run_agent(
        self, agent: Any, task: str, context: Any = None, documents: Any = None
    ) -> AgentOutcome:
        raise ValueError("Simulated API error")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_full_pipeline_success(self, tmp_path: Path, registry: Registry) -> None:
        """planner → implementer → reviewer → release-manager all pass."""
        adapter = MockAdapter(
            {
                "planner": _make_outcome("planner", quality=9, recommended_next="implementer"),
                "implementer": _make_outcome("implementer", quality=9, recommended_next="reviewer"),
                "reviewer": _make_outcome(
                    "reviewer", quality=9, recommended_next="release-manager"
                ),
                "release-manager": _make_outcome("release-manager", quality=9),
            }
        )
        store = RunStore(tmp_path / "runs")
        orch = registry.get_orchestrator("hotfix")
        runner = OrchestratorRunner(
            orchestrator=orch,
            registry=registry,
            adapter=adapter,  # type: ignore[arg-type]
            store=store,
            config=GatingConfig(min_quality=8),
        )

        summary = runner.run("Fix the login bug")
        assert summary.final_status == "success"
        assert summary.stop_condition is not None
        assert summary.stop_condition.reason == "terminal_agent_passed"
        assert len(summary.steps) == 4

    def test_run_dir_created(self, tmp_path: Path, registry: Registry) -> None:
        adapter = MockAdapter(
            {
                "planner": _make_outcome("planner", quality=9, recommended_next="implementer"),
                "implementer": _make_outcome("implementer", quality=9, recommended_next="reviewer"),
                "reviewer": _make_outcome(
                    "reviewer", quality=9, recommended_next="release-manager"
                ),
                "release-manager": _make_outcome("release-manager", quality=9),
            }
        )
        store = RunStore(tmp_path / "runs")
        orch = registry.get_orchestrator("hotfix")
        runner = OrchestratorRunner(
            orchestrator=orch,
            registry=registry,
            adapter=adapter,  # type: ignore[arg-type]
            store=store,
            config=GatingConfig(min_quality=8),
        )
        summary = runner.run("task")
        run_dir = tmp_path / "runs" / summary.run_id
        assert run_dir.exists()
        assert (run_dir / "summary.json").exists()
        assert (run_dir / "report.md").exists()


class TestStoppingCriteria:
    def test_max_rounds_stops_pipeline(self, tmp_path: Path, registry: Registry) -> None:
        # Always returns low quality — pipeline should stop at max_rounds
        adapter = MockAdapter({"planner": _make_outcome("planner", quality=5, status="revise")})
        store = RunStore(tmp_path / "runs")
        orch = registry.get_orchestrator("hotfix")
        runner = OrchestratorRunner(
            orchestrator=orch,
            registry=registry,
            adapter=adapter,  # type: ignore[arg-type]
            store=store,
            config=GatingConfig(min_quality=8, max_rounds=3, max_no_progress=10),
        )
        summary = runner.run("task")
        assert summary.stop_condition is not None
        assert summary.stop_condition.reason == "max_rounds_reached"
        assert summary.final_status == "failed"

    def test_no_progress_stops_pipeline(self, tmp_path: Path, registry: Registry) -> None:
        # Always returns same low quality — should stop after max_no_progress rounds
        adapter = MockAdapter({"planner": _make_outcome("planner", quality=5, status="revise")})
        store = RunStore(tmp_path / "runs")
        orch = registry.get_orchestrator("hotfix")
        runner = OrchestratorRunner(
            orchestrator=orch,
            registry=registry,
            adapter=adapter,  # type: ignore[arg-type]
            store=store,
            config=GatingConfig(min_quality=8, max_rounds=20, max_no_progress=2),
        )
        summary = runner.run("task")
        assert summary.stop_condition is not None
        assert summary.stop_condition.reason == "no_progress"

    def test_needs_human_stops_pipeline(self, tmp_path: Path, registry: Registry) -> None:
        adapter = MockAdapter({"planner": _make_outcome("planner", quality=10, needs_human=True)})
        store = RunStore(tmp_path / "runs")
        orch = registry.get_orchestrator("hotfix")
        runner = OrchestratorRunner(
            orchestrator=orch,
            registry=registry,
            adapter=adapter,  # type: ignore[arg-type]
            store=store,
            config=GatingConfig(min_quality=8),
        )
        summary = runner.run("task")
        assert summary.stop_condition is not None
        assert summary.stop_condition.reason == "needs_human"
        assert summary.final_status == "blocked"

    def test_stop_status_stops_pipeline(self, tmp_path: Path, registry: Registry) -> None:
        adapter = MockAdapter(
            {
                "planner": _make_outcome(
                    "planner", quality=10, status="stop", stop_reason="Security risk"
                )
            }
        )
        store = RunStore(tmp_path / "runs")
        orch = registry.get_orchestrator("hotfix")
        runner = OrchestratorRunner(
            orchestrator=orch,
            registry=registry,
            adapter=adapter,  # type: ignore[arg-type]
            store=store,
            config=GatingConfig(),
        )
        summary = runner.run("task")
        assert summary.stop_condition is not None
        assert summary.stop_condition.reason == "stop_signal"

    def test_repeated_block_stops_pipeline(self, tmp_path: Path, registry: Registry) -> None:
        adapter = MockAdapter({"planner": _make_outcome("planner", quality=9, status="blocked")})
        store = RunStore(tmp_path / "runs")
        orch = registry.get_orchestrator("hotfix")
        runner = OrchestratorRunner(
            orchestrator=orch,
            registry=registry,
            adapter=adapter,  # type: ignore[arg-type]
            store=store,
            config=GatingConfig(min_quality=8, fail_on_blocked=True, max_rounds=10),
        )
        summary = runner.run("task")
        assert summary.stop_condition is not None
        assert summary.final_status in {"blocked", "failed"}

    def test_validation_failure_stops_after_two(self, tmp_path: Path, registry: Registry) -> None:
        store = RunStore(tmp_path / "runs")
        orch = registry.get_orchestrator("hotfix")
        runner = OrchestratorRunner(
            orchestrator=orch,
            registry=registry,
            adapter=ErrorAdapter(),  # type: ignore[arg-type]
            store=store,
            config=GatingConfig(max_rounds=20),
        )
        summary = runner.run("task")
        assert summary.stop_condition is not None
        assert summary.stop_condition.reason == "validation_failure"


class TestQualityImprovement:
    def test_agent_retried_on_low_quality(self, tmp_path: Path, registry: Registry) -> None:
        """Agent should be retried when quality is low (same agent, two attempts)."""
        adapter = MockAdapter(
            {
                "planner": [
                    _make_outcome("planner", quality=5, status="revise"),
                    _make_outcome("planner", quality=9, recommended_next="implementer"),
                ],
                "implementer": _make_outcome("implementer", quality=9, recommended_next="reviewer"),
                "reviewer": _make_outcome(
                    "reviewer", quality=9, recommended_next="release-manager"
                ),
                "release-manager": _make_outcome("release-manager", quality=9),
            }
        )
        store = RunStore(tmp_path / "runs")
        orch = registry.get_orchestrator("hotfix")
        runner = OrchestratorRunner(
            orchestrator=orch,
            registry=registry,
            adapter=adapter,  # type: ignore[arg-type]
            store=store,
            config=GatingConfig(min_quality=8, max_rounds=15),
        )
        summary = runner.run("task")
        assert summary.final_status == "success"
        # Planner was called twice
        assert adapter.call_counts.get("planner", 0) == 2


class RecordingAdapter(MockAdapter):
    """MockAdapter that also records the documents passed to each call."""

    def __init__(self, outcomes: dict[str, AgentOutcome | list[AgentOutcome]]) -> None:
        super().__init__(outcomes)
        self.received_documents: list[list[Document] | None] = []

    def run_agent(
        self,
        agent: AgentDefinition,
        task: str,
        context: dict[str, Any] | None = None,
        documents: Any = None,
    ) -> AgentOutcome:
        self.received_documents.append(documents)
        return super().run_agent(agent, task, context, documents)


class TestDocuments:
    def test_documents_passed_to_all_agents(self, tmp_path: Path, registry: Registry) -> None:
        """Documents should be forwarded to every agent in the pipeline."""
        adapter = RecordingAdapter(
            {
                "planner": _make_outcome("planner", quality=9, recommended_next="implementer"),
                "implementer": _make_outcome("implementer", quality=9, recommended_next="reviewer"),
                "reviewer": _make_outcome(
                    "reviewer", quality=9, recommended_next="release-manager"
                ),
                "release-manager": _make_outcome("release-manager", quality=9),
            }
        )
        store = RunStore(tmp_path / "runs")
        orch = registry.get_orchestrator("hotfix")
        runner = OrchestratorRunner(
            orchestrator=orch,
            registry=registry,
            adapter=adapter,  # type: ignore[arg-type]
            store=store,
            config=GatingConfig(min_quality=8),
        )
        docs = [
            Document(label="PRD", source="/tmp/prd.md", content="Product requirements"),
            Document(label="JIRA-99", source="inline", content="Bug report details"),
        ]
        summary = runner.run("Fix the bug", documents=docs)
        assert summary.final_status == "success"
        # Every agent call received the documents
        assert len(adapter.received_documents) == 4
        for received in adapter.received_documents:
            assert received == docs

    def test_document_labels_in_summary(self, tmp_path: Path, registry: Registry) -> None:
        adapter = RecordingAdapter(
            {
                "planner": _make_outcome("planner", quality=9, recommended_next="implementer"),
                "implementer": _make_outcome("implementer", quality=9, recommended_next="reviewer"),
                "reviewer": _make_outcome(
                    "reviewer", quality=9, recommended_next="release-manager"
                ),
                "release-manager": _make_outcome("release-manager", quality=9),
            }
        )
        store = RunStore(tmp_path / "runs")
        orch = registry.get_orchestrator("hotfix")
        runner = OrchestratorRunner(
            orchestrator=orch,
            registry=registry,
            adapter=adapter,  # type: ignore[arg-type]
            store=store,
        )
        docs = [Document(label="Design Doc", source="inline", content="Architecture")]
        summary = runner.run("task", documents=docs)
        assert summary.document_labels == ["Design Doc"]

    def test_documents_persisted_to_run_dir(self, tmp_path: Path, registry: Registry) -> None:
        adapter = RecordingAdapter(
            {
                "planner": _make_outcome("planner", quality=9, recommended_next="implementer"),
                "implementer": _make_outcome("implementer", quality=9, recommended_next="reviewer"),
                "reviewer": _make_outcome(
                    "reviewer", quality=9, recommended_next="release-manager"
                ),
                "release-manager": _make_outcome("release-manager", quality=9),
            }
        )
        store = RunStore(tmp_path / "runs")
        orch = registry.get_orchestrator("hotfix")
        runner = OrchestratorRunner(
            orchestrator=orch,
            registry=registry,
            adapter=adapter,  # type: ignore[arg-type]
            store=store,
        )
        docs = [Document(label="PRD", source="inline", content="Content here")]
        summary = runner.run("task", documents=docs)
        docs_file = tmp_path / "runs" / summary.run_id / "documents.json"
        assert docs_file.exists()
        import json

        data = json.loads(docs_file.read_text())
        assert len(data) == 1
        assert data[0]["label"] == "PRD"

    def test_no_documents_file_when_empty(self, tmp_path: Path, registry: Registry) -> None:
        adapter = RecordingAdapter(
            {
                "planner": _make_outcome("planner", quality=9, recommended_next="implementer"),
                "implementer": _make_outcome("implementer", quality=9, recommended_next="reviewer"),
                "reviewer": _make_outcome(
                    "reviewer", quality=9, recommended_next="release-manager"
                ),
                "release-manager": _make_outcome("release-manager", quality=9),
            }
        )
        store = RunStore(tmp_path / "runs")
        orch = registry.get_orchestrator("hotfix")
        runner = OrchestratorRunner(
            orchestrator=orch,
            registry=registry,
            adapter=adapter,  # type: ignore[arg-type]
            store=store,
        )
        summary = runner.run("task")
        docs_file = tmp_path / "runs" / summary.run_id / "documents.json"
        assert not docs_file.exists()
