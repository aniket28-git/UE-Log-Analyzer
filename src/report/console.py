from __future__ import annotations
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.padding import Padding
from ..analyzers.results import AnalysisReport

_SEV_STYLE = {
    "fatal": "bold red",
    "error": "red",
    "warning": "yellow",
    "info": "dim",
}


class ConsoleReport:
    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def render(self, report: AnalysisReport, filename: str = "") -> None:
        c = self.console
        c.print()
        c.rule(f"[bold cyan]UE LOG ANALYSIS[/]  {filename}", style="cyan")
        c.print()

        self._summary(report)

        if report.has_crash:
            self._crashes(report)

        if report.errors.error_groups:
            self._errors(report)

        if report.errors.warning_groups:
            self._warnings(report)

        if report.assets.issues:
            self._assets(report)

        if report.shaders.issues:
            self._shaders(report)

        if report.performance.events:
            self._performance(report)

        if report.network.events:
            self._network(report)

        self._timeline(report)

    # ── sections ─────────────────────────────────────────────────────────────

    def _summary(self, report: AnalysisReport) -> None:
        c = self.console
        pr = report.parse_result

        grid = Table.grid(padding=(0, 3))
        grid.add_column(style="bold", min_width=22)
        grid.add_column(min_width=10)

        def row(label: str, value: str, style: str = "") -> None:
            grid.add_row(label, Text(value, style=style) if style else value)

        row("Lines parsed:", f"{pr.total_lines:,}")
        row(
            "Crash detected:",
            "YES" if report.has_crash else "NO",
            "bold red" if report.has_crash else "bold green",
        )
        row(
            "Errors:",
            str(report.errors.total_errors),
            "red" if report.errors.total_errors else "green",
        )
        row(
            "Warnings:",
            str(report.errors.total_warnings),
            "yellow" if report.errors.total_warnings else "green",
        )
        row("Asset issues:", str(report.assets.total))
        row("Shader issues:", str(len(report.shaders.issues)))
        row(
            "Hitches (>33 ms):",
            str(report.performance.hitch_count),
            "yellow" if report.performance.hitch_count else "",
        )
        row("GC purges:", str(report.performance.gc_purge_count))
        row("Network events:", str(len(report.network.events)))

        c.print(Panel(grid, title="[bold]SUMMARY[/]", border_style="cyan"))
        c.print()

    def _crashes(self, report: AnalysisReport) -> None:
        c = self.console
        c.rule("[bold red]CRASH[/]", style="red")
        c.print()

        for idx, detail in enumerate(report.crash.details, 1):
            cb = detail.block
            lines: list[str] = []

            lines.append(f"[bold]Line:[/] {cb.line_number}  |  [bold]Frame:[/] {cb.trigger_entry.frame}")
            lines.append(f"[bold red]{cb.summary}[/]")

            if detail.exception_type:
                lines.append(f"\n[bold]Exception type:[/] {detail.exception_type}")
            if detail.source_file:
                lines.append(f"[bold]Source:[/] {detail.source_file}:{detail.source_line}")

            if cb.context_before:
                lines.append("\n[bold dim]--- context before ---[/]")
                for e in cb.context_before[-5:]:
                    lines.append(f"  [dim]L{e.line_number:>6}[/]  {e.message[:100]}")

            if cb.callstack_lines:
                lines.append("\n[bold dim]--- callstack ---[/]")
                for cs in cb.callstack_lines[:25]:
                    if cs.strip():
                        lines.append(f"  [dim]{cs}[/]")

            if cb.context_after:
                lines.append("\n[bold dim]--- context after ---[/]")
                for e in cb.context_after[:5]:
                    if hasattr(e, "message"):
                        lines.append(f"  [dim]L{e.line_number:>6}[/]  {e.message[:100]}")

            c.print(Panel(
                "\n".join(lines),
                title=f"[bold red]CRASH #{idx}[/]",
                border_style="red",
            ))
            c.print()

    def _errors(self, report: AnalysisReport) -> None:
        c = self.console
        c.rule("[red]ERRORS[/]", style="red")
        t = _make_group_table("bold red")
        for g in report.errors.error_groups[:10]:
            t.add_row(str(g.count), g.category, g.template[:90], str(g.first_line))
        c.print(t)
        c.print()

    def _warnings(self, report: AnalysisReport) -> None:
        c = self.console
        c.rule("[yellow]WARNINGS[/]", style="yellow")
        t = _make_group_table("bold yellow")
        for g in report.errors.warning_groups[:10]:
            t.add_row(str(g.count), g.category, g.template[:90], str(g.first_line))
        c.print(t)
        c.print()

    def _assets(self, report: AnalysisReport) -> None:
        c = self.console
        c.rule("[yellow]ASSET ISSUES[/]", style="yellow")
        t = Table(show_header=True, header_style="bold", border_style="dim")
        t.add_column("Kind", width=14)
        t.add_column("Asset Path")
        t.add_column("Line", justify="right", width=7)
        for issue in report.assets.issues:
            sty = "red" if issue.kind in ("load_failure", "cook_error") else "yellow"
            t.add_row(Text(issue.kind, style=sty), issue.asset_path[:80], str(issue.entry.line_number))
        c.print(t)
        c.print()

    def _shaders(self, report: AnalysisReport) -> None:
        c = self.console
        c.rule("[yellow]SHADER ISSUES[/]", style="yellow")
        t = Table(show_header=True, header_style="bold", border_style="dim")
        t.add_column("Kind", width=14)
        t.add_column("Message")
        t.add_column("ms", justify="right", width=8)
        t.add_column("Line", justify="right", width=7)
        for issue in report.shaders.issues:
            sty = "red" if issue.kind == "compile_error" else "yellow"
            t.add_row(
                Text(issue.kind, style=sty),
                issue.message[:70],
                str(issue.compile_time_ms) if issue.compile_time_ms else "-",
                str(issue.entry.line_number),
            )
        c.print(t)
        c.print()

    def _performance(self, report: AnalysisReport) -> None:
        c = self.console
        c.rule("[yellow]PERFORMANCE[/]", style="yellow")
        t = Table(show_header=True, header_style="bold", border_style="dim")
        t.add_column("Kind", width=16)
        t.add_column("Description")
        t.add_column("ms", justify="right", width=8)
        t.add_column("Line", justify="right", width=7)
        for ev in report.performance.events:
            sty = "red" if ev.kind == "oom_warning" else "yellow"
            t.add_row(
                Text(ev.kind, style=sty),
                ev.description[:70],
                f"{ev.value_ms:.1f}" if ev.value_ms is not None else "-",
                str(ev.entry.line_number),
            )
        c.print(t)
        c.print()

    def _network(self, report: AnalysisReport) -> None:
        c = self.console
        c.rule("[yellow]NETWORK[/]", style="yellow")
        t = Table(show_header=True, header_style="bold", border_style="dim")
        t.add_column("Kind", width=16)
        t.add_column("Description")
        t.add_column("Line", justify="right", width=7)
        for ev in report.network.events:
            sty = "red" if ev.kind == "error" else "yellow"
            t.add_row(Text(ev.kind, style=sty), ev.description[:80], str(ev.entry.line_number))
        c.print(t)
        c.print()

    def _timeline(self, report: AnalysisReport) -> None:
        c = self.console
        c.rule("[bold cyan]TIMELINE[/]", style="cyan")
        t = Table(show_header=True, header_style="bold cyan", border_style="dim")
        t.add_column("Line", justify="right", width=7)
        t.add_column("Severity", width=9)
        t.add_column("Kind", width=20)
        t.add_column("Description")
        for ev in report.timeline:
            sty = _SEV_STYLE.get(ev.severity, "")
            t.add_row(
                str(ev.line_number),
                Text(ev.severity.upper(), style=sty),
                ev.kind,
                ev.description[:80],
                style=sty,
            )
        c.print(t)
        c.print()


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_group_table(header_style: str) -> Table:
    t = Table(show_header=True, header_style=header_style, border_style="dim")
    t.add_column("Count", justify="right", width=6)
    t.add_column("Category", width=26)
    t.add_column("Message Template")
    t.add_column("First line", justify="right", width=10)
    return t
