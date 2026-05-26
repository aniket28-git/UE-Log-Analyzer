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


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("log_file", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option(
    "--output", "-f",
    type=click.Choice(["console", "html", "json"], case_sensitive=False),
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
    "--severity", "-s",
    type=click.Choice(["all", "warning", "error"], case_sensitive=False),
    default="all", show_default=True,
    help="Minimum severity level to include (all / warning / error).",
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
    type=float, default=33.0, show_default=True, metavar="MS",
    help="Frame hitch threshold in milliseconds.",
)
@click.option(
    "--shader-threshold",
    type=int, default=1000, show_default=True, metavar="MS",
    help="Slow shader compile threshold in milliseconds.",
)
def analyze(
    log_file: str,
    output: str,
    out_file: str | None,
    severity: str,
    category: tuple[str, ...],
    since: str | None,
    until: str | None,
    hitch_threshold: float,
    shader_threshold: int,
) -> None:
    """Analyze an Unreal Engine log file and report every finding.

    LOG_FILE is the path to a .log file produced by UE4/UE5.

    Examples:

    \b
      ue-log-analyzer MyProject.log
      ue-log-analyzer MyProject.log --output html -o report.html
      ue-log-analyzer MyProject.log --severity error
      ue-log-analyzer MyProject.log --category LogEngine --category LogNet
      ue-log-analyzer MyProject.log --since 12:00:00 --until 12:05:00
    """
    err_console = Console(stderr=True)
    path = Path(log_file)

    # ── Parse with progress bar ───────────────────────────────────────────────
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

    # ── Validate timestamp args ───────────────────────────────────────────────
    since_dt = _require_ts(since, "--since", err_console)
    until_dt = _require_ts(until, "--until", err_console)

    # ── Filter ────────────────────────────────────────────────────────────────
    opts = FilterOptions(
        min_severity=severity,
        categories=list(category) if category else None,
        since=since_dt,
        until=until_dt,
    )
    filtered = apply_filters(result, opts)

    if opts.categories or opts.min_severity != "all" or since_dt or until_dt:
        err_console.print(
            f"[dim]After filters: [bold]{len(filtered.entries):,}[/] entries[/dim]"
        )

    # ── Analyze ───────────────────────────────────────────────────────────────
    from .analyzers.shaders import ShaderAnalyzer
    from .analyzers.performance import PerformanceAnalyzer
    from .analyzers.crash import CrashAnalyzer
    from .analyzers.errors import ErrorAnalyzer
    from .analyzers.assets import AssetAnalyzer
    from .analyzers.network import NetworkAnalyzer
    from .analyzers.timeline import TimelineBuilder
    from .analyzers.results import AnalysisReport

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

    # ── Render ────────────────────────────────────────────────────────────────
    filename = path.name
    output = output.lower()

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


# ── helpers ───────────────────────────────────────────────────────────────────

def _count_lines(path: Path) -> int:
    """Fast approximate line count via byte scan."""
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
    analyze()
