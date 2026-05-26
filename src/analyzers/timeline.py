from __future__ import annotations
from typing import TYPE_CHECKING
from .results import TimelineEvent, AnalysisReport

if TYPE_CHECKING:
    from ..models import ParseResult

_MAX_ERRORS = 20
_MAX_WARNINGS = 15


class TimelineBuilder:
    def build(self, result: "ParseResult", report: AnalysisReport) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []

        # Crashes — highest priority
        for detail in report.crash.details:
            cb = detail.block
            desc = f"CRASH: {cb.summary[:100]}"
            if detail.exception_type:
                desc += f" | {detail.exception_type}"
            if detail.source_file:
                desc += f" | {detail.source_file}:{detail.source_line}"
            events.append(TimelineEvent(
                line_number=cb.line_number,
                kind="crash",
                description=desc,
                severity="fatal",
                timestamp=cb.trigger_entry.timestamp,
                frame=cb.trigger_entry.frame,
            ))

        # Errors
        for g in report.errors.error_groups[:_MAX_ERRORS]:
            e = g.examples[0] if g.examples else None
            if not e:
                continue
            suffix = f" (x{g.count})" if g.count > 1 else ""
            events.append(TimelineEvent(
                line_number=e.line_number,
                kind="error",
                description=f"[{g.category}] {g.template[:100]}{suffix}",
                severity="error",
                timestamp=e.timestamp,
                frame=e.frame,
            ))

        # Warnings
        for g in report.errors.warning_groups[:_MAX_WARNINGS]:
            e = g.examples[0] if g.examples else None
            if not e:
                continue
            suffix = f" (x{g.count})" if g.count > 1 else ""
            events.append(TimelineEvent(
                line_number=e.line_number,
                kind="warning",
                description=f"[{g.category}] {g.template[:100]}{suffix}",
                severity="warning",
                timestamp=e.timestamp,
                frame=e.frame,
            ))

        # Asset issues
        for issue in report.assets.issues:
            sev = "error" if issue.kind in ("load_failure", "cook_error") else "warning"
            events.append(TimelineEvent(
                line_number=issue.entry.line_number,
                kind=f"asset_{issue.kind}",
                description=f"Asset {issue.kind.replace('_', ' ')}: {issue.asset_path}",
                severity=sev,
                timestamp=issue.entry.timestamp,
                frame=issue.entry.frame,
            ))

        # Shader issues
        for issue in report.shaders.issues:
            sev = "error" if issue.kind == "compile_error" else "warning"
            time_str = f" ({issue.compile_time_ms}ms)" if issue.compile_time_ms else ""
            events.append(TimelineEvent(
                line_number=issue.entry.line_number,
                kind=f"shader_{issue.kind}",
                description=f"Shader {issue.kind.replace('_', ' ')}: {issue.message[:80]}{time_str}",
                severity=sev,
                timestamp=issue.entry.timestamp,
                frame=issue.entry.frame,
            ))

        # Performance events
        for perf in report.performance.events:
            sev = "error" if perf.kind == "oom_warning" else "warning"
            events.append(TimelineEvent(
                line_number=perf.entry.line_number,
                kind=perf.kind,
                description=perf.description,
                severity=sev,
                timestamp=perf.entry.timestamp,
                frame=perf.entry.frame,
            ))

        # Network events
        for net in report.network.events:
            sev = "error" if net.kind == "error" else "warning"
            events.append(TimelineEvent(
                line_number=net.entry.line_number,
                kind=net.kind,
                description=f"[Network] {net.description[:100]}",
                severity=sev,
                timestamp=net.entry.timestamp,
                frame=net.entry.frame,
            ))

        events.sort(key=lambda ev: ev.line_number)
        return events
