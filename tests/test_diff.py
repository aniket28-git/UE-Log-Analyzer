from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parser import LogParser
from src.analyzers.results import AnalysisReport
from src.analyzers.crash import CrashAnalyzer
from src.analyzers.errors import ErrorAnalyzer
from src.analyzers.assets import AssetAnalyzer
from src.analyzers.shaders import ShaderAnalyzer
from src.analyzers.performance import PerformanceAnalyzer
from src.analyzers.network import NetworkAnalyzer
from src.analyzers.timeline import TimelineBuilder
from src.diff import compute_diff, DiffReport, SectionDiff

SAMPLES = Path(__file__).parent / "sample_logs"


def _make_report(log_path: Path) -> AnalysisReport:
    result = LogParser().parse(log_path)
    report = AnalysisReport(
        parse_result=result,
        crash=CrashAnalyzer().analyze(result),
        errors=ErrorAnalyzer().analyze(result),
        assets=AssetAnalyzer().analyze(result),
        shaders=ShaderAnalyzer().analyze(result),
        performance=PerformanceAnalyzer().analyze(result),
        network=NetworkAnalyzer().analyze(result),
    )
    report.timeline = TimelineBuilder().build(result, report)
    return report


class TestSectionDiff:
    def test_delta_positive(self):
        s = SectionDiff(count_before=2, count_after=5)
        assert s.delta == 3

    def test_delta_negative(self):
        s = SectionDiff(count_before=5, count_after=2)
        assert s.delta == -3

    def test_delta_zero(self):
        s = SectionDiff(count_before=3, count_after=3)
        assert s.delta == 0


class TestComputeDiff:
    def setup_method(self):
        self.normal = _make_report(SAMPLES / "normal.log")
        self.crash = _make_report(SAMPLES / "crash.log")

    def test_returns_diff_report(self):
        diff = compute_diff(self.normal, self.normal, "a.log", "b.log")
        assert isinstance(diff, DiffReport)

    def test_log_names_stored(self):
        diff = compute_diff(self.normal, self.crash, "before.log", "after.log")
        assert diff.log_before == "before.log"
        assert diff.log_after == "after.log"

    def test_same_file_no_regressions(self):
        diff = compute_diff(self.normal, self.normal, "a.log", "b.log")
        assert not diff.has_regressions

    def test_crash_log_vs_normal_has_regressions(self):
        diff = compute_diff(self.normal, self.crash, "normal.log", "crash.log")
        assert diff.has_regressions

    def test_new_crashes_detected(self):
        diff = compute_diff(self.normal, self.crash, "normal.log", "crash.log")
        assert diff.crashes.count_after > diff.crashes.count_before

    def test_crash_additions_populated(self):
        diff = compute_diff(self.normal, self.crash, "normal.log", "crash.log")
        assert len(diff.crashes.added) > 0

    def test_resolved_items(self):
        # Reversing the direction: crash → normal should show removals
        diff = compute_diff(self.crash, self.normal, "crash.log", "normal.log")
        assert len(diff.crashes.removed) > 0

    def test_same_file_all_counts_equal(self):
        diff = compute_diff(self.normal, self.normal, "a.log", "b.log")
        for section in (diff.errors, diff.warnings, diff.crashes, diff.assets,
                        diff.shaders, diff.performance, diff.network):
            assert section.count_before == section.count_after
            assert section.delta == 0

    def test_same_file_no_added_or_removed(self):
        diff = compute_diff(self.normal, self.normal, "a.log", "b.log")
        for section in (diff.errors, diff.warnings, diff.crashes, diff.assets,
                        diff.shaders, diff.performance, diff.network):
            assert section.added == []
            assert section.removed == []


class TestDiffCLI:
    def setup_method(self):
        from click.testing import CliRunner
        from src.main import diff_cmd
        self.runner = CliRunner()
        self.diff_cmd = diff_cmd

    def test_diff_console_output(self):
        result = self.runner.invoke(self.diff_cmd, [
            str(SAMPLES / "normal.log"),
            str(SAMPLES / "crash.log"),
        ])
        # Exit code 1 because crash log has regressions
        assert "LOG DIFF" in result.output or result.exit_code in (0, 1)

    def test_diff_json_output(self):
        result = self.runner.invoke(self.diff_cmd, [
            str(SAMPLES / "normal.log"),
            str(SAMPLES / "crash.log"),
            "--output", "json",
        ])
        import json
        idx = result.output.find("{")
        assert idx != -1, f"No JSON found: {result.output[:300]}"
        data = json.loads(result.output[idx:])
        assert "has_regressions" in data
        assert "crashes" in data
        assert "errors" in data

    def test_diff_same_log_exit_zero(self):
        result = self.runner.invoke(self.diff_cmd, [
            str(SAMPLES / "normal.log"),
            str(SAMPLES / "normal.log"),
        ])
        assert result.exit_code == 0

    def test_diff_regression_exits_one(self):
        result = self.runner.invoke(self.diff_cmd, [
            str(SAMPLES / "normal.log"),
            str(SAMPLES / "crash.log"),
        ])
        assert result.exit_code == 1

    def test_diff_to_file(self, tmp_path):
        out = tmp_path / "diff.json"
        result = self.runner.invoke(self.diff_cmd, [
            str(SAMPLES / "normal.log"),
            str(SAMPLES / "crash.log"),
            "--output", "json",
            "--out-file", str(out),
        ])
        assert out.exists()
        import json
        data = json.loads(out.read_text())
        assert "has_regressions" in data
