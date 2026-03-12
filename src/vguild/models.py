"""Pydantic models for structured agent outputs and orchestrator state."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AgentOutcome(BaseModel):
    """Structured output returned by every agent in the guild."""

    agent_name: str
    status: Literal["pass", "revise", "blocked", "stop"]
    quality_score: int = Field(ge=0, le=10, description="Overall quality 0–10")
    confidence_score: int = Field(ge=0, le=10, description="Confidence in output 0–10")
    summary: str = Field(description="One-paragraph summary of what was done")
    findings: list[str] = Field(default_factory=list, description="Key findings or observations")
    artifacts_changed: list[str] = Field(
        default_factory=list, description="Files or resources modified"
    )
    tests_run: list[str] = Field(default_factory=list, description="Test suites or checks executed")
    recommended_next_agent: str | None = Field(
        default=None, description="Suggested next agent name"
    )
    needs_human: bool = Field(default=False, description="Escalate to human if True")
    stop_reason: str | None = Field(
        default=None, description="Reason to halt pipeline (when status=stop)"
    )
    notes_for_next_agent: list[str] = Field(
        default_factory=list, description="Instructions passed to the next agent"
    )

    @field_validator("quality_score", "confidence_score")
    @classmethod
    def validate_score(cls, v: int) -> int:
        if not 0 <= v <= 10:
            raise ValueError(f"Score must be 0–10, got {v}")
        return v


class GateDecision(BaseModel):
    """Result of a quality gate evaluation."""

    passed: bool
    reason: str
    quality_score: int
    confidence_score: int
    next_agent: str | None = None
    override_applied: bool = False


class RunStep(BaseModel):
    """A single agent execution within an orchestrator run."""

    step_number: int
    agent_name: str
    timestamp: datetime
    outcome: AgentOutcome
    gate_decision: GateDecision
    duration_seconds: float


class StopCondition(BaseModel):
    """The reason an orchestrator pipeline stopped."""

    reason: Literal[
        "terminal_agent_passed",
        "max_rounds_reached",
        "repeated_block",
        "no_progress",
        "needs_human",
        "validation_failure",
        "stop_signal",
    ]
    detail: str


class RunSummary(BaseModel):
    """Complete summary of an orchestrator run."""

    run_id: str
    orchestrator_name: str
    task: str
    started_at: datetime
    ended_at: datetime
    steps: list[RunStep] = Field(default_factory=list)
    final_status: Literal["success", "failed", "stopped", "blocked"]
    stop_condition: StopCondition | None = None


class OrchestratorState(BaseModel):
    """Mutable runtime state tracked during an orchestrator loop."""

    current_agent: str
    round_number: int = 0
    no_progress_count: int = 0
    block_count: int = 0
    validation_failure_count: int = 0
    last_quality_score: int | None = None
    steps: list[RunStep] = Field(default_factory=list)


class AgentDefinition(BaseModel):
    """Parsed agent definition from a catalog .md file."""

    name: str
    description: str
    model: str = "sonnet"
    tools: list[str] = Field(default_factory=list)
    max_turns: int = 5
    tags: list[str] = Field(default_factory=list)
    system_prompt: str  # Full Markdown body


class OrchestratorDefinition(BaseModel):
    """Parsed orchestrator definition from a catalog .md file."""

    name: str
    description: str
    entry_agent: str
    terminal_agents: list[str]
    quality_threshold: int = Field(default=8, ge=0, le=10)
    max_rounds: int = 10
    max_no_progress: int = 2
    allowed_handoffs: dict[str, list[str]] = Field(default_factory=dict)
    system_prompt: str = ""  # Optional orchestrator-level context
