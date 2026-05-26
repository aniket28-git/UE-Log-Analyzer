from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from io import StringIO

from src.parser import LogParser
from src.analyzers.runner import run_all
from src.report.console import ConsoleReport
from src.report.html import HtmlReport
from src.report.json_export import JsonExport

SAMPLES = Path(__file__).parent / "sample_logs"


def make_report(name: str):
    result = LogParser().parse(SAMPLES / name)
    return run_all(result), name


# ── Console Report ────────────────────────────────────────────────────────────

class TestConsoleReport:
    def setup_method(self):
        self.report, self.filename = make_report("comprehensive.log")
        self.crash_report, _ = make_report("crash.log")

    def _capture(self, report, filename=""):
        buf = StringIO()
        console = Console(file=buf, highlight=False, markup=True, no_color=True)
        ConsoleReport(console).render(report, filename)
        return buf.getvalue()

    def test_renders_without_error(self):
        output = self._capture(self.report, "comprehensive.log")
        assert len(output) > 0

    def test_summary_present(self):
        output = self._capture(self.report)
        assert "SUMMARY" in output

    def test_error_count_in_output(self):
        output = self._capture(self.report)
        assert "ERRORS" in output

    def test_warning_section_present(self):
        output = self._capture(self.report)
        assert "WARNINGS" in output

    def test_timeline_present(self):
        output = self._capture(self.report)
        assert "TIMELINE" in output

    def test_crash_section_rendered(self):
        output = self._capture(self.crash_report, "crash.log")
        assert "CRASH" in output

    def test_crash_callstack_in_output(self):
        output = self._capture(self.crash_report)
        assert "callstack" in output.lower() or "UActorComponent" in output or "context" in output.lower()

    def test_asset_section_rendered(self):
        output = self._capture(self.report)
        assert "ASSET" in output

    def test_performance_section_rendered(self):
        output = self._capture(self.report)
        assert "PERFORMANCE" in output

    def test_network_section_rendered(self):
        output = self._capture(self.report)
        assert "NETWORK" in output

    def test_filename_in_header(self):
        output = self._capture(self.report, "myfile.log")
        assert "myfile.log" in output

    def test_clean_log_no_crash_section(self):
        report, _ = make_report("normal.log")
        output = self._capture(report)
        assert "CRASH #1" not in output


# ── HTML Report ───────────────────────────────────────────────────────────────

class TestHtmlReport:
    def setup_method(self):
        self.report, _ = make_report("comprehensive.log")
        self.crash_report, _ = make_report("crash.log")
        self.renderer = HtmlReport()

    def test_produces_html(self):
        html = self.renderer.render(self.report, "comprehensive.log")
        assert html.strip().startswith("<!DOCTYPE html>")

    def test_title_contains_filename(self):
        html = self.renderer.render(self.report, "test_file.log")
        assert "test_file.log" in html

    def test_summary_stats_present(self):
        html = self.renderer.render(self.report)
        assert "Errors" in html
        assert "Warnings" in html
        assert "Crash" in html

    def test_crash_section_in_html(self):
        html = self.renderer.render(self.crash_report, "crash.log")
        assert "Crash" in html
        assert "EXCEPTION_ACCESS_VIOLATION" in html or "Assertion failed" in html

    def test_error_table_populated(self):
        html = self.renderer.render(self.report)
        assert "LogEngine" in html

    def test_asset_section_populated(self):
        html = self.renderer.render(self.report)
        assert "load_failure" in html or "missing_ref" in html

    def test_shader_section_populated(self):
        html = self.renderer.render(self.report)
        assert "compile_error" in html or "slow_compile" in html

    def test_timeline_section_populated(self):
        html = self.renderer.render(self.report)
        assert "Timeline" in html

    def test_html_has_style(self):
        html = self.renderer.render(self.report)
        assert "<style>" in html

    def test_no_unclosed_tags(self):
        html = self.renderer.render(self.report)
        assert html.count("<table") == html.count("</table>")
        assert html.count("<details") == html.count("</details>")

    def test_self_contained(self):
        html = self.renderer.render(self.report)
        # No external src/href references
        assert 'src="http' not in html
        assert "href=\"http" not in html

    def test_empty_sections_omitted(self):
        report, _ = make_report("normal.log")
        html = self.renderer.render(report)
        # normal.log has no crashes — the crash details div should not appear
        assert '<div class="crash-block">' not in html


# ── JSON Export ───────────────────────────────────────────────────────────────

class TestJsonExport:
    def setup_method(self):
        self.report, _ = make_report("comprehensive.log")
        self.crash_report, _ = make_report("crash.log")
        self.exporter = JsonExport()

    def _parse(self, report=None, filename="") -> dict:
        r = report or self.report
        return json.loads(self.exporter.render(r, filename))

    def test_valid_json(self):
        raw = self.exporter.render(self.report)
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_top_level_keys(self):
        data = self._parse()
        for key in ("meta", "summary", "crashes", "errors", "warnings",
                    "assets", "shaders", "performance", "network", "timeline"):
            assert key in data, f"missing key: {key}"

    def test_meta_fields(self):
        data = self._parse(filename="foo.log")
        assert data["meta"]["filename"] == "foo.log"
        assert data["meta"]["total_lines"] > 0
        assert "generated_at" in data["meta"]

    def test_summary_fields(self):
        data = self._parse()
        s = data["summary"]
        assert "has_crash" in s
        assert "total_errors" in s
        assert "total_warnings" in s

    def test_no_crash_in_comprehensive(self):
        data = self._parse()
        assert data["summary"]["has_crash"] is False
        assert data["crashes"] == []

    def test_crash_present_in_crash_log(self):
        data = self._parse(self.crash_report)
        assert data["summary"]["has_crash"] is True
        assert len(data["crashes"]) == 1
        crash = data["crashes"][0]
        assert "callstack" in crash
        assert "exception_type" in crash
        assert "source_file" in crash

    def test_errors_are_sorted_by_count(self):
        data = self._parse()
        counts = [e["count"] for e in data["errors"]]
        assert counts == sorted(counts, reverse=True)

    def test_asset_issues_present(self):
        data = self._parse()
        assert len(data["assets"]) >= 3
        for a in data["assets"]:
            assert "kind" in a
            assert "asset_path" in a
            assert "line_number" in a

    def test_timeline_sorted_by_line(self):
        data = self._parse()
        lines = [e["line_number"] for e in data["timeline"]]
        assert lines == sorted(lines)

    def test_timestamps_are_iso(self):
        data = self._parse(self.crash_report)
        for ev in data["timeline"]:
            if ev["timestamp"] is not None:
                # Should parse without error
                from datetime import datetime
                datetime.fromisoformat(ev["timestamp"])
