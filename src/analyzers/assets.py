from __future__ import annotations
import re
from ..models import ParseResult
from .results import AssetIssue, AssetAnalysisResult

# Ordered list of (pattern, kind) — first match wins per line
_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"[Ff]ailed to find object '([^']+)'"), "missing_ref"),
    (re.compile(r"[Cc]ouldn'?t load package '([^']+)'"), "load_failure"),
    (re.compile(r"[Ee]rror loading '([^']+)'"), "load_failure"),
    (re.compile(r"[Ff]ailed to load '([^']+)'"), "load_failure"),
    (re.compile(r"[Cc]ook.*?[Ee]rror.*?'([^']+)'"), "cook_error"),
    (re.compile(r"[Aa]sset.*?not found.*?'([^']+)'"), "missing_ref"),
    (re.compile(r"[Mm]issing.*?[Aa]sset.*?'([^']+)'"), "missing_ref"),
    (re.compile(r"[Uu]nable to find.*?'([^']+)'"), "missing_ref"),
]


class AssetAnalyzer:
    def analyze(self, result: ParseResult) -> AssetAnalysisResult:
        issues: list[AssetIssue] = []
        seen: set[tuple[str, str]] = set()

        for entry in result.entries:
            for pattern, kind in _PATTERNS:
                m = pattern.search(entry.message)
                if m:
                    path = m.group(1)
                    key = (kind, path)
                    if key not in seen:
                        seen.add(key)
                        issues.append(AssetIssue(kind=kind, asset_path=path, entry=entry))
                    break  # only one match per entry

        return AssetAnalysisResult(issues=issues)
