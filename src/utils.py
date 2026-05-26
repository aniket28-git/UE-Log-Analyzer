from __future__ import annotations
import re
from datetime import datetime
from typing import Optional

# [2024.03.15-12.34.56:789][  0]LogCategory: Verbosity: Message
_LINE_RE = re.compile(
    r"^\[(?P<ts>\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}:\d{3})\]"
    r"\[(?P<frame>\s*\d+)\]"
    r"(?P<category>[A-Za-z0-9_]+)"
    r"(?:: (?P<verbosity>Fatal|Error|Warning|Display|Log|Verbose|VeryVerbose))?"
    r": (?P<message>.*)",
    re.IGNORECASE,
)

# Lines that belong to a crash block (no UE header)
_CRASH_TRIGGERS = re.compile(
    r"(Fatal error!|Unhandled Exception:|Assertion failed:|LowLevelFatalError|"
    r"Crash in runnable thread|access violation reading location|"
    r"ensure condition '.*?' failed)",
    re.IGNORECASE,
)

# Callstack line — starts with 0x or a frame index like "0   "
_CALLSTACK_LINE_RE = re.compile(
    r"^\s*(0x[0-9a-fA-F]+|!\s|\d+\s+0x|[A-Za-z0-9_]+!)",
)

_TS_FORMAT = "%Y.%m.%d-%H.%M.%S:%f"


def parse_timestamp(ts_str: str) -> Optional[datetime]:
    try:
        # UE uses 3-digit milliseconds; pad to 6 for %f
        base, ms = ts_str.rsplit(":", 1)
        return datetime.strptime(f"{base}:{ms.ljust(6, '0')}", _TS_FORMAT)
    except (ValueError, AttributeError):
        return None


def match_log_line(line: str):
    """Return the regex match object if line looks like a standard UE log line."""
    return _LINE_RE.match(line)


def is_crash_trigger(line: str) -> bool:
    return bool(_CRASH_TRIGGERS.search(line))


def is_callstack_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    # Callstack lines often start with whitespace + address
    return bool(_CALLSTACK_LINE_RE.match(stripped)) or stripped.startswith("0x")
