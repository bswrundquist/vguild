"""Core orchestrator loop — pipeline execution, gate checks, and stopping criteria."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from vguild.config import GatingConfig
from vguild.gating import check_progress, evaluate_gate
from vguild.models import (
    AgentOutcome,
    OrchestratorDefinition,
    OrchestratorState,
    RunStep,
    RunSummary,
    StopCondition,
)
from vguild.registry import Registry
from vguild.run_store import RunStore, make_run_id
from vguild.sdk_adapter import SDKAdapter

logger = logging.getLogger(__name__)


class OrchestratorRunner:
    """Runs a full agent pipeline for a given orchestrator definition.

    Pipeline loop:
      1. Run current agent (with retry on validation failure)
      2. Evaluate quality gate
      3. Check stopping criteria
      4. Advance to next agent (or stop)
    """

    def __init__(
        self,
        orchestrator: OrchestratorDefinition,
        registry: Registry,
        adapter: SDKAdapter,
        store: RunStore,
        config: GatingConfig | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.registry = registry
        self.adapter = adapter
        self.store = store
        self.config = config or GatingConfig()

    def run(self, task: str) -> RunSummary:
        """Execute the pipeline and return a complete RunSummary."""
        run_id = make_run_id(self.orchestrator.name)
        run_dir = self.store.create_run_dir(run_id)
        started_at = datetime.now(tz=UTC)

        logger.info(
            "[bold]Starting run[/bold] [cyan]%s[/cyan] — orchestrator: %s",
            run_id,
            self.orchestrator.name,
        )
        logger.info("Task: %s", task[:120] + ("…" if len(task) > 120 else ""))

        state = OrchestratorState(current_agent=self.orchestrator.entry_agent)
        context: dict[str, Any] = {}
        stop_condition: StopCondition | None = None
        final_status = "failed"

        while True:
            state.round_number += 1

            # ── Stopping criterion: max rounds ────────────────────────────
            if state.round_number > self.config.max_rounds:
                stop_condition = StopCondition(
                    reason="max_rounds_reached",
                    detail=f"Reached maximum of {self.config.max_rounds} rounds",
                )
                logger.warning("Stopping: %s", stop_condition.detail)
                break

            logger.info(
                "Round %d/%d — agent: [cyan]%s[/cyan]",
                state.round_number,
                self.config.max_rounds,
                state.current_agent,
            )

            # ── Run agent (with one validation-failure retry) ─────────────
            agent_def = self.registry.get_agent(state.current_agent)
            start_time = time.monotonic()
            outcome, error = self._run_agent_safe(agent_def, task, context)
            duration = time.monotonic() - start_time

            if outcome is None:
                state.validation_failure_count += 1
                logger.error(
                    "Validation failure #%d: %s",
                    state.validation_failure_count,
                    error,
                )
                if state.validation_failure_count >= 2:
                    stop_condition = StopCondition(
                        reason="validation_failure",
                        detail=f"Two consecutive validation failures: {error}",
                    )
                    break
                # Inject repair context and retry without incrementing round
                context["repair_hint"] = (
                    f"Previous response was invalid. Error: {error}. "
                    "You MUST call submit_outcome with a valid AgentOutcome JSON."
                )
                state.round_number -= 1  # Don't count the repair attempt
                continue

            # Reset validation counter and clear repair context
            state.validation_failure_count = 0
            context.pop("repair_hint", None)

            # ── Evaluate quality gate ─────────────────────────────────────
            gate = evaluate_gate(
                outcome=outcome,
                orchestrator=self.orchestrator,
                config=self.config,
                current_agent=state.current_agent,
            )

            # Record step
            step = RunStep(
                step_number=len(state.steps) + 1,
                agent_name=state.current_agent,
                timestamp=datetime.now(tz=UTC),
                outcome=outcome,
                gate_decision=gate,
                duration_seconds=duration,
            )
            state.steps.append(step)
            self.store.save_step(run_dir, step)

            gate_symbol = "✓" if gate.passed else "✗"
            logger.info(
                "  Q:%d/10  C:%d/10  gate:%s  (%s)",
                outcome.quality_score,
                outcome.confidence_score,
                gate_symbol,
                gate.reason,
            )

            # ── Check hard stopping signals ───────────────────────────────
            if outcome.needs_human:
                stop_condition = StopCondition(
                    reason="needs_human",
                    detail=f"Agent {state.current_agent!r} requires human intervention",
                )
                final_status = "blocked"
                break

            if outcome.status == "stop":
                stop_condition = StopCondition(
                    reason="stop_signal",
                    detail=(
                        f"Agent {state.current_agent!r}: "
                        f"{outcome.stop_reason or 'stop signal received'}"
                    ),
                )
                break

            # ── Terminal agent pass ───────────────────────────────────────
            if state.current_agent in self.orchestrator.terminal_agents and gate.passed:
                stop_condition = StopCondition(
                    reason="terminal_agent_passed",
                    detail=(
                        f"Terminal agent {state.current_agent!r} passed "
                        f"with quality {outcome.quality_score}/10"
                    ),
                )
                final_status = "success"
                logger.info("[green]Pipeline complete![/green] %s", stop_condition.detail)
                break

            # ── Gate failed ───────────────────────────────────────────────
            if not gate.passed:
                if outcome.status == "blocked":
                    state.block_count += 1
                    logger.warning(
                        "Agent blocked (%d/%d)", state.block_count, 2
                    )
                    if state.block_count >= 2:
                        stop_condition = StopCondition(
                            reason="repeated_block",
                            detail=f"Blocked {state.block_count} times consecutively",
                        )
                        final_status = "blocked"
                        break
                else:
                    state.block_count = 0

                # Check no-progress
                if not check_progress(state.last_quality_score, outcome.quality_score):
                    state.no_progress_count += 1
                    logger.warning(
                        "No quality progress (%d/%d), score=%d",
                        state.no_progress_count,
                        self.config.max_no_progress,
                        outcome.quality_score,
                    )
                    if state.no_progress_count >= self.config.max_no_progress:
                        stop_condition = StopCondition(
                            reason="no_progress",
                            detail=(
                                f"Quality score stuck at {outcome.quality_score}/10 "
                                f"for {state.no_progress_count} rounds"
                            ),
                        )
                        break
                else:
                    state.no_progress_count = 0

                state.last_quality_score = outcome.quality_score

                # Retry same agent with revision context
                context = _build_context(outcome)
                context["needs_revision"] = True
                context["gate_reason"] = gate.reason
                logger.info("  Gate failed — retrying [cyan]%s[/cyan]", state.current_agent)
                continue

            # ── Gate passed — advance pipeline ────────────────────────────
            state.block_count = 0
            state.no_progress_count = 0
            state.last_quality_score = None

            if gate.next_agent:
                context = _build_context(outcome)
                state.current_agent = gate.next_agent
                logger.info("  Advancing to: [cyan]%s[/cyan]", state.current_agent)
            else:
                # Passed but no next agent (edge case — terminal with no handoff defined)
                stop_condition = StopCondition(
                    reason="terminal_agent_passed",
                    detail=f"Agent {state.current_agent!r} passed — no further handoffs",
                )
                final_status = "success"
                break

        ended_at = datetime.now(tz=UTC)

        summary = RunSummary(
            run_id=run_id,
            orchestrator_name=self.orchestrator.name,
            task=task,
            started_at=started_at,
            ended_at=ended_at,
            steps=state.steps,
            final_status=final_status,
            stop_condition=stop_condition,
        )
        self.store.save_summary(run_dir, summary)

        logger.info(
            "Run [cyan]%s[/cyan] finished — [bold]%s[/bold]",
            run_id,
            final_status.upper(),
        )
        if stop_condition:
            logger.info("Stop: %s — %s", stop_condition.reason, stop_condition.detail)

        return summary

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_agent_safe(
        self,
        agent_def: Any,
        task: str,
        context: dict[str, Any],
    ) -> tuple[AgentOutcome | None, str | None]:
        """Run an agent, capturing validation errors without raising."""
        try:
            return self.adapter.run_agent(agent_def, task, context), None
        except (ValueError, Exception) as exc:
            return None, str(exc)


def _build_context(outcome: AgentOutcome) -> dict[str, Any]:
    """Build context dict to pass to the next agent."""
    return {
        "previous_agent": outcome.agent_name,
        "notes_for_next_agent": outcome.notes_for_next_agent,
        "findings": outcome.findings,
        "artifacts_changed": outcome.artifacts_changed,
        "summary": outcome.summary,
    }
