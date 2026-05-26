from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parser import LogParser
from src.filters import FilterOptions, apply_filters, parse_timestamp_arg
from src.models import Verbosity

SAMPLES = Path(__file__).parent / "sample_logs"


def parse(name: str):
    return LogParser().parse(SAMPLES / name)


class TestSeverityFilter:
    def setup_method(self):
        self.result = parse("comprehensive.log")

    def test_all_keeps_everything(self):
        opts = FilterOptions(min_severity="all")
        filtered = apply_filters(self.result, opts)
        assert len(filtered.entries) == len(self.result.entries)

    def test_error_filter_keeps_only_errors(self):
        opts = FilterOptions(min_severity="error")
        filtered = apply_filters(self.result, opts)
        for entry in filtered.entries:
            assert entry.verbosity in (Verbosity.ERROR, Verbosity.FATAL), \
                f"Entry with verbosity {entry.verbosity} should have been filtered out"

    def test_warning_filter_keeps_warnings_and_above(self):
        opts = FilterOptions(min_severity="warning")
        filtered = apply_filters(self.result, opts)
        for entry in filtered.entries:
            assert entry.verbosity in (Verbosity.WARNING, Verbosity.ERROR, Verbosity.FATAL), \
                f"Unexpected verbosity: {entry.verbosity}"

    def test_error_filter_reduces_count(self):
        all_opts = FilterOptions(min_severity="all")
        err_opts = FilterOptions(min_severity="error")
        all_filtered = apply_filters(self.result, all_opts)
        err_filtered = apply_filters(self.result, err_opts)
        assert len(err_filtered.entries) < len(all_filtered.entries)

    def test_crash_blocks_always_preserved(self):
        result = parse("crash.log")
        opts = FilterOptions(min_severity="error")
        filtered = apply_filters(result, opts)
        assert len(filtered.crash_blocks) == len(result.crash_blocks)

    def test_total_lines_preserved(self):
        opts = FilterOptions(min_severity="error")
        filtered = apply_filters(self.result, opts)
        assert filtered.total_lines == self.result.total_lines


class TestCategoryFilter:
    def setup_method(self):
        self.result = parse("comprehensive.log")

    def test_single_category(self):
        opts = FilterOptions(categories=["LogEngine"])
        filtered = apply_filters(self.result, opts)
        for entry in filtered.entries:
            assert entry.category.lower() == "logengine"

    def test_multiple_categories(self):
        opts = FilterOptions(categories=["LogEngine", "LogNet"])
        filtered = apply_filters(self.result, opts)
        allowed = {"logengine", "lognet"}
        for entry in filtered.entries:
            assert entry.category.lower() in allowed

    def test_case_insensitive(self):
        opts_lower = FilterOptions(categories=["logengine"])
        opts_upper = FilterOptions(categories=["LOGENGINE"])
        f1 = apply_filters(self.result, opts_lower)
        f2 = apply_filters(self.result, opts_upper)
        assert len(f1.entries) == len(f2.entries)

    def test_unknown_category_gives_empty(self):
        opts = FilterOptions(categories=["LogNonExistentXYZ"])
        filtered = apply_filters(self.result, opts)
        assert len(filtered.entries) == 0

    def test_no_categories_keeps_all(self):
        opts = FilterOptions(categories=None)
        filtered = apply_filters(self.result, opts)
        assert len(filtered.entries) == len(self.result.entries)


class TestTimestampFilter:
    def setup_method(self):
        self.result = parse("comprehensive.log")
        # comprehensive.log spans 10:00:00 to 10:00:18

    def test_since_cuts_early_entries(self):
        since = datetime(2024, 3, 15, 10, 0, 10)  # 10:00:10
        opts = FilterOptions(since=since)
        filtered = apply_filters(self.result, opts)
        for entry in filtered.entries:
            if entry.timestamp:
                assert entry.timestamp >= since

    def test_until_cuts_late_entries(self):
        until = datetime(2024, 3, 15, 10, 0, 5)   # 10:00:05
        opts = FilterOptions(until=until)
        filtered = apply_filters(self.result, opts)
        for entry in filtered.entries:
            if entry.timestamp:
                assert entry.timestamp <= until

    def test_combined_range(self):
        since = datetime(2024, 3, 15, 10, 0, 5)
        until = datetime(2024, 3, 15, 10, 0, 12)
        opts = FilterOptions(since=since, until=until)
        filtered = apply_filters(self.result, opts)
        for entry in filtered.entries:
            if entry.timestamp:
                assert since <= entry.timestamp <= until

    def test_entries_without_timestamps_pass_through(self):
        result = LogParser().parse(SAMPLES / "no_header.log")
        since = datetime(2024, 3, 15, 10, 0, 5)
        opts = FilterOptions(since=since)
        filtered = apply_filters(result, opts)
        no_ts = [e for e in filtered.entries if e.timestamp is None]
        # Continuation lines have no timestamp — they should still be present
        assert len(no_ts) > 0

    def test_finalize_called(self):
        opts = FilterOptions(min_severity="error")
        filtered = apply_filters(self.result, opts)
        # finalize() sets errors/warnings lists
        assert filtered.errors == [e for e in filtered.entries if e.is_error]


class TestCombinedFilters:
    def test_severity_and_category(self):
        result = parse("comprehensive.log")
        opts = FilterOptions(min_severity="error", categories=["LogEngine"])
        filtered = apply_filters(result, opts)
        for entry in filtered.entries:
            assert entry.category.lower() == "logengine"
            assert entry.verbosity in (Verbosity.ERROR, Verbosity.FATAL)


class TestParseTimestampArg:
    def test_full_ue_format(self):
        dt = parse_timestamp_arg("2024.03.15-12.34.56")
        assert dt is not None
        assert dt.year == 2024
        assert dt.hour == 12
        assert dt.minute == 34

    def test_time_only_colon(self):
        dt = parse_timestamp_arg("12:34:56")
        assert dt is not None
        assert dt.hour == 12
        assert dt.minute == 34
        assert dt.second == 56

    def test_time_only_dot(self):
        dt = parse_timestamp_arg("12.34.56")
        assert dt is not None
        assert dt.hour == 12

    def test_invalid_returns_none(self):
        dt = parse_timestamp_arg("not-a-time")
        assert dt is None

    def test_full_ue_with_ms(self):
        dt = parse_timestamp_arg("2024.03.15-12.34.56:789")
        assert dt is not None
        assert dt.second == 56


class TestProgressCallback:
    def test_progress_fn_called(self):
        called_with = []
        def on_progress(n):
            called_with.append(n)

        result = LogParser().parse(
            SAMPLES / "comprehensive.log",
            progress_fn=on_progress,
        )
        # Should be called at least once at EOF
        assert len(called_with) >= 1
        # Last call should equal total_lines
        assert called_with[-1] == result.total_lines
