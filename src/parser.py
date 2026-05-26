from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from .models import CrashBlock, LogEntry, ParseResult, Verbosity
from .utils import is_callstack_line, is_crash_trigger, match_log_line, parse_timestamp

# How many normal entries to keep as context around a crash
_CONTEXT_WINDOW = 10

# After a crash trigger, collect up to this many lines as callstack
_MAX_CALLSTACK_LINES = 120


def _make_entry(line_number: int, raw: str, m) -> LogEntry:
    ts = parse_timestamp(m.group("ts"))
    frame_str = m.group("frame").strip()
    frame = int(frame_str) if frame_str.isdigit() else None
    verbosity_str = m.group("verbosity") or "Display"
    return LogEntry(
        line_number=line_number,
        raw=raw,
        category=m.group("category"),
        verbosity=Verbosity.from_str(verbosity_str),
        message=m.group("message"),
        timestamp=ts,
        frame=frame,
    )


def _make_continuation_entry(line_number: int, raw: str, prev_category: str) -> LogEntry:
    """Lines that have no UE header are continuations — attach to previous category."""
    return LogEntry(
        line_number=line_number,
        raw=raw,
        category=prev_category,
        verbosity=Verbosity.UNKNOWN,
        message=raw.rstrip("\n"),
    )


def _iter_lines(path: Path) -> Iterator[tuple[int, str]]:
    """Yield (1-based line number, line text), stripping BOM and normalising endings."""
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for idx, line in enumerate(fh, start=1):
            yield idx, line.rstrip("\r\n")


class LogParser:
    def parse(self, path: str | Path) -> ParseResult:
        path = Path(path)
        result = ParseResult()

        recent: list[LogEntry] = []   # sliding window for crash context
        last_category = "Unknown"

        # State machine for crash block collection
        in_crash = False
        current_crash: CrashBlock | None = None
        callstack_lines_remaining = 0

        for line_number, raw in _iter_lines(path):
            result.total_lines = line_number

            m = match_log_line(raw)

            # ── Standard UE log line ────────────────────────────────────────
            if m:
                entry = _make_entry(line_number, raw, m)
                last_category = entry.category

                # Close an open crash block when we see a normal line again
                # (after callstack lines have been exhausted)
                if in_crash and callstack_lines_remaining <= 0:
                    result.crash_blocks.append(current_crash)
                    in_crash = False
                    current_crash = None

                if in_crash and current_crash is not None:
                    # Still collecting context after callstack
                    current_crash.context_after.append(entry)
                    if len(current_crash.context_after) >= _CONTEXT_WINDOW:
                        result.crash_blocks.append(current_crash)
                        in_crash = False
                        current_crash = None
                else:
                    result.entries.append(entry)
                    _update_window(recent, entry, _CONTEXT_WINDOW)

                # Check if this well-formed line itself triggers a crash
                if entry.is_fatal or is_crash_trigger(entry.message):
                    in_crash, current_crash, callstack_lines_remaining = _open_crash(
                        entry, recent, result
                    )

            # ── Non-standard line (continuation / callstack / raw output) ───
            else:
                if in_crash and current_crash is not None:
                    if callstack_lines_remaining > 0:
                        current_crash.callstack_lines.append(raw)
                        callstack_lines_remaining -= 1
                        # Blank line signals end of callstack section
                        if raw.strip() == "":
                            callstack_lines_remaining = 0
                    else:
                        current_crash.context_after.append(
                            _make_continuation_entry(line_number, raw, last_category)
                        )
                        if len(current_crash.context_after) >= _CONTEXT_WINDOW:
                            result.crash_blocks.append(current_crash)
                            in_crash = False
                            current_crash = None
                else:
                    # Check if this unformatted line is a crash trigger
                    if is_crash_trigger(raw):
                        trigger = _make_continuation_entry(line_number, raw, last_category)
                        trigger.verbosity = Verbosity.FATAL
                        result.entries.append(trigger)
                        _update_window(recent, trigger, _CONTEXT_WINDOW)
                        in_crash, current_crash, callstack_lines_remaining = _open_crash(
                            trigger, recent, result
                        )
                    else:
                        entry = _make_continuation_entry(line_number, raw, last_category)
                        result.entries.append(entry)
                        _update_window(recent, entry, _CONTEXT_WINDOW)

        # Flush any open crash block at EOF
        if in_crash and current_crash is not None:
            result.crash_blocks.append(current_crash)

        result.finalize()
        return result


def _update_window(window: list[LogEntry], entry: LogEntry, size: int) -> None:
    window.append(entry)
    if len(window) > size:
        window.pop(0)


def _open_crash(
    trigger: LogEntry,
    recent: list[LogEntry],
    result: ParseResult,
) -> tuple[bool, CrashBlock, int]:
    """Start collecting a crash block; remove trigger from entries if it was just added."""
    if result.entries and result.entries[-1] is trigger:
        result.entries.pop()

    crash = CrashBlock(
        trigger_entry=trigger,
        context_before=list(recent),
    )
    return True, crash, _MAX_CALLSTACK_LINES
