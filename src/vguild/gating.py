"""Quality gate logic — controls agent handoffs and pipeline progression."""

from __future__ import annotations

from vguild.config import GatingConfig
from vguild.models import AgentOutcome, GateDecision, OrchestratorDefinition


def evaluate_gate(
    outcome: AgentOutcome,
    orchestrator: OrchestratorDefinition,
    config: GatingConfig,
    current_agent: str,
) -> GateDecision:
    """Evaluate whether an agent outcome passes the quality gate.

    Evaluation order (first failure wins):
      1. needs_human → fail
      2. status == "stop" → fail (stop_reason propagated)
      3. status == "blocked" and fail_on_blocked → fail
      4. quality_score below effective threshold → fail
      5. No valid next agent and not a terminal → fail
      6. Otherwise → pass
    """
    # Effective threshold: higher of orchestrator setting and CLI override
    threshold = max(orchestrator.quality_threshold, config.min_quality)

    # 1. Human escalation required
    if outcome.needs_human:
        return GateDecision(
            passed=False,
            reason="Agent requires human intervention",
            quality_score=outcome.quality_score,
            confidence_score=outcome.confidence_score,
            next_agent=None,
        )

    # 2. Explicit stop signal
    if outcome.status == "stop":
        return GateDecision(
            passed=False,
            reason=f"Agent stopped: {outcome.stop_reason or 'no reason given'}",
            quality_score=outcome.quality_score,
            confidence_score=outcome.confidence_score,
            next_agent=None,
        )

    # 3. Blocked with strict mode
    if outcome.status == "blocked" and config.fail_on_blocked:
        return GateDecision(
            passed=False,
            reason="Agent is blocked (fail_on_blocked=True)",
            quality_score=outcome.quality_score,
            confidence_score=outcome.confidence_score,
            next_agent=None,
        )

    # 4. Quality threshold
    if outcome.quality_score < threshold:
        return GateDecision(
            passed=False,
            reason=(
                f"Quality score {outcome.quality_score}/10 is below threshold {threshold}/10"
            ),
            quality_score=outcome.quality_score,
            confidence_score=outcome.confidence_score,
            next_agent=None,
        )

    # 5. Determine next agent
    next_agent = _resolve_next_agent(outcome, orchestrator, current_agent)
    is_terminal = current_agent in orchestrator.terminal_agents

    if next_agent is None and not is_terminal:
        return GateDecision(
            passed=False,
            reason=f"No valid next agent defined for {current_agent!r}",
            quality_score=outcome.quality_score,
            confidence_score=outcome.confidence_score,
            next_agent=None,
        )

    return GateDecision(
        passed=True,
        reason=f"Quality score {outcome.quality_score}/10 meets threshold {threshold}/10",
        quality_score=outcome.quality_score,
        confidence_score=outcome.confidence_score,
        next_agent=next_agent,
    )


def _resolve_next_agent(
    outcome: AgentOutcome,
    orchestrator: OrchestratorDefinition,
    current_agent: str,
) -> str | None:
    """Determine the next agent using allowed_handoffs and agent recommendation."""
    if current_agent in orchestrator.terminal_agents:
        return None

    allowed = orchestrator.allowed_handoffs.get(current_agent, [])
    if not allowed:
        return None

    # Honour agent recommendation if it is in the allowed set
    if outcome.recommended_next_agent and outcome.recommended_next_agent in allowed:
        return outcome.recommended_next_agent

    # Default to the first allowed handoff
    return allowed[0]


def check_progress(last_score: int | None, current_score: int) -> bool:
    """Return True when quality improved since the last round."""
    if last_score is None:
        return True
    return current_score > last_score
