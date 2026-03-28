"""Typer CLI for vguild."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from vguild import __version__
from vguild.config import GatingConfig
from vguild.deploy import deploy_agent, deploy_orchestrator, deploy_orchestrator_with_agents
from vguild.logging_utils import setup_logging
from vguild.models import AgentOutcome, Document, RunSummary
from vguild.orchestrators.base import OrchestratorRunner
from vguild.registry import Registry
from vguild.run_store import RunStore
from vguild.sdk_adapter import SDKAdapter

console = Console()
err = Console(stderr=True)

# ---------------------------------------------------------------------------
# App + sub-apps
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="vguild",
    help="[bold]vguild[/bold] — agent guild system for collaborative software task solving.",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
)

agents_app = typer.Typer(
    help="List, inspect, validate, and run individual agents.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
orchestrators_app = typer.Typer(
    help="List, inspect, and run orchestrator pipelines.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
deploy_app = typer.Typer(
    help="Deploy agents and orchestrators into a target workspace.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
eval_app = typer.Typer(
    help="Run named evaluations.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

app.add_typer(agents_app, name="agents")
app.add_typer(orchestrators_app, name="orchestrators")
app.add_typer(deploy_app, name="deploy")
app.add_typer(eval_app, name="eval")

# ---------------------------------------------------------------------------
# Shared options (reused across commands)
# ---------------------------------------------------------------------------

_CATALOG_OPT = Annotated[
    Path | None,
    typer.Option("--catalog", help="Path to catalog directory (default: ./catalog)"),
]
_RUNS_OPT = Annotated[
    Path,
    typer.Option("--runs-dir", help="Path to runs storage directory (default: ./runs)"),
]
_API_KEY_OPT = Annotated[
    str | None,
    typer.Option("--api-key", envvar="ANTHROPIC_API_KEY", help="Anthropic API key"),
]
_VERBOSE_OPT = Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging")]
_DRY_RUN_OPT = Annotated[bool, typer.Option("--dry-run", help="Simulate without calling the API")]
_JSON_OPT = Annotated[bool, typer.Option("--json", help="Output results as JSON")]
_DOC_OPT = Annotated[
    list[str] | None,
    typer.Option(
        "--doc",
        "-d",
        help='Attach a document: path [or path:label="Label"]. Use "-" for stdin.',
    ),
]

_MAX_DOC_SIZE = 100_000  # characters per document (~25K tokens)
_MAX_TOTAL_DOC_SIZE = 300_000  # total across all documents

_EXTENSION_CONTENT_TYPES: dict[str, str] = {
    ".md": "text/markdown",
    ".json": "application/json",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".txt": "text/plain",
    ".py": "text/x-python",
}

_doc_logger = logging.getLogger(__name__)


def _load_documents(doc_args: list[str] | None) -> list[Document]:
    """Parse --doc arguments into Document objects."""
    if not doc_args:
        return []

    documents: list[Document] = []
    total_size = 0
    for raw in doc_args:
        label, source, content, truncated = _parse_doc_arg(raw)

        remaining = _MAX_TOTAL_DOC_SIZE - total_size
        if remaining <= 0:
            _doc_logger.warning("Document budget exhausted, skipping: %s", label)
            continue
        if len(content) > remaining:
            content = content[:remaining] + "\n\n[... truncated (budget) ...]"
            truncated = True

        total_size += len(content)
        content_type = _guess_content_type(source)
        documents.append(
            Document(
                label=label,
                source=source,
                content=content,
                content_type=content_type,
                truncated=truncated,
            )
        )
    return documents


def _parse_doc_arg(raw: str) -> tuple[str, str, str, bool]:
    """Parse a single --doc argument. Returns (label, source, content, truncated)."""
    label_override: str | None = None
    match = re.match(r'^(.*?):label="(.*)"$', raw)
    if match:
        raw = match.group(1)
        label_override = match.group(2)

    if raw == "-":
        content = sys.stdin.read()
        source = "inline"
        label = label_override or "stdin"
    else:
        path = Path(raw)
        if not path.exists():
            raise typer.BadParameter(f"Document not found: {raw}")
        content = path.read_text(encoding="utf-8")
        source = str(path.resolve())
        label = label_override or path.stem

    truncated = False
    if len(content) > _MAX_DOC_SIZE:
        content = content[:_MAX_DOC_SIZE] + "\n\n[... truncated ...]"
        truncated = True

    return label, source, content, truncated


def _guess_content_type(source: str) -> str:
    """Infer content type from file extension."""
    if source == "inline":
        return "text/plain"
    suffix = Path(source).suffix.lower()
    return _EXTENSION_CONTENT_TYPES.get(suffix, "text/plain")


# ---------------------------------------------------------------------------
# agents commands
# ---------------------------------------------------------------------------


@agents_app.command("list")
def agents_list(
    catalog: _CATALOG_OPT = None,
    output_json: _JSON_OPT = False,
) -> None:
    """List all agents in the catalog."""
    registry = _registry(catalog)
    agents = registry.load_agents()

    if output_json:
        data = [
            {
                "name": a.name,
                "description": a.description,
                "model": a.model,
                "tools": a.tools,
                "tags": a.tags,
                "max_turns": a.max_turns,
            }
            for a in agents.values()
        ]
        console.print_json(json.dumps(data))
        return

    table = Table(title="Guild Agents", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Model", style="dim")
    table.add_column("Tools", style="dim")
    table.add_column("Tags", style="dim")

    for agent in sorted(agents.values(), key=lambda a: a.name):
        table.add_row(
            agent.name,
            agent.description,
            agent.model,
            ", ".join(agent.tools) or "—",
            ", ".join(agent.tags) or "—",
        )

    console.print(table)


@agents_app.command("show")
def agents_show(
    name: Annotated[str, typer.Argument(help="Agent name")],
    catalog: _CATALOG_OPT = None,
) -> None:
    """Show full details for a specific agent."""
    registry = _registry(catalog)
    try:
        agent = registry.get_agent(name)
    except KeyError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(Panel(f"[bold cyan]{agent.name}[/bold cyan]", expand=False))
    console.print(f"[bold]Description:[/bold] {agent.description}")
    console.print(f"[bold]Model:[/bold]       {agent.model}")
    console.print(f"[bold]Max turns:[/bold]   {agent.max_turns}")
    console.print(f"[bold]Tools:[/bold]       {', '.join(agent.tools) or '—'}")
    console.print(f"[bold]Tags:[/bold]        {', '.join(agent.tags) or '—'}")
    console.print()
    console.print("[bold]System Prompt:[/bold]")
    console.print(Syntax(agent.system_prompt, "markdown", theme="monokai", word_wrap=True))


@agents_app.command("validate")
def agents_validate(
    catalog: _CATALOG_OPT = None,
    output_json: _JSON_OPT = False,
) -> None:
    """Validate all catalog entries for structural correctness."""
    registry = _registry(catalog)
    errors = registry.validate_all()

    if output_json:
        console.print_json(json.dumps({"errors": errors, "ok": len(errors) == 0}))
        return

    if errors:
        err.print(f"[red]Found {len(errors)} validation error(s):[/red]")
        for e in errors:
            err.print(f"  [red]✗[/red] {e}")
        raise typer.Exit(1)

    agents = registry.load_agents()
    orchestrators = registry.load_orchestrators()
    console.print(
        f"[green]✓[/green] All catalog entries valid — "
        f"{len(agents)} agents, {len(orchestrators)} orchestrators"
    )


@agents_app.command("run")
def agents_run(
    name: Annotated[str, typer.Argument(help="Agent name")],
    task: Annotated[str, typer.Option("--task", "-t", help="Task description")],
    doc: _DOC_OPT = None,
    catalog: _CATALOG_OPT = None,
    runs_dir: _RUNS_OPT = Path("runs"),
    api_key: _API_KEY_OPT = None,
    dry_run: _DRY_RUN_OPT = False,
    output_json: _JSON_OPT = False,
    verbose: _VERBOSE_OPT = False,
) -> None:
    """Run a single agent for a task and print its outcome.

    Example:
      vguild agents run planner --task "Analyse the auth regression in PR #42"
    """
    setup_logging(verbose)
    registry = _registry(catalog)
    adapter = SDKAdapter(api_key=api_key, dry_run=dry_run)

    try:
        agent_def = registry.get_agent(name)
    except KeyError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    documents = _load_documents(doc)

    try:
        outcome = adapter.run_agent(agent_def, task, documents=documents or None)
    except Exception as exc:
        err.print(f"[red]Agent failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    if output_json:
        console.print_json(outcome.model_dump_json(indent=2))
    else:
        _print_outcome(outcome)


# ---------------------------------------------------------------------------
# orchestrators commands
# ---------------------------------------------------------------------------


@orchestrators_app.command("list")
def orchestrators_list(
    catalog: _CATALOG_OPT = None,
    output_json: _JSON_OPT = False,
) -> None:
    """List all orchestrators in the catalog."""
    registry = _registry(catalog)
    orchestrators = registry.load_orchestrators()

    if output_json:
        data = [
            {
                "name": o.name,
                "description": o.description,
                "entry_agent": o.entry_agent,
                "terminal_agents": o.terminal_agents,
                "quality_threshold": o.quality_threshold,
                "max_rounds": o.max_rounds,
            }
            for o in orchestrators.values()
        ]
        console.print_json(json.dumps(data))
        return

    table = Table(title="Guild Orchestrators", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="magenta")
    table.add_column("Description")
    table.add_column("Entry Agent", style="cyan")
    table.add_column("Terminal Agent(s)", style="cyan")
    table.add_column("Q Threshold", justify="right")
    table.add_column("Max Rounds", justify="right")

    for orch in sorted(orchestrators.values(), key=lambda o: o.name):
        table.add_row(
            orch.name,
            orch.description,
            orch.entry_agent,
            ", ".join(orch.terminal_agents),
            str(orch.quality_threshold),
            str(orch.max_rounds),
        )

    console.print(table)


@orchestrators_app.command("show")
def orchestrators_show(
    name: Annotated[str, typer.Argument(help="Orchestrator name")],
    catalog: _CATALOG_OPT = None,
) -> None:
    """Show full pipeline details for an orchestrator."""
    registry = _registry(catalog)
    try:
        orch = registry.get_orchestrator(name)
    except KeyError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(Panel(f"[bold magenta]{orch.name}[/bold magenta]", expand=False))
    console.print(f"[bold]Description:[/bold]       {orch.description}")
    console.print(f"[bold]Entry agent:[/bold]       {orch.entry_agent}")
    console.print(f"[bold]Terminal agents:[/bold]   {', '.join(orch.terminal_agents)}")
    console.print(f"[bold]Quality threshold:[/bold] {orch.quality_threshold}/10")
    console.print(f"[bold]Max rounds:[/bold]        {orch.max_rounds}")
    console.print(f"[bold]Max no-progress:[/bold]   {orch.max_no_progress}")
    console.print()

    if orch.allowed_handoffs:
        console.print("[bold]Allowed Handoffs:[/bold]")
        for from_agent, targets in orch.allowed_handoffs.items():
            console.print(f"  {from_agent} → {', '.join(targets)}")

    if orch.system_prompt:
        console.print()
        console.print("[bold]Orchestrator Context:[/bold]")
        console.print(Syntax(orch.system_prompt, "markdown", theme="monokai", word_wrap=True))


@orchestrators_app.command("run")
def orchestrators_run(
    name: Annotated[str, typer.Argument(help="Orchestrator name")],
    task: Annotated[
        str | None, typer.Option("--task", "-t", help="Task description (inline)")
    ] = None,
    task_file: Annotated[
        Path | None, typer.Option("--task-file", "-f", help="Path to task Markdown file")
    ] = None,
    doc: _DOC_OPT = None,
    catalog: _CATALOG_OPT = None,
    runs_dir: _RUNS_OPT = Path("runs"),
    api_key: _API_KEY_OPT = None,
    min_quality: Annotated[
        int, typer.Option("--min-quality", min=0, max=10, help="Override quality threshold")
    ] = 8,
    max_rounds: Annotated[
        int, typer.Option("--max-rounds", min=1, help="Override max rounds")
    ] = 10,
    max_no_progress: Annotated[
        int, typer.Option("--max-no-progress", min=1, help="Override max no-progress rounds")
    ] = 2,
    fail_on_blocked: Annotated[
        bool, typer.Option("--fail-on-blocked/--no-fail-on-blocked")
    ] = False,
    dry_run: _DRY_RUN_OPT = False,
    output_json: _JSON_OPT = False,
    verbose: _VERBOSE_OPT = False,
) -> None:
    """Run an orchestrator pipeline for a task.

    Examples:
      vguild orchestrators run hotfix --task "Fix NullPointerException in auth.login()"
      vguild orchestrators run new-feature --task-file examples/tasks/feature.md --dry-run
      vguild orchestrators run hotfix --task "..." --min-quality 9 --max-rounds 5
    """
    setup_logging(verbose)

    if not task and not task_file:
        err.print("[red]Error:[/red] Provide --task or --task-file")
        raise typer.Exit(1)

    task_text = task_file.read_text(encoding="utf-8") if task_file else task
    assert task_text  # narrowed above

    config = GatingConfig(
        min_quality=min_quality,
        max_rounds=max_rounds,
        max_no_progress=max_no_progress,
        fail_on_blocked=fail_on_blocked,
    )

    registry = _registry(catalog)
    adapter = SDKAdapter(api_key=api_key, dry_run=dry_run)
    store = RunStore(runs_dir)

    try:
        orchestrator = registry.get_orchestrator(name)
    except KeyError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    runner = OrchestratorRunner(
        orchestrator=orchestrator,
        registry=registry,
        adapter=adapter,
        store=store,
        config=config,
    )

    documents = _load_documents(doc)

    summary = runner.run(task_text, documents=documents or None)

    if output_json:
        console.print_json(summary.model_dump_json(indent=2))
    else:
        _print_run_summary(summary)

    if summary.final_status not in {"success"}:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# deploy commands
# ---------------------------------------------------------------------------


@deploy_app.command("agent")
def deploy_agent_cmd(
    name: Annotated[str, typer.Argument(help="Agent name to deploy")],
    workspace: Annotated[
        Path,
        typer.Option("--workspace", "-w", help="Target workspace directory"),
    ] = Path("."),
    catalog: _CATALOG_OPT = None,
    symlink: Annotated[
        bool, typer.Option("--symlink/--copy", help="Symlink instead of copy")
    ] = False,
) -> None:
    """Deploy an agent prompt to <workspace>/.claude/agents/.

    Example:
      vguild deploy agent planner --workspace ../my-project
    """
    registry = _registry(catalog)
    try:
        dest = deploy_agent(name, workspace, registry, symlink=symlink)
        action = "Symlinked" if symlink else "Copied"
        console.print(f"[green]✓[/green] {action} agent [cyan]{name}[/cyan] → {dest}")
    except KeyError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


@deploy_app.command("orchestrator")
def deploy_orchestrator_cmd(
    name: Annotated[str, typer.Argument(help="Orchestrator name to deploy")],
    workspace: Annotated[
        Path,
        typer.Option("--workspace", "-w", help="Target workspace directory"),
    ] = Path("."),
    catalog: _CATALOG_OPT = None,
    with_agents: Annotated[
        bool,
        typer.Option("--with-agents/--orchestrator-only", help="Also deploy all referenced agents"),
    ] = True,
    symlink: Annotated[
        bool, typer.Option("--symlink/--copy", help="Symlink instead of copy")
    ] = False,
) -> None:
    """Deploy an orchestrator (and its agents) to a workspace.

    Example:
      vguild deploy orchestrator hotfix --workspace ../my-project --with-agents
    """
    registry = _registry(catalog)
    try:
        if with_agents:
            deployed = deploy_orchestrator_with_agents(name, workspace, registry, symlink=symlink)
            action = "Symlinked" if symlink else "Deployed"
            for resource, path in deployed.items():
                console.print(f"[green]✓[/green] {action} [cyan]{resource}[/cyan] → {path}")
        else:
            dest = deploy_orchestrator(name, workspace, registry, symlink=symlink)
            action = "Symlinked" if symlink else "Copied"
            console.print(f"[green]✓[/green] {action} orchestrator [cyan]{name}[/cyan] → {dest}")
    except KeyError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# eval commands
# ---------------------------------------------------------------------------


@eval_app.command("run")
def eval_run(
    name: Annotated[str, typer.Argument(help="Evaluation name (e.g. hotfix-happy-path)")],
    catalog: _CATALOG_OPT = None,
    runs_dir: _RUNS_OPT = Path("runs"),
    api_key: _API_KEY_OPT = None,
    verbose: _VERBOSE_OPT = False,
) -> None:
    """Run a named evaluation scenario.

    Evaluation scenarios live in examples/evals/ as Markdown files.

    Example:
      vguild eval run hotfix-happy-path
    """
    setup_logging(verbose)
    eval_file = Path("examples") / "evals" / f"{name}.md"
    if not eval_file.exists():
        err.print(f"[red]Error:[/red] Evaluation file not found: {eval_file}")
        raise typer.Exit(1)

    content = eval_file.read_text(encoding="utf-8")
    # Eval files follow the same format as task files and specify the orchestrator
    # in a YAML frontmatter field "orchestrator"
    from vguild.prompt_loader import parse_frontmatter

    metadata, task_body = parse_frontmatter(content)
    orchestrator_name = metadata.get("orchestrator")
    if not orchestrator_name:
        err.print("[red]Error:[/red] Eval file must have 'orchestrator' in frontmatter")
        raise typer.Exit(1)

    registry = _registry(catalog)
    adapter = SDKAdapter(api_key=api_key, dry_run=False)
    store = RunStore(runs_dir)

    try:
        orchestrator = registry.get_orchestrator(orchestrator_name)
    except KeyError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    quality_threshold = int(metadata.get("quality_threshold", orchestrator.quality_threshold))
    config = GatingConfig(min_quality=quality_threshold)

    runner = OrchestratorRunner(
        orchestrator=orchestrator,
        registry=registry,
        adapter=adapter,
        store=store,
        config=config,
    )
    summary = runner.run(task_body)
    _print_run_summary(summary)

    if summary.final_status != "success":
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


@app.command()
def doctor(
    catalog: _CATALOG_OPT = None,
) -> None:
    """Check system health: Python version, API key, and catalog validity."""
    ok = True

    # Python version
    py_ver = sys.version.split()[0]
    min_version = (3, 11)
    if sys.version_info >= min_version:
        console.print(f"[green]✓[/green] Python {py_ver} (≥3.11 required)")
    else:
        console.print(f"[red]✗[/red] Python {py_ver} — requires ≥3.11")
        ok = False

    # API key
    if os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[green]✓[/green] ANTHROPIC_API_KEY is set")
    else:
        console.print("[yellow]⚠[/yellow] ANTHROPIC_API_KEY is not set (required for real runs)")

    # Catalog validation
    registry = _registry(catalog)
    errors = registry.validate_all()
    if errors:
        for e in errors:
            console.print(f"[red]✗[/red] {e}")
        ok = False
    else:
        agents = registry.load_agents()
        orchestrators = registry.load_orchestrators()
        console.print(
            f"[green]✓[/green] Catalog valid — "
            f"{len(agents)} agents, {len(orchestrators)} orchestrators "
            f"(at {registry.catalog_dir})"
        )

    # Catalog directory
    if not registry.catalog_dir.exists():
        console.print(f"[red]✗[/red] Catalog directory not found: {registry.catalog_dir}")
        ok = False

    if not ok:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


@app.command()
def version() -> None:
    """Print the vguild version."""
    console.print(f"vguild {__version__}")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _registry(catalog: Path | None) -> Registry:
    return Registry(catalog_dir=catalog)


def _print_outcome(outcome: AgentOutcome) -> None:

    status_color = {
        "pass": "green",
        "revise": "yellow",
        "blocked": "red",
        "stop": "red bold",
    }.get(outcome.status, "white")

    console.print(
        Panel(
            f"[{status_color}]{outcome.status.upper()}[/{status_color}] — "
            f"Q:{outcome.quality_score}/10  C:{outcome.confidence_score}/10",
            title=f"[cyan]{outcome.agent_name}[/cyan]",
            expand=False,
        )
    )
    console.print(f"\n[bold]Summary:[/bold] {outcome.summary}\n")

    if outcome.findings:
        console.print("[bold]Findings:[/bold]")
        for f in outcome.findings:
            console.print(f"  • {f}")

    if outcome.artifacts_changed:
        console.print("\n[bold]Artifacts changed:[/bold]")
        for a in outcome.artifacts_changed:
            console.print(f"  • [dim]{a}[/dim]")

    if outcome.notes_for_next_agent:
        console.print("\n[bold]Notes for next agent:[/bold]")
        for n in outcome.notes_for_next_agent:
            console.print(f"  → {n}")

    if outcome.needs_human:
        console.print("\n[red bold]⚠ Human intervention required[/red bold]")

    if outcome.recommended_next_agent:
        console.print(f"\n[dim]Recommended next: {outcome.recommended_next_agent}[/dim]")


def _print_run_summary(summary: RunSummary) -> None:

    status_color = "green" if summary.final_status == "success" else "red"
    duration = (summary.ended_at - summary.started_at).total_seconds()

    console.print()
    console.print(
        Panel(
            f"[{status_color}]{summary.final_status.upper()}[/{status_color}]  "
            f"[dim]{duration:.1f}s  {len(summary.steps)} steps[/dim]",
            title=f"[bold magenta]{summary.orchestrator_name}[/bold magenta]  "
            f"[dim]{summary.run_id}[/dim]",
            expand=False,
        )
    )

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("#", style="dim", width=3)
    table.add_column("Agent", style="cyan")
    table.add_column("Status")
    table.add_column("Q", justify="right")
    table.add_column("C", justify="right")
    table.add_column("Gate")
    table.add_column("Duration", justify="right", style="dim")

    for step in summary.steps:
        o = step.outcome
        g = step.gate_decision
        status_c = {"pass": "green", "revise": "yellow", "blocked": "red", "stop": "red"}.get(
            o.status, "white"
        )
        gate_text = Text("✓ pass" if g.passed else "✗ fail", style="green" if g.passed else "red")
        table.add_row(
            str(step.step_number),
            step.agent_name,
            Text(o.status, style=status_c),
            str(o.quality_score),
            str(o.confidence_score),
            gate_text,
            f"{step.duration_seconds:.1f}s",
        )

    console.print(table)

    if summary.stop_condition:
        sc = summary.stop_condition
        color = "green" if sc.reason == "terminal_agent_passed" else "yellow"
        console.print(f"\n[{color}]Stop:[/{color}] [{color}]{sc.reason}[/{color}] — {sc.detail}")

    console.print(f"\n[dim]Run artifacts saved to: runs/{summary.run_id}/[/dim]")
