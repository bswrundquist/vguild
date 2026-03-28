"""Tests for Pydantic model validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vguild.models import AgentOutcome, Document, OrchestratorState


class TestAgentOutcome:
    def test_valid_outcome(self) -> None:
        o = AgentOutcome(
            agent_name="planner",
            status="pass",
            quality_score=9,
            confidence_score=8,
            summary="Done.",
            findings=[],
            artifacts_changed=[],
            tests_run=[],
            recommended_next_agent=None,
            needs_human=False,
            stop_reason=None,
            notes_for_next_agent=[],
        )
        assert o.quality_score == 9
        assert o.status == "pass"

    def test_score_bounds(self) -> None:
        with pytest.raises(ValidationError):
            AgentOutcome(
                agent_name="x",
                status="pass",
                quality_score=11,  # invalid
                confidence_score=5,
                summary="",
            )

    def test_score_zero_valid(self) -> None:
        o = AgentOutcome(
            agent_name="x",
            status="blocked",
            quality_score=0,
            confidence_score=0,
            summary="Nothing done.",
        )
        assert o.quality_score == 0

    def test_invalid_status(self) -> None:
        with pytest.raises(ValidationError):
            AgentOutcome(
                agent_name="x",
                status="unknown",  # type: ignore[arg-type]
                quality_score=5,
                confidence_score=5,
                summary="Bad status.",
            )

    def test_defaults(self) -> None:
        o = AgentOutcome(
            agent_name="x",
            status="pass",
            quality_score=8,
            confidence_score=8,
            summary="OK.",
        )
        assert o.findings == []
        assert o.artifacts_changed == []
        assert o.tests_run == []
        assert o.needs_human is False
        assert o.recommended_next_agent is None
        assert o.notes_for_next_agent == []

    def test_model_json_schema_has_required_fields(self) -> None:
        schema = AgentOutcome.model_json_schema()
        props = schema.get("properties", {})
        assert "agent_name" in props
        assert "status" in props
        assert "quality_score" in props
        assert "confidence_score" in props


class TestDocument:
    def test_create_with_defaults(self) -> None:
        doc = Document(label="PRD", source="/tmp/prd.md", content="Hello")
        assert doc.content_type == "text/markdown"
        assert doc.truncated is False

    def test_explicit_fields(self) -> None:
        doc = Document(
            label="JIRA-1234",
            source="https://jira.example.com/JIRA-1234",
            content='{"key": "value"}',
            content_type="application/json",
            truncated=True,
        )
        assert doc.label == "JIRA-1234"
        assert doc.truncated is True
        assert doc.content_type == "application/json"

    def test_model_dump_roundtrip(self) -> None:
        doc = Document(label="design", source="inline", content="Some text")
        data = doc.model_dump()
        doc2 = Document.model_validate(data)
        assert doc == doc2


class TestOrchestratorState:
    def test_initial_state(self) -> None:
        state = OrchestratorState(current_agent="planner")
        assert state.round_number == 0
        assert state.no_progress_count == 0
        assert state.block_count == 0
        assert state.validation_failure_count == 0
        assert state.steps == []

    def test_mutation(self) -> None:
        state = OrchestratorState(current_agent="planner")
        state.round_number += 1
        state.no_progress_count += 1
        assert state.round_number == 1
        assert state.no_progress_count == 1
