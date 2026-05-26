from __future__ import annotations
import json
from ..diff import DiffReport, SectionDiff


def _section_dict(section: SectionDiff, serializer) -> dict:
    return {
        "count_before": section.count_before,
        "count_after": section.count_after,
        "delta": section.delta,
        "added": [serializer(x) for x in section.added],
        "removed": [serializer(x) for x in section.removed],
    }


class DiffJsonExport:
    def render(self, diff: DiffReport) -> str:
        data = {
            "log_before": diff.log_before,
            "log_after": diff.log_after,
            "has_regressions": diff.has_regressions,
            "crashes": _section_dict(diff.crashes, lambda c: {
                "exception_type": c.exception_type,
                "source_file": c.source_file,
                "source_line": c.source_line,
            }),
            "errors": _section_dict(diff.errors, lambda g: {
                "category": g.category,
                "template": g.template,
                "count": g.count,
            }),
            "warnings": _section_dict(diff.warnings, lambda g: {
                "category": g.category,
                "template": g.template,
                "count": g.count,
            }),
            "assets": _section_dict(diff.assets, lambda a: {
                "kind": a.kind,
                "asset_path": a.asset_path,
            }),
            "shaders": _section_dict(diff.shaders, lambda s: {
                "kind": s.kind,
                "message": s.message,
            }),
            "performance": _section_dict(diff.performance, lambda e: {
                "kind": e.kind,
                "description": e.description,
            }),
            "network": _section_dict(diff.network, lambda e: {
                "kind": e.kind,
                "description": e.description,
            }),
        }
        return json.dumps(data, indent=2, default=str)
