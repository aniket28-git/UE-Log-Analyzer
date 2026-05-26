from __future__ import annotations
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TaskProgressColumn,
)

from .parser import LogParser
from .filters import FilterOptions, apply_filters, parse_timestamp_arg
from .analyzers.runner import run_all
from .report.console import ConsoleReport
from .report.html import HtmlReport
from .report.json_export import JsonExport
from .config import load_config
from .watcher import poll_until_changed


# ── CLI group ─────────────────────────────────────────────────────────────────

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli():
    """UE Log Analyzer — analyze and diff Unreal Engine log files."""


# ── analyze command ───────────────────────────────────────────────────────────

@cli.command("analyze")
@click.argument("log_file", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option(
    "--output", "-f",
    type=click.Choice(["console", "html", "json"], case_sensitive=False),
    default=None,
    help="Output format (default: config default or console).",
)
@click.option(
    "--out-file", "-o",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Write output to FILE instead of stdout.",
)
@click.option(
    "--severity", "-s",
    type=click.Choice(["all", "warning", "error"], case_sensitive=False),
    default=None,
    help="Minimum severity level (default: config default or all).",
)
@click.option(
    "--category", "-c",
    multiple=True, metavar="CAT",
    help="Show only entries from this log category (repeatable). "
         "E.g. -c LogEngine -c LogNet",
)
@click.option(
    "--since",
    default=None, metavar="TIMESTAMP",
    help="Ignore entries before this time.  "
         "Formats: HH:MM:SS  or  YYYY.MM.DD-HH.MM.SS",
)
@click.option(
    "--until",
    default=None, metavar="TIMESTAMP",
    help="Ignore entries after this time.  "
         "Formats: HH:MM:SS  or  YYYY.MM.DD-HH.MM.SS",
)
@click.option(
    "--hitch-threshold",
    type=float, default=None, metavar="MS",
    help="Frame hitch threshold in milliseconds (default: config or 33).",
)
@click.option(
    "--shader-threshold",
    type=int, default=None, metavar="MS",
    help="Slow shader compile threshold in milliseconds (default: config or 1000).",
)
@click.option(
    "--watch", is_flag=True, default=False,
    help="Re-analyze whenever the file changes. Press Ctrl+C to stop.",
)
def analyze(
    log_file: str,
    output: str | None,
    out_file: str | None,
    severity: str | None,
    category: tuple[str, ...],
    since: str | None,
    until: str | None,
    hitch_threshold: float | None,
    shader_threshold: int | None,
    watch: bool,
) -> None:
    """Analyze an Unreal Engine log file and report every finding.

    LOG_FILE is the path to a .log file produced by UE4/UE5.

    Examples:

    \b
      ue-log-analyzer analyze MyProject.log
      ue-log-analyzer analyze MyProject.log --output html -o report.html
      ue-log-analyzer analyze MyProject.log --severity error
      ue-log-analyzer analyze MyProject.log --category LogEngine --category LogNet
      ue-log-analyzer analyze MyProject.log --since 12:00:00 --until 12:05:00
      ue-log-analyzer analyze MyProject.log --watch
    """
    err_console = Console(stderr=True)
    path = Path(log_file)

    # Load config from the log file's directory (walks up to project root)
    cfg = load_config(path.parent)

    # Resolve effective values: CLI flag > config > built-in default
    effective_output = (output or cfg.default_output).lower()
    effective_severity = (severity or cfg.default_severity).lower()
    effective_hitch = hitch_threshold if hitch_threshold is not None else cfg.hitch_threshold_ms
    effective_shader = shader_threshold if shader_threshold is not None else cfg.shader_threshold_ms

    # Validate timestamp args once (before any loop)
    since_dt = _require_ts(since, "--since", err_console)
    until_dt = _require_ts(until, "--until", err_console)

    opts = FilterOptions(
        min_severity=effective_severity,
        categories=list(category) if category else None,
        since=since_dt,
        until=until_dt,
    )

    def _run_once() -> None:
        report = _build_report(path, opts, effective_hitch, effective_shader, err_console)
        _render(report, path.name, effective_output, out_file, err_console)

    if watch:
        err_console.print("[cyan]Watch mode active — press Ctrl+C to exit[/cyan]")
        _run_once()
        try:
            while True:
                err_console.print("[dim]Watching for changes…[/dim]")
                poll_until_changed(path)
                err_console.clear()
                _run_once()
        except KeyboardInterrupt:
            err_console.print("\n[dim]Watch mode stopped.[/dim]")
    else:
        _run_once()


# ── diff command ──────────────────────────────────────────────────────────────

@cli.command("diff")
@click.argument("log_before", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.argument("log_after", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option(
    "--output", "-f",
    type=click.Choice(["console", "json"], case_sensitive=False),
    default="console", show_default=True,
    help="Output format.",
)
@click.option(
    "--out-file", "-o",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Write output to FILE instead of stdout.",
)
@click.option(
    "--hitch-threshold",
    type=float, default=None, metavar="MS",
    help="Frame hitch threshold in milliseconds (default: config or 33).",
)
@click.option(
    "--shader-threshold",
    type=int, default=None, metavar="MS",
    help="Slow shader compile threshold in milliseconds (default: config or 1000).",
)
def diff_cmd(
    log_before: str,
    log_after: str,
    output: str,
    out_file: str | None,
    hitch_threshold: float | None,
    shader_threshold: int | None,
) -> None:
    """Compare two Unreal Engine logs and surface new issues.

    Shows what changed between LOG_BEFORE and LOG_AFTER: new crashes, errors,
    warnings, asset issues, shader problems, performance events, and network
    events that appear in the after log but not in the before log.

    Examples:

    \b
      ue-log-analyzer diff before.log after.log
      ue-log-analyzer diff before.log after.log --output json -o diff.json
    """
    from .diff import compute_diff
    from .report.diff_console import DiffConsoleReport
    from .report.diff_json import DiffJsonExport

    err_console = Console(stderr=True)
    path_before = Path(log_before)
    path_after = Path(log_after)

    cfg = load_config(path_before.parent)
    effective_hitch = hitch_threshold if hitch_threshold is not None else cfg.hitch_threshold_ms
    effective_shader = shader_threshold if shader_threshold is not None else cfg.shader_threshold_ms

    opts = FilterOptions()

    before_report = _build_report(path_before, opts, effective_hitch, effective_shader, err_console)
    after_report = _build_report(path_after, opts, effective_hitch, effective_shader, err_console)

    diff = compute_diff(before_report, after_report, path_before.name, path_after.name)

    output = output.lower()
    if output == "console":
        if out_file:
            out = Console(file=open(out_file, "w", encoding="utf-8"), no_color=True, highlight=False)
            DiffConsoleReport(out).render(diff)
            err_console.print(f"[green]Diff report saved to[/] {out_file}")
        else:
            DiffConsoleReport().render(diff)
    elif output == "json":
        data = DiffJsonExport().render(diff)
        if out_file:
            Path(out_file).write_text(data, encoding="utf-8")
            err_console.print(f"[green]Diff JSON saved to[/] {out_file}")
        else:
            click.echo(data)

    # Exit with code 1 if regressions were found (useful in CI)
    if diff.has_regressions:
        sys.exit(1)


# ── shared helpers ────────────────────────────────────────────────────────────

def _build_report(
    path: Path,
    opts: FilterOptions,
    hitch_threshold: float,
    shader_threshold: int,
    err_console: Console,
):
    from .analyzers.shaders import ShaderAnalyzer
    from .analyzers.performance import PerformanceAnalyzer
    from .analyzers.crash import CrashAnalyzer
    from .analyzers.errors import ErrorAnalyzer
    from .analyzers.assets import AssetAnalyzer
    from .analyzers.network import NetworkAnalyzer
    from .analyzers.timeline import TimelineBuilder
    from .analyzers.results import AnalysisReport

    total_lines = _count_lines(path)

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]{task.description}"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=err_console,
        transient=True,
    ) as progress:
        task = progress.add_task(f"Parsing {path.name}", total=total_lines or None)

        def _on_line(n: int) -> None:
            progress.update(task, completed=n)

        result = LogParser().parse(path, progress_fn=_on_line)

    err_console.print(
        f"[dim]Parsed [bold]{result.total_lines:,}[/] lines — "
        f"[red]{len(result.errors)}[/] errors, "
        f"[yellow]{len(result.warnings)}[/] warnings, "
        f"[{'red' if result.crash_blocks else 'green'}]"
        f"{'crash detected' if result.crash_blocks else 'no crash'}[/][/dim]"
    )

    filtered = apply_filters(result, opts)

    if opts.categories or opts.min_severity != "all" or opts.since or opts.until:
        err_console.print(
            f"[dim]After filters: [bold]{len(filtered.entries):,}[/] entries[/dim]"
        )

    report = AnalysisReport(
        parse_result=filtered,
        crash=CrashAnalyzer().analyze(filtered),
        errors=ErrorAnalyzer().analyze(filtered),
        assets=AssetAnalyzer().analyze(filtered),
        shaders=ShaderAnalyzer(slow_threshold_ms=shader_threshold).analyze(filtered),
        performance=PerformanceAnalyzer(hitch_threshold_ms=hitch_threshold).analyze(filtered),
        network=NetworkAnalyzer().analyze(filtered),
    )
    report.timeline = TimelineBuilder().build(filtered, report)
    return report


def _render(
    report,
    filename: str,
    output: str,
    out_file: str | None,
    err_console: Console,
) -> None:
    if output == "console":
        if out_file:
            out = Console(file=open(out_file, "w", encoding="utf-8"), no_color=True, highlight=False)
            ConsoleReport(out).render(report, filename)
            err_console.print(f"[green]Report saved to[/] {out_file}")
        else:
            ConsoleReport().render(report, filename)

    elif output == "html":
        html = HtmlReport().render(report, filename)
        if out_file:
            Path(out_file).write_text(html, encoding="utf-8")
            err_console.print(f"[green]HTML report saved to[/] {out_file}")
        else:
            click.echo(html)

    elif output == "json":
        data = JsonExport().render(report, filename)
        if out_file:
            Path(out_file).write_text(data, encoding="utf-8")
            err_console.print(f"[green]JSON saved to[/] {out_file}")
        else:
            click.echo(data)


def _count_lines(path: Path) -> int:
    try:
        with open(path, "rb") as f:
            return f.read().count(b"\n")
    except OSError:
        return 0


def _require_ts(value: str | None, flag: str, console: Console):
    if value is None:
        return None
    dt = parse_timestamp_arg(value)
    if dt is None:
        console.print(f"[red]Error:[/] could not parse {flag} value {value!r}. "
                      "Use HH:MM:SS or YYYY.MM.DD-HH.MM.SS")
        sys.exit(1)
    return dt


if __name__ == "__main__":
    cli()
