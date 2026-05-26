from __future__ import annotations
import re
from ..models import ParseResult
from .results import CrashDetail, CrashAnalysisResult

_EXCEPTION_RE = re.compile(
    r"(EXCEPTION_\w+|access violation|stack overflow|divide by zero|illegal instruction)",
    re.I,
)
_FILE_LINE_RE = re.compile(r"\[File:([^\]]+)\]\s*\[Line:\s*(\d+)\]")


class CrashAnalyzer:
    def analyze(self, result: ParseResult) -> CrashAnalysisResult:
        details: list[CrashDetail] = []

        for block in result.crash_blocks:
            exc_type: str | None = None
            all_lines = (
                [block.trigger_entry.message]
                + block.callstack_lines
                + [e.raw for e in block.context_after]
            )
            for line in all_lines:
                m = _EXCEPTION_RE.search(line)
                if m:
                    exc_type = m.group(1)
                    break

            src_file: str | None = None
            src_line: int | None = None
            m2 = _FILE_LINE_RE.search(block.trigger_entry.message)
            if m2:
                # Keep only the filename, not the full build path
                src_file = re.split(r"[/\\]", m2.group(1))[-1]
                src_line = int(m2.group(2))

            details.append(CrashDetail(
                block=block,
                exception_type=exc_type,
                source_file=src_file,
                source_line=src_line,
                callstack_depth=len(block.callstack_lines),
            ))

        return CrashAnalysisResult(details=details)
