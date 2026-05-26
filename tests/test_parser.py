from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parser import LogParser
from src.models import Verbosity

SAMPLES = Path(__file__).parent / "sample_logs"


class TestNormalLog:
    def setup_method(self):
        self.result = LogParser().parse(SAMPLES / "normal.log")

    def test_total_lines(self):
        assert self.result.total_lines == 10

    def test_entry_count(self):
        # All 10 lines have UE headers in normal.log
        assert len(self.result.entries) == 10

    def test_no_crashes(self):
        assert len(self.result.crash_blocks) == 0

    def test_error_count(self):
        # Two identical error lines
        assert len(self.result.errors) == 2

    def test_warning_count(self):
        assert len(self.result.warnings) == 3

    def test_first_entry(self):
        e = self.result.entries[0]
        assert e.line_number == 1
        assert e.category == "LogInit"
        assert e.verbosity == Verbosity.DISPLAY
        assert "Loading project settings" in e.message
        assert e.frame == 0

    def test_timestamp_parsed(self):
        e = self.result.entries[0]
        assert e.timestamp is not None
        assert e.timestamp.year == 2024
        assert e.timestamp.month == 3
        assert e.timestamp.day == 15

    def test_error_entry(self):
        err = self.result.errors[0]
        assert err.verbosity == Verbosity.ERROR
        assert err.category == "LogEngine"

    def test_warning_category(self):
        categories = {w.category for w in self.result.warnings}
        assert "LogNet" in categories
        assert "LogShaderCompilers" in categories


class TestCrashLog:
    def setup_method(self):
        self.result = LogParser().parse(SAMPLES / "crash.log")

    def test_crash_detected(self):
        assert len(self.result.crash_blocks) == 1

    def test_crash_summary(self):
        crash = self.result.crash_blocks[0]
        assert "Assertion failed" in crash.summary or "Fatal" in crash.summary

    def test_crash_callstack_not_empty(self):
        crash = self.result.crash_blocks[0]
        assert len(crash.callstack_lines) > 0

    def test_crash_context_before(self):
        crash = self.result.crash_blocks[0]
        # Should have captured the 4 normal lines before the crash
        assert len(crash.context_before) >= 3

    def test_crash_context_after(self):
        crash = self.result.crash_blocks[0]
        # The two LogExit lines after the callstack
        assert len(crash.context_after) >= 1

    def test_crash_line_number(self):
        crash = self.result.crash_blocks[0]
        assert crash.line_number == 5  # 5th line in crash.log


class TestNoHeaderLog:
    def setup_method(self):
        self.result = LogParser().parse(SAMPLES / "no_header.log")

    def test_total_lines(self):
        assert self.result.total_lines == 5

    def test_continuation_entries_captured(self):
        # Lines 2 and 3 have no header — should still be in entries
        raw_messages = [e.raw for e in self.result.entries]
        assert any("continuation" in r for r in raw_messages)
        assert any("Another raw" in r for r in raw_messages)

    def test_continuation_inherits_category(self):
        # Continuation lines should get the category of the previous entry
        cont = [e for e in self.result.entries if "no UE header" in e.raw]
        assert len(cont) == 1
        assert cont[0].category == "LogInit"

    def test_normal_entries_after_continuation(self):
        last = self.result.entries[-1]
        assert last.category == "LogEngine"
        assert last.verbosity == Verbosity.DISPLAY


class TestUtilParsing:
    def test_timestamp(self):
        from src.utils import parse_timestamp
        dt = parse_timestamp("2024.03.15-12.34.56:789")
        assert dt is not None
        assert dt.hour == 12
        assert dt.minute == 34
        assert dt.second == 56

    def test_invalid_timestamp(self):
        from src.utils import parse_timestamp
        assert parse_timestamp("not-a-timestamp") is None

    def test_crash_trigger_detection(self):
        from src.utils import is_crash_trigger
        assert is_crash_trigger("Fatal error!")
        assert is_crash_trigger("Assertion failed: ptr != nullptr")
        assert is_crash_trigger("Unhandled Exception: EXCEPTION_ACCESS_VIOLATION")
        assert not is_crash_trigger("Normal log message")

    def test_line_regex_match(self):
        from src.utils import match_log_line
        line = "[2024.03.15-12.34.56:789][  0]LogEngine: Error: Something bad"
        m = match_log_line(line)
        assert m is not None
        assert m.group("category") == "LogEngine"
        assert m.group("verbosity") == "Error"
        assert m.group("message") == "Something bad"
        assert m.group("frame").strip() == "0"

    def test_line_regex_no_verbosity(self):
        from src.utils import match_log_line
        line = "[2024.03.15-12.34.56:789][  5]LogInit: Engine initialized"
        m = match_log_line(line)
        assert m is not None
        assert m.group("verbosity") is None
        assert m.group("message") == "Engine initialized"
