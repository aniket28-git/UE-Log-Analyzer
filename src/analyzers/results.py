from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import LogEntry, CrashBlock, ParseResult, Verbosity


# ── Crash ────────────────────────────────────────────────────────────────────

@dataclass
class CrashDetail:
    block: "CrashBlock"
    exception_type: Optional[str]
    source_file: Optional[str]
    source_line: Optional[int]
    callstack_depth: int


@dataclass
class CrashAnalysisResult:
    details: list[CrashDetail] = field(default_factory=list)

    @property
    def has_crash(self) -> bool:
        return len(self.details) > 0


# ── Errors / Warnings ────────────────────────────────────────────────────────

@dataclass
class ErrorGroup:
    category: str
    verbosity: "Verbosity"
    template: str           # normalised message with paths/numbers replaced
    count: int
    first_line: int
    examples: list["LogEntry"] = field(default_factory=list)


@dataclass
class ErrorAnalysisResult:
    error_groups: list[ErrorGroup] = field(default_factory=list)
    warning_groups: list[ErrorGroup] = field(default_factory=list)

    @property
    def total_errors(self) -> int:
        return sum(g.count for g in self.error_groups)

    @property
    def total_warnings(self) -> int:
        return sum(g.count for g in self.warning_groups)


# ── Assets ───────────────────────────────────────────────────────────────────

@dataclass
class AssetIssue:
    kind: str               # "load_failure" | "missing_ref" | "cook_error"
    asset_path: str
    entry: "LogEntry"


@dataclass
class AssetAnalysisResult:
    issues: list[AssetIssue] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.issues)


# ── Shaders ──────────────────────────────────────────────────────────────────

@dataclass
class ShaderIssue:
    kind: str               # "compile_error" | "slow_compile"
    message: str
    compile_time_ms: Optional[int]
    entry: "LogEntry"


@dataclass
class ShaderAnalysisResult:
    issues: list[ShaderIssue] = field(default_factory=list)

    @property
    def compile_errors(self) -> int:
        return sum(1 for i in self.issues if i.kind == "compile_error")

    @property
    def slow_compiles(self) -> int:
        return sum(1 for i in self.issues if i.kind == "slow_compile")


# ── Performance ──────────────────────────────────────────────────────────────

@dataclass
class PerformanceEvent:
    kind: str               # "hitch" | "gc_purge" | "oom_warning" | "memory_warning"
    description: str
    entry: "LogEntry"
    value_ms: Optional[float] = None


@dataclass
class PerformanceAnalysisResult:
    events: list[PerformanceEvent] = field(default_factory=list)

    @property
    def hitch_count(self) -> int:
        return sum(1 for e in self.events if e.kind == "hitch")

    @property
    def gc_purge_count(self) -> int:
        return sum(1 for e in self.events if e.kind == "gc_purge")


# ── Network ──────────────────────────────────────────────────────────────────

@dataclass
class NetworkEvent:
    kind: str               # "error" | "packet_loss" | "timeout" | "disconnect" | "connect_failed"
    description: str
    entry: "LogEntry"


@dataclass
class NetworkAnalysisResult:
    events: list[NetworkEvent] = field(default_factory=list)


# ── Timeline ─────────────────────────────────────────────────────────────────

@dataclass
class TimelineEvent:
    line_number: int
    kind: str
    description: str
    severity: str           # "info" | "warning" | "error" | "fatal"
    timestamp: Optional[datetime] = None
    frame: Optional[int] = None


# ── Top-level report ─────────────────────────────────────────────────────────

@dataclass
class AnalysisReport:
    parse_result: "ParseResult"
    crash: CrashAnalysisResult
    errors: ErrorAnalysisResult
    assets: AssetAnalysisResult
    shaders: ShaderAnalysisResult
    performance: PerformanceAnalysisResult
    network: NetworkAnalysisResult
    timeline: list[TimelineEvent] = field(default_factory=list)

    @property
    def has_crash(self) -> bool:
        return self.crash.has_crash
