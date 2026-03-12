"""Tests for quality gate logic."""

from __future__ import annotations

from vguild.config import GatingConfig
from vguild.gating import check_progress, evaluate_gate
from vguild.models import AgentOutcome, OrchestratorDefinition

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_orchestrator(
    entry: str = "planner",
    terminals: list[str] | None = None,
    threshold: int = 8,
    handoffs: dict[str, list[str]] | None = None,
) -> OrchestratorDefinition:
    return OrchestratorDefinition(
        name="test",
        description="test",
        entry_agent=entry,
        terminal_agents=terminals or ["release-manager"],
        quality_threshold=threshold,
        max_rounds=10,
        max_no_progress=2,
        allowed_handoffs=handoffs if handoffs is not None else {"planner": ["implementer"]},
    )


def make_outcome(
    agent: str = "planner",
    status: str = "pass",
    quality: int = 9,
    confidence: int = 8,
    recommended: str | None = None,
    needs_human: bool = False,
    stop_reason: str | None = None,
) -> AgentOutcome:
    return AgentOutcome(
        agent_name=agent,
        status=status,  # type: ignore[arg-type]
        quality_score=quality,
        confidence_score=confidence,
        summary="Test outcome.",
        recommended_next_agent=recommended,
        needs_human=needs_human,
        stop_reason=stop_reason,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEvaluateGate:
    def test_pass_sufficient_quality(self) -> None:
        orch = make_orchestrator(handoffs={"planner": ["implementer"]})
        outcome = make_outcome(quality=9)
        gate = evaluate_gate(outcome, orch, GatingConfig(min_quality=8), "planner")
        assert gate.passed is True
        assert gate.next_agent == "implementer"

    def test_fail_below_threshold(self) -> None:
        orch = make_orchestrator(handoffs={"planner": ["implementer"]})
        outcome = make_outcome(quality=7)
        gate = evaluate_gate(outcome, orch, GatingConfig(min_quality=8), "planner")
        assert gate.passed is False
        assert "7" in gate.reason

    def test_exact_threshold_passes(self) -> None:
        orch = make_orchestrator(threshold=8, handoffs={"planner": ["implementer"]})
        outcome = make_outcome(quality=8)
        gate = evaluate_gate(outcome, orch, GatingConfig(min_quality=8), "planner")
        assert gate.passed is True

    def test_needs_human_fails(self) -> None:
        orch = make_orchestrator(handoffs={"planner": ["implementer"]})
        outcome = make_outcome(quality=10, needs_human=True)
        gate = evaluate_gate(outcome, orch, GatingConfig(), "planner")
        assert gate.passed is False
        assert "human" in gate.reason.lower()
        assert gate.next_agent is None

    def test_stop_status_fails(self) -> None:
        orch = make_orchestrator(handoffs={"planner": ["implementer"]})
        outcome = make_outcome(quality=10, status="stop", stop_reason="Critical issue")
        gate = evaluate_gate(outcome, orch, GatingConfig(), "planner")
        assert gate.passed is False
        assert "stopped" in gate.reason.lower() or "stop" in gate.reason.lower()

    def test_blocked_with_fail_on_blocked(self) -> None:
        orch = make_orchestrator(handoffs={"planner": ["implementer"]})
        outcome = make_outcome(quality=9, status="blocked")
        gate = evaluate_gate(
            outcome, orch, GatingConfig(fail_on_blocked=True), "planner"
        )
        assert gate.passed is False

    def test_blocked_without_fail_on_blocked(self) -> None:
        # blocked + high quality + no fail_on_blocked → pass (gate checks quality only)
        orch = make_orchestrator(handoffs={"planner": ["implementer"]})
        outcome = make_outcome(quality=9, status="blocked")
        gate = evaluate_gate(
            outcome, orch, GatingConfig(fail_on_blocked=False), "planner"
        )
        assert gate.passed is True

    def test_terminal_agent_pass_no_next(self) -> None:
        orch = make_orchestrator(
            terminals=["release-manager"],
            handoffs={"planner": ["release-manager"]},
        )
        outcome = make_outcome(agent="release-manager", quality=9)
        gate = evaluate_gate(outcome, orch, GatingConfig(), "release-manager")
        assert gate.passed is True
        assert gate.next_agent is None

    def test_recommended_agent_used(self) -> None:
        orch = make_orchestrator(handoffs={"planner": ["implementer", "reviewer"]})
        outcome = make_outcome(quality=9, recommended="reviewer")
        gate = evaluate_gate(outcome, orch, GatingConfig(min_quality=8), "planner")
        assert gate.passed is True
        assert gate.next_agent == "reviewer"

    def test_recommended_not_in_allowed_uses_default(self) -> None:
        orch = make_orchestrator(handoffs={"planner": ["implementer"]})
        outcome = make_outcome(quality=9, recommended="nonexistent-agent")
        gate = evaluate_gate(outcome, orch, GatingConfig(min_quality=8), "planner")
        assert gate.passed is True
        assert gate.next_agent == "implementer"

    def test_cli_min_quality_overrides_orchestrator_threshold(self) -> None:
        # Orchestrator threshold = 8, CLI min_quality = 9 → effective threshold = 9
        orch = make_orchestrator(threshold=8, handoffs={"planner": ["implementer"]})
        outcome = make_outcome(quality=8)
        gate = evaluate_gate(outcome, orch, GatingConfig(min_quality=9), "planner")
        assert gate.passed is False

    def test_no_handoffs_defined_non_terminal_fails(self) -> None:
        orch = make_orchestrator(handoffs={})  # no handoffs
        outcome = make_outcome(quality=9)
        gate = evaluate_gate(outcome, orch, GatingConfig(), "planner")
        assert gate.passed is False


class TestCheckProgress:
    def test_no_previous_score_is_progress(self) -> None:
        assert check_progress(None, 5) is True

    def test_improvement_is_progress(self) -> None:
        assert check_progress(5, 7) is True

    def test_same_score_is_not_progress(self) -> None:
        assert check_progress(7, 7) is False

    def test_lower_score_is_not_progress(self) -> None:
        assert check_progress(8, 6) is False
