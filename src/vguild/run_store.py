"""Persist and retrieve run artifacts in runs/<run_id>/."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from vguild.models import RunStep, RunSummary


class RunStore:
    """Manages run artifact storage under a configurable root directory."""

    def __init__(self, runs_dir: Path | str) -> None:
        self.runs_dir = Path(runs_dir)

    def create_run_dir(self, run_id: str) -> Path:
        """Create and return a fresh directory for the given run_id."""
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "steps").mkdir(exist_ok=True)
        return run_dir

    def save_step(self, run_dir: Path, step: RunStep) -> None:
        """Append a step JSON file into runs/<run_id>/steps/."""
        name = f"{step.step_number:03d}_{step.agent_name}.json"
        (run_dir / "steps" / name).write_text(
            step.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def save_summary(self, run_dir: Path, summary: RunSummary) -> None:
        """Write summary.json and a human-readable report.md."""
        (run_dir / "summary.json").write_text(
            summary.model_dump_json(indent=2),
            encoding="utf-8",
        )
        (run_dir / "report.md").write_text(
            _render_markdown_report(summary),
            encoding="utf-8",
        )

    def load_summary(self, run_id: str) -> RunSummary:
        """Load a previously saved RunSummary."""
        path = self.runs_dir / run_id / "summary.json"
        if not path.exists():
            raise FileNotFoundError(f"Run not found: {run_id!r}")
        return RunSummary.model_validate_json(path.read_text(encoding="utf-8"))

    def list_runs(self) -> list[str]:
        """Return all run IDs that have a summary.json, sorted oldest-first."""
        if not self.runs_dir.exists():
            return []
        return sorted(
            d.name
            for d in self.runs_dir.iterdir()
            if d.is_dir() and (d / "summary.json").exists()
        )


def make_run_id(orchestrator_name: str) -> str:
    """Generate a sortable run ID: <timestamp>_<orchestrator_name>."""
    ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S")
    safe_name = orchestrator_name.replace(" ", "_").replace("-", "_")
    return f"{ts}_{safe_name}"


# ---------------------------------------------------------------------------
# Markdown report renderer
# ---------------------------------------------------------------------------


def _render_markdown_report(summary: RunSummary) -> str:
    duration = (summary.ended_at - summary.started_at).total_seconds()
    status_icon = "✅" if summary.final_status == "success" else "❌"

    lines: list[str] = [
        f"# Run Report: {summary.orchestrator_name}",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Run ID | `{summary.run_id}` |",
        f"| Status | {status_icon} {summary.final_status} |",
        f"| Started | {summary.started_at.isoformat()} |",
        f"| Duration | {duration:.1f}s |",
        f"| Steps | {len(summary.steps)} |",
        "",
        "## Task",
        "",
        summary.task,
        "",
        "## Pipeline Steps",
        "",
    ]

    for step in summary.steps:
        o = step.outcome
        g = step.gate_decision
        gate_icon = "✓" if g.passed else "✗"
        lines += [
            f"### Step {step.step_number}: `{step.agent_name}` {gate_icon}",
            "",
            f"- **Status:** `{o.status}`",
            f"- **Quality:** {o.quality_score}/10  **Confidence:** {o.confidence_score}/10",
            f"- **Gate:** {'passed' if g.passed else 'FAILED'} — {g.reason}",
            f"- **Duration:** {step.duration_seconds:.1f}s",
            "",
            f"**Summary:** {o.summary}",
            "",
        ]
        if o.findings:
            lines.append("**Findings:**")
            lines.extend(f"- {f}" for f in o.findings)
            lines.append("")
        if o.artifacts_changed:
            lines.append("**Artifacts Changed:**")
            lines.extend(f"- `{a}`" for a in o.artifacts_changed)
            lines.append("")
        if o.tests_run:
            lines.append("**Tests Run:**")
            lines.extend(f"- `{t}`" for t in o.tests_run)
            lines.append("")
        if o.notes_for_next_agent:
            lines.append("**Notes for Next Agent:**")
            lines.extend(f"- {n}" for n in o.notes_for_next_agent)
            lines.append("")

    if summary.stop_condition:
        sc = summary.stop_condition
        lines += [
            "## Stop Condition",
            "",
            f"- **Reason:** `{sc.reason}`",
            f"- **Detail:** {sc.detail}",
            "",
        ]

    return "\n".join(lines)
