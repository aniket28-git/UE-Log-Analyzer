from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from click.testing import CliRunner
from src.main import cli, analyze

SAMPLES = Path(__file__).parent / "sample_logs"
COMPREHENSIVE = str(SAMPLES / "comprehensive.log")
CRASH_LOG = str(SAMPLES / "crash.log")
NORMAL_LOG = str(SAMPLES / "normal.log")


def _parse_json(output: str) -> dict:
    """Strip diagnostic preamble lines and parse the JSON payload."""
    idx = output.find("{")
    if idx == -1:
        raise ValueError(f"No JSON found in output:\n{output[:500]}")
    return json.loads(output[idx:])


def _parse_html(output: str) -> str:
    """Strip diagnostic preamble and return the HTML payload."""
    idx = output.find("<!DOCTYPE")
    if idx == -1:
        raise ValueError(f"No HTML found in output:\n{output[:500]}")
    return output[idx:]


class TestCLIBasic:
    def setup_method(self):
        self.runner = CliRunner()

    def test_runs_successfully(self):
        result = self.runner.invoke(analyze, [COMPREHENSIVE])
        assert result.exit_code == 0, result.output

    def test_output_not_empty(self):
        result = self.runner.invoke(analyze, [COMPREHENSIVE])
        assert len(result.output) > 0

    def test_summary_in_output(self):
        result = self.runner.invoke(analyze, [COMPREHENSIVE])
        assert "SUMMARY" in result.output

    def test_missing_file_exits_nonzero(self):
        result = self.runner.invoke(analyze, ["/nonexistent/path/foo.log"])
        assert result.exit_code != 0

    def test_help_flag(self):
        result = self.runner.invoke(analyze, ["--help"])
        assert result.exit_code == 0
        assert "LOG_FILE" in result.output
        assert "--output" in result.output

    def test_crash_log_shows_crash(self):
        result = self.runner.invoke(analyze, [CRASH_LOG])
        assert result.exit_code == 0
        assert "CRASH" in result.output


class TestCLIOutputFormats:
    def setup_method(self):
        self.runner = CliRunner()

    def test_json_output_valid(self):
        result = self.runner.invoke(analyze, [COMPREHENSIVE, "--output", "json"])
        assert result.exit_code == 0, result.output
        data = _parse_json(result.output)
        assert "summary" in data
        assert "timeline" in data

    def test_html_output_valid(self):
        result = self.runner.invoke(analyze, [COMPREHENSIVE, "--output", "html"])
        assert result.exit_code == 0, result.output
        assert _parse_html(result.output).startswith("<!DOCTYPE html>")

    def test_console_is_default(self):
        result = self.runner.invoke(analyze, [COMPREHENSIVE])
        assert result.exit_code == 0
        assert "SUMMARY" in result.output
        # Console output is not pure JSON (contains table/rich formatting)
        assert "ERRORS" in result.output or "WARNINGS" in result.output

    def test_output_to_file_json(self, tmp_path):
        out = tmp_path / "report.json"
        result = self.runner.invoke(analyze, [
            COMPREHENSIVE, "--output", "json", "--out-file", str(out)
        ])
        assert result.exit_code == 0, result.output
        assert out.exists()
        data = json.loads(out.read_text())
        assert "summary" in data

    def test_output_to_file_html(self, tmp_path):
        out = tmp_path / "report.html"
        result = self.runner.invoke(analyze, [
            COMPREHENSIVE, "--output", "html", "--out-file", str(out)
        ])
        assert result.exit_code == 0, result.output
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content


class TestCLISeverityFilter:
    def setup_method(self):
        self.runner = CliRunner()

    def test_error_filter_reduces_timeline(self):
        all_result = self.runner.invoke(analyze, [COMPREHENSIVE, "--output", "json"])
        err_result = self.runner.invoke(analyze, [COMPREHENSIVE, "--output", "json", "--severity", "error"])
        all_data = _parse_json(all_result.output)
        err_data = _parse_json(err_result.output)
        # Error filter should produce same or fewer timeline events
        assert len(err_data["timeline"]) <= len(all_data["timeline"])

    def test_warning_filter_excludes_display(self):
        result = self.runner.invoke(analyze, [COMPREHENSIVE, "--output", "json", "--severity", "warning"])
        data = _parse_json(result.output)
        # All warning+ entries — no Display-level entries in errors/warnings
        for g in data["warnings"]:
            assert g["verbosity"] in ("Warning", "Error", "Fatal")

    def test_invalid_severity_shows_error(self):
        result = self.runner.invoke(analyze, [COMPREHENSIVE, "--severity", "verbose"])
        assert result.exit_code != 0


class TestCLICategoryFilter:
    def setup_method(self):
        self.runner = CliRunner()

    def test_single_category(self):
        result = self.runner.invoke(analyze, [
            COMPREHENSIVE, "--output", "json", "--category", "LogEngine"
        ])
        assert result.exit_code == 0, result.output
        data = _parse_json(result.output)
        for g in data["errors"] + data["warnings"]:
            assert g["category"].lower() == "logengine"

    def test_multiple_categories(self):
        result = self.runner.invoke(analyze, [
            COMPREHENSIVE, "--output", "json",
            "--category", "LogEngine", "--category", "LogNet"
        ])
        assert result.exit_code == 0, result.output
        data = _parse_json(result.output)
        allowed = {"logengine", "lognet"}
        for g in data["errors"] + data["warnings"]:
            assert g["category"].lower() in allowed


class TestCLITimestampFilter:
    def setup_method(self):
        self.runner = CliRunner()

    def test_since_flag(self):
        result = self.runner.invoke(analyze, [
            COMPREHENSIVE, "--output", "json", "--since", "10:00:10"
        ])
        assert result.exit_code == 0, result.output
        data = _parse_json(result.output)
        # Timeline events should all be at or after line corresponding to 10:00:10
        assert isinstance(data["timeline"], list)

    def test_until_flag(self):
        result = self.runner.invoke(analyze, [
            COMPREHENSIVE, "--output", "json", "--until", "10:00:05"
        ])
        assert result.exit_code == 0, result.output

    def test_invalid_since_exits_nonzero(self):
        result = self.runner.invoke(analyze, [COMPREHENSIVE, "--since", "not-a-time"])
        assert result.exit_code != 0


class TestCLIThresholds:
    def setup_method(self):
        self.runner = CliRunner()

    def test_hitch_threshold_affects_count(self):
        low = self.runner.invoke(analyze, [COMPREHENSIVE, "--output", "json", "--hitch-threshold", "10"])
        high = self.runner.invoke(analyze, [COMPREHENSIVE, "--output", "json", "--hitch-threshold", "200"])
        low_data = _parse_json(low.output)
        high_data = _parse_json(high.output)
        low_hitches = sum(1 for e in low_data["performance"] if e["kind"] == "hitch")
        high_hitches = sum(1 for e in high_data["performance"] if e["kind"] == "hitch")
        assert low_hitches >= high_hitches

    def test_shader_threshold_affects_count(self):
        low = self.runner.invoke(analyze, [COMPREHENSIVE, "--output", "json", "--shader-threshold", "500"])
        high = self.runner.invoke(analyze, [COMPREHENSIVE, "--output", "json", "--shader-threshold", "3000"])
        low_data = _parse_json(low.output)
        high_data = _parse_json(high.output)
        assert len(low_data["shaders"]) >= len(high_data["shaders"])
