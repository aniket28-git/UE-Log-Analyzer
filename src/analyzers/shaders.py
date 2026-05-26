from __future__ import annotations
import re
from ..models import ParseResult
from .results import ShaderIssue, ShaderAnalysisResult

_SLOW_THRESHOLD_MS = 1000
_TIME_RE = re.compile(r"(\d+)\s*ms", re.I)

# Categories that are shader/GPU related
_SHADER_CATS = re.compile(r"LogShader|LogD3D|LogVulkan|LogMetal|LogRHI", re.I)


class ShaderAnalyzer:
    def __init__(self, slow_threshold_ms: int = _SLOW_THRESHOLD_MS):
        self.slow_threshold_ms = slow_threshold_ms

    def analyze(self, result: ParseResult) -> ShaderAnalysisResult:
        issues: list[ShaderIssue] = []

        for entry in result.entries:
            if not _SHADER_CATS.search(entry.category):
                continue

            if entry.is_error:
                issues.append(ShaderIssue(
                    kind="compile_error",
                    message=entry.message,
                    compile_time_ms=None,
                    entry=entry,
                ))
                continue

            m = _TIME_RE.search(entry.message)
            if m:
                ms = int(m.group(1))
                if ms >= self.slow_threshold_ms:
                    issues.append(ShaderIssue(
                        kind="slow_compile",
                        message=entry.message,
                        compile_time_ms=ms,
                        entry=entry,
                    ))

        return ShaderAnalysisResult(issues=issues)
