"""Load and parse agent/orchestrator prompt files with YAML frontmatter."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from vguild.models import AgentDefinition, OrchestratorDefinition

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n?---\s*\n(.*)", re.DOTALL)


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter from the Markdown body.

    Returns a (metadata_dict, body_str) tuple. If no frontmatter is found,
    returns ({}, original_content).
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}, content

    raw_yaml = match.group(1)
    body = match.group(2).strip()

    try:
        metadata: dict[str, Any] = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML frontmatter: {exc}") from exc

    return metadata, body


def load_agent(path: Path) -> AgentDefinition:
    """Load an AgentDefinition from a Markdown file."""
    content = path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)

    return AgentDefinition(
        name=metadata.get("name", path.stem),
        description=metadata.get("description", ""),
        model=metadata.get("model", "sonnet"),
        tools=metadata.get("tools") or [],
        max_turns=int(metadata.get("max_turns", 5)),
        tags=metadata.get("tags") or [],
        system_prompt=body,
    )


def load_orchestrator(path: Path) -> OrchestratorDefinition:
    """Load an OrchestratorDefinition from a Markdown file."""
    content = path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)

    if "entry_agent" not in metadata:
        raise ValueError(f"{path}: missing required frontmatter key 'entry_agent'")

    return OrchestratorDefinition(
        name=metadata.get("name", path.stem),
        description=metadata.get("description", ""),
        entry_agent=metadata["entry_agent"],
        terminal_agents=metadata.get("terminal_agents") or [],
        quality_threshold=int(metadata.get("quality_threshold", 8)),
        max_rounds=int(metadata.get("max_rounds", 10)),
        max_no_progress=int(metadata.get("max_no_progress", 2)),
        allowed_handoffs=metadata.get("allowed_handoffs") or {},
        system_prompt=body,
    )
