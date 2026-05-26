from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Verbosity(str, Enum):
    FATAL = "Fatal"
    ERROR = "Error"
    WARNING = "Warning"
    DISPLAY = "Display"
    LOG = "Log"
    VERBOSE = "Verbose"
    VERY_VERBOSE = "VeryVerbose"
    UNKNOWN = "Unknown"

    @classmethod
    def from_str(cls, text: str) -> "Verbosity":
        _map = {
            "fatal": cls.FATAL,
            "error": cls.ERROR,
            "warning": cls.WARNING,
            "display": cls.DISPLAY,
            "log": cls.LOG,
            "verbose": cls.VERBOSE,
            "veryverbose": cls.VERY_VERBOSE,
        }
        return _map.get(text.lower(), cls.UNKNOWN)


@dataclass
class LogEntry:
    line_number: int
    raw: str
    category: str
    verbosity: Verbosity
    message: str
    timestamp: Optional[datetime] = None
    frame: Optional[int] = None

    @property
    def is_error(self) -> bool:
        return self.verbosity in (Verbosity.ERROR, Verbosity.FATAL)

    @property
    def is_warning(self) -> bool:
        return self.verbosity == Verbosity.WARNING

    @property
    def is_fatal(self) -> bool:
        return self.verbosity == Verbosity.FATAL


@dataclass
class CrashBlock:
    """A fatal error / unhandled exception with its full callstack and surrounding context."""
    trigger_entry: LogEntry
    callstack_lines: list[str] = field(default_factory=list)
    context_before: list[LogEntry] = field(default_factory=list)
    context_after: list[LogEntry] = field(default_factory=list)

    @property
    def line_number(self) -> int:
        return self.trigger_entry.line_number

    @property
    def summary(self) -> str:
        return self.trigger_entry.message


@dataclass
class ParseResult:
    """Everything the parser produces from a single log file."""
    entries: list[LogEntry] = field(default_factory=list)
    crash_blocks: list[CrashBlock] = field(default_factory=list)
    total_lines: int = 0
    parse_errors: list[str] = field(default_factory=list)

    # Derived convenience collections (populated by parser after pass)
    errors: list[LogEntry] = field(default_factory=list)
    warnings: list[LogEntry] = field(default_factory=list)

    def finalize(self) -> None:
        self.errors = [e for e in self.entries if e.is_error]
        self.warnings = [e for e in self.entries if e.is_warning]
