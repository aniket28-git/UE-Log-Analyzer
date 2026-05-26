from __future__ import annotations
import json
from datetime import datetime
from ..analyzers.results import AnalysisReport
from ..models import LogEntry


def _entry(e: LogEntry) -> dict:
    return {
        "line_number": e.line_number,
        "category": e.category,
        "verbosity": e.verbosity.value,
        "message": e.message,
        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        "frame": e.frame,
    }


class JsonExport:
    def render(self, report: AnalysisReport, filename: str = "") -> str:
        pr = report.parse_result

        data: dict = {
            "meta": {
                "filename": filename,
                "generated_at": datetime.now().isoformat(),
                "total_lines": pr.total_lines,
                "parse_errors": pr.parse_errors,
            },
            "summary": {
                "has_crash": report.has_crash,
                "total_errors": report.errors.total_errors,
                "total_warnings": report.errors.total_warnings,
                "asset_issues": report.assets.total,
                "shader_compile_errors": report.shaders.compile_errors,
                "shader_slow_compiles": report.shaders.slow_compiles,
                "hitch_count": report.performance.hitch_count,
                "gc_purge_count": report.performance.gc_purge_count,
                "network_events": len(report.network.events),
            },
            "crashes": [
                {
                    "line_number": d.block.line_number,
                    "summary": d.block.summary,
                    "exception_type": d.exception_type,
                    "source_file": d.source_file,
                    "source_line": d.source_line,
                    "callstack_depth": d.callstack_depth,
                    "callstack": d.block.callstack_lines,
                    "trigger": _entry(d.block.trigger_entry),
                }
                for d in report.crash.details
            ],
            "errors": [
                {
                    "category": g.category,
                    "verbosity": g.verbosity.value,
                    "template": g.template,
                    "count": g.count,
                    "first_line": g.first_line,
                    "examples": [_entry(e) for e in g.examples],
                }
                for g in report.errors.error_groups
            ],
            "warnings": [
                {
                    "category": g.category,
                    "verbosity": g.verbosity.value,
                    "template": g.template,
                    "count": g.count,
                    "first_line": g.first_line,
                    "examples": [_entry(e) for e in g.examples],
                }
                for g in report.errors.warning_groups
            ],
            "assets": [
                {
                    "kind": i.kind,
                    "asset_path": i.asset_path,
                    "line_number": i.entry.line_number,
                }
                for i in report.assets.issues
            ],
            "shaders": [
                {
                    "kind": i.kind,
                    "message": i.message,
                    "compile_time_ms": i.compile_time_ms,
                    "line_number": i.entry.line_number,
                }
                for i in report.shaders.issues
            ],
            "performance": [
                {
                    "kind": ev.kind,
                    "description": ev.description,
                    "value_ms": ev.value_ms,
                    "line_number": ev.entry.line_number,
                }
                for ev in report.performance.events
            ],
            "network": [
                {
                    "kind": ev.kind,
                    "description": ev.description,
                    "line_number": ev.entry.line_number,
                }
                for ev in report.network.events
            ],
            "timeline": [
                {
                    "line_number": ev.line_number,
                    "kind": ev.kind,
                    "severity": ev.severity,
                    "description": ev.description,
                    "timestamp": ev.timestamp.isoformat() if ev.timestamp else None,
                    "frame": ev.frame,
                }
                for ev in report.timeline
            ],
        }

        return json.dumps(data, indent=2, ensure_ascii=False)
