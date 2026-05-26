from __future__ import annotations
import re
from ..models import ParseResult
from .results import PerformanceEvent, PerformanceAnalysisResult

_HITCH_THRESHOLD_MS = 33.0  # ~30 fps frame budget

_HITCH_RE = re.compile(
    r"(?:hitch.*?(\d+\.?\d*)\s*ms|(\d+\.?\d*)\s*ms.*?hitch)", re.I
)
_GC_RE = re.compile(
    r"(collecting garbage|gc full purge|garbage collection took|purging uobjects)", re.I
)
_GC_TIME_RE = re.compile(r"(\d+\.?\d*)\s*ms")
_OOM_RE = re.compile(
    r"(out of memory|allocation failed|not enough memory|ran out of memory)", re.I
)
_MEM_WARN_RE = re.compile(
    r"(memory.*?warning|texture.*?memory.*?exceed|virtual memory.*?low|physical memory.*?low)", re.I
)
_FRAME_TIME_RE = re.compile(r"frame.*?time.*?(\d+\.?\d*)\s*ms", re.I)


class PerformanceAnalyzer:
    def __init__(self, hitch_threshold_ms: float = _HITCH_THRESHOLD_MS):
        self.hitch_threshold_ms = hitch_threshold_ms

    def analyze(self, result: ParseResult) -> PerformanceAnalysisResult:
        events: list[PerformanceEvent] = []

        for entry in result.entries:
            msg = entry.message

            m = _HITCH_RE.search(msg)
            if m:
                ms = float(m.group(1) or m.group(2))
                if ms >= self.hitch_threshold_ms:
                    events.append(PerformanceEvent(
                        kind="hitch",
                        description=f"Frame hitch: {ms:.1f}ms (line {entry.line_number})",
                        entry=entry,
                        value_ms=ms,
                    ))
                continue

            # Check frame time even without the word "hitch"
            m = _FRAME_TIME_RE.search(msg)
            if m:
                ms = float(m.group(1))
                if ms >= self.hitch_threshold_ms:
                    events.append(PerformanceEvent(
                        kind="hitch",
                        description=f"High frame time: {ms:.1f}ms",
                        entry=entry,
                        value_ms=ms,
                    ))
                continue

            if _GC_RE.search(msg):
                m2 = _GC_TIME_RE.search(msg)
                ms2 = float(m2.group(1)) if m2 else None
                events.append(PerformanceEvent(
                    kind="gc_purge",
                    description=msg[:120],
                    entry=entry,
                    value_ms=ms2,
                ))
                continue

            if _OOM_RE.search(msg):
                events.append(PerformanceEvent(
                    kind="oom_warning",
                    description=msg[:120],
                    entry=entry,
                ))
                continue

            if _MEM_WARN_RE.search(msg):
                events.append(PerformanceEvent(
                    kind="memory_warning",
                    description=msg[:120],
                    entry=entry,
                ))

        return PerformanceAnalysisResult(events=events)
