from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .models import ParseResult, Verbosity

# Maps CLI severity name -> set of Verbosity values to KEEP
_SEVERITY_SETS: dict[str, set[Verbosity]] = {
    "all": set(Verbosity),
    "warning": {Verbosity.WARNING, Verbosity.ERROR, Verbosity.FATAL},
    "error": {Verbosity.ERROR, Verbosity.FATAL},
}


@dataclass
class FilterOptions:
    min_severity: str = "all"                     # "all" | "warning" | "error"
    categories: Optional[list[str]] = None        # keep only these categories
    since: Optional[datetime] = None              # keep entries at or after
    until: Optional[datetime] = None              # keep entries at or before


def apply_filters(result: ParseResult, opts: FilterOptions) -> ParseResult:
    """Return a new ParseResult with entries filtered by opts.

    CrashBlocks are always preserved regardless of filters — they are too
    important to hide.
    """
    keep_verbosity = _SEVERITY_SETS.get(opts.min_severity, set(Verbosity))
    category_set = (
        {c.lower() for c in opts.categories} if opts.categories else None
    )

    entries = []
    for entry in result.entries:
        # Severity gate
        if entry.verbosity not in keep_verbosity:
            continue
        # Category gate
        if category_set and entry.category.lower() not in category_set:
            continue
        # Timestamp gates (entries without timestamps pass through)
        if opts.since and entry.timestamp and entry.timestamp < opts.since:
            continue
        if opts.until and entry.timestamp and entry.timestamp > opts.until:
            continue
        entries.append(entry)

    filtered = ParseResult(
        entries=entries,
        crash_blocks=result.crash_blocks,   # crashes always shown
        total_lines=result.total_lines,
        parse_errors=result.parse_errors,
    )
    filtered.finalize()
    return filtered


def parse_timestamp_arg(ts_str: str) -> Optional[datetime]:
    """Parse a --since / --until argument.

    Accepts:
      - Full UE format:  2024.03.15-12.34.56
      - Time only:       12:34:56  (assumes any date)
    """
    formats = [
        "%Y.%m.%d-%H.%M.%S",
        "%Y.%m.%d-%H.%M.%S:%f",
        "%H:%M:%S",
        "%H.%M.%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    return None
