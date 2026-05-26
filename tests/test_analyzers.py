from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parser import LogParser
from src.analyzers.runner import run_all
from src.analyzers.crash import CrashAnalyzer
from src.analyzers.errors import ErrorAnalyzer
from src.analyzers.assets import AssetAnalyzer
from src.analyzers.shaders import ShaderAnalyzer
from src.analyzers.performance import PerformanceAnalyzer
from src.analyzers.network import NetworkAnalyzer

SAMPLES = Path(__file__).parent / "sample_logs"


def parse(name: str):
    return LogParser().parse(SAMPLES / name)


# ── Crash Analyzer ────────────────────────────────────────────────────────────

class TestCrashAnalyzer:
    def setup_method(self):
        self.result = parse("crash.log")
        self.report = CrashAnalyzer().analyze(self.result)

    def test_has_crash(self):
        assert self.report.has_crash

    def test_one_crash_detail(self):
        assert len(self.report.details) == 1

    def test_exception_type_extracted(self):
        detail = self.report.details[0]
        assert detail.exception_type is not None
        assert "EXCEPTION_ACCESS_VIOLATION" in detail.exception_type or \
               "access violation" in detail.exception_type.lower()

    def test_source_file_extracted(self):
        detail = self.report.details[0]
        assert detail.source_file is not None
        assert detail.source_file == "ActorComponent.cpp"

    def test_source_line_extracted(self):
        detail = self.report.details[0]
        assert detail.source_line == 412

    def test_callstack_depth(self):
        detail = self.report.details[0]
        assert detail.callstack_depth > 0

    def test_no_crash_on_normal_log(self):
        result = parse("normal.log")
        report = CrashAnalyzer().analyze(result)
        assert not report.has_crash


# ── Error Analyzer ────────────────────────────────────────────────────────────

class TestErrorAnalyzer:
    def setup_method(self):
        self.result = parse("comprehensive.log")
        self.report = ErrorAnalyzer().analyze(self.result)

    def test_errors_found(self):
        assert self.report.total_errors >= 2

    def test_warnings_found(self):
        assert self.report.total_warnings >= 3

    def test_deduplication(self):
        # The BP_Enemy warning appears 3 times — should collapse to 1 group with count=3
        enemy_groups = [
            g for g in self.report.warning_groups
            if "BP_Enemy" in g.template or "BP_Enemy" in (g.examples[0].message if g.examples else "")
        ]
        assert len(enemy_groups) == 1
        assert enemy_groups[0].count == 3

    def test_groups_sorted_by_count(self):
        if len(self.report.warning_groups) >= 2:
            counts = [g.count for g in self.report.warning_groups]
            assert counts == sorted(counts, reverse=True)

    def test_examples_capped(self):
        for g in self.report.error_groups + self.report.warning_groups:
            assert len(g.examples) <= 3

    def test_error_group_has_category(self):
        for g in self.report.error_groups:
            assert g.category != ""

    def test_load_failures_as_errors(self):
        categories = {g.category for g in self.report.error_groups}
        assert "LogEngine" in categories


# ── Asset Analyzer ────────────────────────────────────────────────────────────

class TestAssetAnalyzer:
    def setup_method(self):
        self.result = parse("comprehensive.log")
        self.report = AssetAnalyzer().analyze(self.result)

    def test_issues_found(self):
        assert self.report.total >= 3

    def test_missing_ref_detected(self):
        kinds = {i.kind for i in self.report.issues}
        assert "missing_ref" in kinds

    def test_load_failure_detected(self):
        kinds = {i.kind for i in self.report.issues}
        assert "load_failure" in kinds

    def test_deduplication(self):
        # BP_Enemy appears 3 times but should only produce 1 unique issue
        enemy_issues = [i for i in self.report.issues if "BP_Enemy" in i.asset_path]
        assert len(enemy_issues) == 1

    def test_asset_paths_populated(self):
        for issue in self.report.issues:
            assert issue.asset_path != ""

    def test_no_issues_on_clean_log(self):
        result = parse("normal.log")
        report = AssetAnalyzer().analyze(result)
        # normal.log has one "Failed to find object" warning
        assert report.total >= 1


# ── Shader Analyzer ───────────────────────────────────────────────────────────

class TestShaderAnalyzer:
    def setup_method(self):
        self.result = parse("comprehensive.log")
        self.report = ShaderAnalyzer().analyze(self.result)

    def test_compile_error_detected(self):
        assert self.report.compile_errors == 1

    def test_slow_compile_detected(self):
        # 2450ms is above 1000ms threshold; 980ms is below
        assert self.report.slow_compiles == 1

    def test_slow_compile_time_recorded(self):
        slow = [i for i in self.report.issues if i.kind == "slow_compile"]
        assert slow[0].compile_time_ms == 2450

    def test_below_threshold_not_included(self):
        # 980ms shader should not appear
        times = [i.compile_time_ms for i in self.report.issues if i.compile_time_ms]
        assert 980 not in times

    def test_custom_threshold(self):
        report = ShaderAnalyzer(slow_threshold_ms=500).analyze(self.result)
        # Both 980ms and 2450ms are above 500ms
        assert report.slow_compiles == 2


# ── Performance Analyzer ──────────────────────────────────────────────────────

class TestPerformanceAnalyzer:
    def setup_method(self):
        self.result = parse("comprehensive.log")
        self.report = PerformanceAnalyzer().analyze(self.result)

    def test_hitches_detected(self):
        # 87ms and 120ms are above 33ms threshold; 15ms is below
        assert self.report.hitch_count == 2

    def test_small_hitch_excluded(self):
        # 15ms hitch should not be included
        hitch_values = [e.value_ms for e in self.report.events if e.kind == "hitch"]
        assert 15.0 not in hitch_values

    def test_gc_purge_detected(self):
        assert self.report.gc_purge_count == 1

    def test_gc_time_recorded(self):
        gc_events = [e for e in self.report.events if e.kind == "gc_purge"]
        assert gc_events[0].value_ms == 45.3

    def test_oom_detected(self):
        oom = [e for e in self.report.events if e.kind == "oom_warning"]
        assert len(oom) == 1

    def test_custom_hitch_threshold(self):
        report = PerformanceAnalyzer(hitch_threshold_ms=100.0).analyze(self.result)
        # Only 120ms is above 100ms
        assert report.hitch_count == 1


# ── Network Analyzer ──────────────────────────────────────────────────────────

class TestNetworkAnalyzer:
    def setup_method(self):
        self.result = parse("comprehensive.log")
        self.report = NetworkAnalyzer().analyze(self.result)

    def test_events_found(self):
        assert len(self.report.events) >= 4

    def test_packet_loss_detected(self):
        kinds = {e.kind for e in self.report.events}
        assert "packet_loss" in kinds

    def test_timeout_detected(self):
        kinds = {e.kind for e in self.report.events}
        assert "timeout" in kinds

    def test_error_detected(self):
        kinds = {e.kind for e in self.report.events}
        assert "error" in kinds

    def test_disconnect_detected(self):
        kinds = {e.kind for e in self.report.events}
        assert "disconnect" in kinds

    def test_non_net_categories_ignored(self):
        non_net = [e for e in self.report.events if e.entry.category not in
                   {"LogNet", "LogNetTraffic", "LogNetDormancy", "LogSockets", "LogOnline", "LogNetPackageMap"}]
        assert len(non_net) == 0


# ── Runner (integration) ──────────────────────────────────────────────────────

class TestRunner:
    def setup_method(self):
        self.result = parse("comprehensive.log")
        self.report = run_all(self.result)

    def test_report_assembled(self):
        assert self.report is not None

    def test_no_crash(self):
        assert not self.report.has_crash

    def test_timeline_populated(self):
        assert len(self.report.timeline) > 0

    def test_timeline_sorted_by_line(self):
        lines = [e.line_number for e in self.report.timeline]
        assert lines == sorted(lines)

    def test_timeline_covers_all_severities(self):
        severities = {e.severity for e in self.report.timeline}
        assert "error" in severities
        assert "warning" in severities

    def test_crash_run_all(self):
        crash_result = parse("crash.log")
        crash_report = run_all(crash_result)
        assert crash_report.has_crash
        assert any(e.kind == "crash" for e in crash_report.timeline)
        crash_events = [e for e in crash_report.timeline if e.kind == "crash"]
        assert crash_events[0].severity == "fatal"
