from __future__ import annotations
from rich.console import Console
from rich.panel import Panel
from ..diff import DiffReport, SectionDiff


class DiffConsoleReport:
    def __init__(self, console: Console | None = None) -> None:
        self._con = console or Console()

    def render(self, diff: DiffReport) -> None:
        con = self._con
        con.print(Panel(
            f"[bold]LOG DIFF[/]  [dim]{diff.log_before}[/]  →  [bold]{diff.log_after}[/]",
            style="blue",
        ))
        if diff.has_regressions:
            con.print("\n[bold red]REGRESSIONS DETECTED[/bold red]\n")
        else:
            con.print("\n[bold green]No regressions — no new issues found[/bold green]\n")

        self._section(con, "CRASHES", diff.crashes,
            lambda c: f"[red]+ {c.exception_type or c.block.trigger_entry.message[:80]}[/]",
            lambda c: f"[green]- {c.exception_type or c.block.trigger_entry.message[:80]}[/]")

        self._section(con, "ERRORS", diff.errors,
            lambda g: f"[red]+ [{g.category}] x{g.count}  {g.template[:80]}[/]",
            lambda g: f"[green]- [{g.category}] x{g.count}  {g.template[:80]}[/]")

        self._section(con, "WARNINGS", diff.warnings,
            lambda g: f"[yellow]+ [{g.category}] x{g.count}  {g.template[:80]}[/]",
            lambda g: f"[green]- [{g.category}] x{g.count}  {g.template[:80]}[/]")

        self._section(con, "ASSET ISSUES", diff.assets,
            lambda a: f"[red]+ {a.kind}: {a.asset_path}[/]",
            lambda a: f"[green]- {a.kind}: {a.asset_path}[/]")

        self._section(con, "SHADER ISSUES", diff.shaders,
            lambda s: f"[red]+ {s.kind}: {s.message[:80]}[/]",
            lambda s: f"[green]- {s.kind}: {s.message[:80]}[/]")

        self._section(con, "PERFORMANCE", diff.performance,
            lambda e: f"[red]+ {e.kind}: {e.description[:80]}[/]",
            lambda e: f"[green]- {e.kind}: {e.description[:80]}[/]")

        self._section(con, "NETWORK", diff.network,
            lambda e: f"[red]+ {e.kind}: {e.description[:80]}[/]",
            lambda e: f"[green]- {e.kind}: {e.description[:80]}[/]")

    def _section(
        self, con: Console, title: str, section: SectionDiff,
        added_fmt, removed_fmt,
    ) -> None:
        delta = section.delta
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        color = "red" if delta > 0 else ("green" if delta < 0 else "dim")
        con.print(
            f"[bold]{title}[/]  "
            f"[dim]before {section.count_before}  after {section.count_after}  "
            f"Δ[/][{color}]{delta_str}[/]"
        )
        for item in section.added:
            con.print(f"  {added_fmt(item)}")
        for item in section.removed:
            con.print(f"  {removed_fmt(item)}")
        if not section.added and not section.removed:
            con.print("  [dim]no change[/]")
        con.print()
