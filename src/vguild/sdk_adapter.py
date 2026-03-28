"""Adapter that runs agents via the Anthropic API and validates structured outputs."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import anthropic

from vguild.models import AgentDefinition, AgentOutcome, Document

logger = logging.getLogger(__name__)

# Tool name used to capture the structured output
_OUTCOME_TOOL_NAME = "submit_outcome"

_OUTCOME_TOOL: dict[str, Any] = {
    "name": _OUTCOME_TOOL_NAME,
    "description": (
        "Submit the final structured outcome of your analysis. "
        "Call this exactly once as your last action."
    ),
    "input_schema": AgentOutcome.model_json_schema(),
}

# Model alias map — update as new Claude models are released
_MODEL_ALIASES: dict[str, str] = {
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}

_STRUCTURED_OUTPUT_SUFFIX = """
---

## Output Instructions

After completing your analysis you MUST call the `submit_outcome` tool with your findings.
Do NOT return plain text — only tool use is accepted as your final response.

Field guidance:
- `status`: "pass" complete, "revise" needs work, "blocked" missing dependency, "stop" halt pipeline
- `quality_score` / `confidence_score`: honest 0–10 integers (10 = production-ready)
- `summary`: one paragraph describing what you did
- `findings`: bullet-level key observations
- `artifacts_changed`: file paths or resources you examined or modified
- `tests_run`: test files or commands executed
- `recommended_next_agent`: name of the agent best suited to continue (or null)
- `notes_for_next_agent`: specific instructions for whoever handles this next
"""


class SDKAdapter:
    """Calls the Anthropic API to run guild agents and returns validated AgentOutcome objects."""

    def __init__(
        self,
        api_key: str | None = None,
        dry_run: bool = False,
    ) -> None:
        self.dry_run = dry_run
        self._client: anthropic.Anthropic | None = None
        if not dry_run:
            self._client = anthropic.Anthropic(api_key=api_key)

    def run_agent(
        self,
        agent: AgentDefinition,
        task: str,
        context: dict[str, Any] | None = None,
        documents: list[Document] | None = None,
    ) -> AgentOutcome:
        """Run an agent for the given task and return a validated AgentOutcome.

        In dry_run mode returns a synthesised outcome without calling the API.
        """
        if self.dry_run:
            return self._dry_run_outcome(agent, task)

        system_prompt = self._build_system_prompt(agent)
        user_message = self._build_user_message(task, context, documents)
        model = _resolve_model(agent.model)

        logger.debug("Running agent %r with model %s", agent.name, model)
        assert self._client is not None

        response = self._client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            tools=[_OUTCOME_TOOL],
            tool_choice={"type": "tool", "name": _OUTCOME_TOOL_NAME},
            messages=[{"role": "user", "content": user_message}],
        )

        return self._extract_outcome(agent.name, response)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_system_prompt(self, agent: AgentDefinition) -> str:
        return agent.system_prompt + _STRUCTURED_OUTPUT_SUFFIX

    def _build_user_message(
        self,
        task: str,
        context: dict[str, Any] | None,
        documents: list[Document] | None = None,
    ) -> str:
        parts: list[str] = [f"## Task\n\n{task}"]

        if documents:
            parts.append(self._render_documents(documents))

        if context:
            # Carry over a repair hint if the previous attempt failed validation
            if repair := context.get("repair_hint"):
                parts.append(f"## ⚠ Repair Required\n\n{repair}")
                return "\n\n".join(parts)

            notes = context.get("notes_for_next_agent") or []
            if notes:
                bullet_notes = "\n".join(f"- {n}" for n in notes)
                parts.append(f"## Context from Previous Agent\n\n{bullet_notes}")

            findings = context.get("findings") or []
            if findings:
                bullet_findings = "\n".join(f"- {f}" for f in findings)
                parts.append(f"## Previous Findings\n\n{bullet_findings}")

            artifacts = context.get("artifacts_changed") or []
            if artifacts:
                bullet_artifacts = "\n".join(f"- `{a}`" for a in artifacts)
                parts.append(f"## Artifacts in Scope\n\n{bullet_artifacts}")

            if context.get("needs_revision"):
                gate_reason = context.get("gate_reason", "quality threshold not met")
                parts.append(
                    f"## Revision Required\n\n"
                    f"Your previous attempt did not pass the quality gate: **{gate_reason}**. "
                    "Please improve your output."
                )

        return "\n\n".join(parts)

    @staticmethod
    def _render_documents(documents: list[Document]) -> str:
        """Render attached documents as labeled sections in the user message."""
        _CODE_FENCE_LANGS: dict[str, str] = {
            "application/json": "json",
            "text/yaml": "yaml",
            "text/x-python": "python",
        }
        sections: list[str] = []
        for doc in documents:
            header = f"## Reference Document: {doc.label}"
            if doc.truncated:
                header += " (truncated)"

            lang = _CODE_FENCE_LANGS.get(doc.content_type)
            body = f"```{lang}\n{doc.content}\n```" if lang else doc.content

            sections.append(f"{header}\n\n{body}")
        return "\n\n".join(sections)

    def _extract_outcome(self, agent_name: str, response: anthropic.types.Message) -> AgentOutcome:
        """Extract and validate AgentOutcome from a tool-use response."""
        for block in response.content:
            if block.type == "tool_use" and block.name == _OUTCOME_TOOL_NAME:
                data: dict[str, Any] = dict(block.input)
                data.setdefault("agent_name", agent_name)
                try:
                    return AgentOutcome.model_validate(data)
                except Exception as exc:
                    raise ValueError(
                        f"Agent {agent_name!r} returned invalid AgentOutcome: {exc}"
                    ) from exc

        # Fallback: try parsing text content as JSON (shouldn't normally happen)
        for block in response.content:
            if hasattr(block, "text"):
                try:
                    json_str = _extract_json(block.text)
                    data = json.loads(json_str)
                    data.setdefault("agent_name", agent_name)
                    return AgentOutcome.model_validate(data)
                except Exception:
                    pass

        raise ValueError(
            f"Agent {agent_name!r} did not call {_OUTCOME_TOOL_NAME!r}. "
            f"Response stop reason: {response.stop_reason}"
        )

    def _dry_run_outcome(self, agent: AgentDefinition, task: str) -> AgentOutcome:
        """Return a synthetic pass outcome for dry-run/testing."""
        return AgentOutcome(
            agent_name=agent.name,
            status="pass",
            quality_score=9,
            confidence_score=8,
            summary=f"[DRY RUN] {agent.name} completed task: {task[:80]}",
            findings=["[DRY RUN] No actual analysis performed"],
            artifacts_changed=[],
            tests_run=[],
            recommended_next_agent=None,
            needs_human=False,
            stop_reason=None,
            notes_for_next_agent=[f"[DRY RUN] Placeholder notes from {agent.name}"],
        )


def _resolve_model(alias: str) -> str:
    """Map a short alias to a full Claude model ID."""
    return _MODEL_ALIASES.get(alias, alias)


def _extract_json(text: str) -> str:
    """Extract a JSON object from text, handling markdown code fences."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text
