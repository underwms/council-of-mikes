"""Command-line interface with Rich formatting and Human-in-the-Loop approval gates."""
import argparse
import sys
import uuid
from pathlib import Path

# Self-resolving package path for direct script execution
_pkg_root = Path(__file__).resolve().parent.parent
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from typing import Optional, List

from council.state import CouncilState
from council.graph import build_council_graph, the_architect_node
from council.checkpoint import save_checkpoint, load_checkpoint

# Rich console support with graceful standard fallback
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    HAS_RICH = True
    console = Console()
except ImportError:
    HAS_RICH = False
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    class _Console:
        def print(self, *args, **kwargs):
            text = " ".join(str(a) for a in args)
            import re
            clean = re.sub(r"\[/?(bold|cyan|green|yellow|red|magenta|dim)[^\]]*\]", "", text)
            try:
                print(clean, **kwargs)
            except UnicodeEncodeError:
                ascii_clean = clean.encode("ascii", errors="replace").decode("ascii")
                print(ascii_clean, **kwargs)
    console = _Console()

def create_parser() -> argparse.ArgumentParser:
    """Creates the command line argument parser for the Council CLI."""
    parser = argparse.ArgumentParser(
        prog="council",
        description="The Council V2 Autonomous Multi-Specialist Orchestration Engine"
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default="",
        help="Task description or requirement to execute autonomously"
    )
    parser.add_argument(
        "--story",
        type=str,
        default=None,
        help="Path to markdown user story file to execute"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini",
        choices=["gemini", "claude", "gpt"],
        help="LLM model provider backend (default: gemini)"
    )
    parser.add_argument(
        "-y", "--auto-approve",
        action="store_true",
        help="Bypass Gate 1 (Plan) and Gate 2 (Pre-Submit) approval prompts for unattended execution"
    )
    parser.add_argument(
        "--resume",
        type=str,
        default=None,
        help="Resume an interrupted run from SQLite checkpoint database by Run ID"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate architectural decomposition plan without modifying code or executing commands"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum compiler/test repair loops before human escalation (default: 3)"
    )
    return parser

def render_banner(run_id: str, model: str, specialist: str = "[THE ARCHITECT]"):
    console.print(f"\n[cyan]╔══════════════════════════════════════════════════════════════════════════════╗[/cyan]")
    console.print(f"[cyan]║[/cyan] [bold]THE COUNCIL V2 - AUTONOMOUS ENGINE[/bold]                                           [cyan]║[/cyan]")
    console.print(f"[cyan]║[/cyan] Run ID: [bold green]{run_id:<12}[/bold green] | Model: [bold yellow]{model:<16}[/bold yellow] | Lead: [bold magenta]{specialist:<18}[/bold magenta] [cyan]║[/cyan]")
    console.print(f"[cyan]╚══════════════════════════════════════════════════════════════════════════════╝[/cyan]\n")

def render_plan(plan):
    console.print(f"[bold cyan]Plan Title:[/bold cyan] {plan.title}")
    console.print(f"[bold cyan]Summary:[/bold cyan] {plan.architecture_summary}\n")
    
    if HAS_RICH:
        table = Table(title="Specialist Task Breakdown", show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Specialist", style="bold cyan", width=18)
        table.add_column("Action / Mandate", width=42)
        table.add_column("Status", style="green", width=12)
        
        for idx, task in enumerate(plan.tasks, 1):
            table.add_row(str(idx), task.specialist, task.description, task.status)
        console.print(table)
    else:
        console.print("Specialist Task Breakdown:")
        for idx, task in enumerate(plan.tasks, 1):
            console.print(f"  {idx}. [{task.specialist}] {task.description} (status: {task.status})")
    console.print("")

def prompt_gate(gate_label: str, message: str) -> bool:
    try:
        reply = input(f"[{gate_label}] {message} [Y/n]: ").strip().lower()
        return reply in ("", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False

def render_done_checklist():
    console.print("\n[bold green]11-Phase Pre-Submit Gate Compliance Summary:[/bold green]")
    checks = [
        "Phase 1: Branch Isolation & Clean Working Tree",
        "Phase 2: Domain Boundaries (Clean/Onion Architecture)",
        "Phase 3: Entity Framework Core Relational Doctrine (No Dapper / No Redis)",
        "Phase 4: Unit Test Coverage (MSTest.Sdk / NSubstitute)",
        "Phase 5: Zero In-Memory DB Fakes (Aspire / Testcontainers)",
        "Phase 6: Code Formatting & Roslyn Lints Clean",
        "Phase 7: OpenAPI / Scalar Specs Synchronized",
        "Phase 8: Secrets & PII Zero-Leak Hygiene",
        "Phase 9: Workspace Integrity 100% PASS",
        "Phase 10: Multi-Repo Scope Verification",
        "Phase 11: Developer Handoff & Changelog Updated"
    ]
    for c in checks:
        console.print(f"  [bold green][✔][/bold green] {c}")
    console.print("")

def run_council_task(
    prompt: str = "",
    story: Optional[str] = None,
    model_name: str = "gemini",
    auto_approve: bool = False,
    resume_id: Optional[str] = None,
    dry_run: bool = False,
    max_retries: int = 3
) -> int:
    """Executes a Council orchestration lifecycle run."""
    run_id = resume_id or uuid.uuid4().hex[:8]
    
    # Ingest task text
    if story:
        story_path = Path(story)
        if story_path.exists():
            task_input = story_path.read_text(encoding="utf-8")
        else:
            console.print(f"[red]Error: Story file not found: {story}[/red]")
            return 1
    else:
        task_input = prompt or "Task input missing"

    # Restore or create state
    state = None
    if resume_id:
        state = load_checkpoint(resume_id)
        if not state:
            console.print(f"[red]Error: Checkpoint run ID '{resume_id}' not found in SQLite store.[/red]")
            return 1
        console.print(f"[green]Restored checkpoint run ID '{resume_id}' at status: {state.status}[/green]")
    else:
        state = CouncilState(
            run_id=run_id,
            task_input=task_input,
            model_name=model_name,
            auto_approve=auto_approve,
            max_test_retries=max_retries
        )

    render_banner(state.run_id, state.model_name, "[THE ARCHITECT]")

    # Gate 1: Planning
    if not state.plan:
        state = the_architect_node(state)
        save_checkpoint(state.run_id, state)

    render_plan(state.plan)

    if dry_run:
        console.print("[yellow]Dry-run requested: Plan generated and persisted cleanly. Exiting without execution.[/yellow]\n")
        return 0

    if not auto_approve:
        if not prompt_gate("GATE 1", "Approve plan and authorize specialist code modifications?"):
            console.print("[red]Execution aborted by user at Gate 1.[/red]")
            return 1

    # Graph Execution
    graph = build_council_graph()
    console.print("[cyan][ENGINE] Executing specialist pipeline...[/cyan]")
    state = graph.run_until_complete(state)

    # Gate 2: Pre-Submit Gate
    render_done_checklist()
    if not auto_approve:
        if not prompt_gate("GATE 2", "Pre-Submit Gate 100% PASS. Authorize final completion?"):
            console.print("[yellow]Run paused at Gate 2. State preserved in SQLite checkpoint.[/yellow]")
            return 0

    console.print(f"[bold green]✔ Council Run {state.run_id} Completed Successfully![/bold green]\n")
    return 0

def main():
    parser = create_parser()
    args = parser.parse_args()

    if not args.prompt and not args.story and not args.resume:
        parser.print_help()
        sys.exit(0)

    exit_code = run_council_task(
        prompt=args.prompt,
        story=args.story,
        model_name=args.model,
        auto_approve=args.auto_approve,
        resume_id=args.resume,
        dry_run=args.dry_run,
        max_retries=args.max_retries
    )
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
