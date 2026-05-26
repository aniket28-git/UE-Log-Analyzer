from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config, AnalyzerConfig, CONFIG_FILENAME


class TestLoadConfigDefaults:
    def test_no_file_returns_defaults(self, tmp_path):
        cfg = load_config(tmp_path)
        assert cfg.hitch_threshold_ms == 33.0
        assert cfg.shader_threshold_ms == 1000
        assert cfg.default_output == "console"
        assert cfg.default_severity == "all"
        assert cfg.category_aliases == {}

    def test_returns_analyzer_config_instance(self, tmp_path):
        assert isinstance(load_config(tmp_path), AnalyzerConfig)


class TestLoadConfigThresholds:
    def test_hitch_threshold(self, tmp_path):
        (tmp_path / CONFIG_FILENAME).write_text("[thresholds]\nhitch_ms = 50.0\n")
        cfg = load_config(tmp_path)
        assert cfg.hitch_threshold_ms == 50.0

    def test_shader_threshold(self, tmp_path):
        (tmp_path / CONFIG_FILENAME).write_text("[thresholds]\nshader_ms = 2000\n")
        cfg = load_config(tmp_path)
        assert cfg.shader_threshold_ms == 2000

    def test_both_thresholds(self, tmp_path):
        (tmp_path / CONFIG_FILENAME).write_text(
            "[thresholds]\nhitch_ms = 100.0\nshader_ms = 3000\n"
        )
        cfg = load_config(tmp_path)
        assert cfg.hitch_threshold_ms == 100.0
        assert cfg.shader_threshold_ms == 3000

    def test_partial_thresholds_preserves_defaults(self, tmp_path):
        (tmp_path / CONFIG_FILENAME).write_text("[thresholds]\nhitch_ms = 20.0\n")
        cfg = load_config(tmp_path)
        assert cfg.hitch_threshold_ms == 20.0
        assert cfg.shader_threshold_ms == 1000  # default preserved


class TestLoadConfigDefaults:
    def test_output_default(self, tmp_path):
        (tmp_path / CONFIG_FILENAME).write_text("[defaults]\noutput = 'html'\n")
        cfg = load_config(tmp_path)
        assert cfg.default_output == "html"

    def test_severity_default(self, tmp_path):
        (tmp_path / CONFIG_FILENAME).write_text("[defaults]\nseverity = 'error'\n")
        cfg = load_config(tmp_path)
        assert cfg.default_severity == "error"


class TestLoadConfigCategoryAliases:
    def test_aliases_loaded(self, tmp_path):
        (tmp_path / CONFIG_FILENAME).write_text(
            '[categories]\n[categories.aliases]\ngame = ["LogGame", "LogGameMode"]\n'
        )
        cfg = load_config(tmp_path)
        assert "game" in cfg.category_aliases
        assert cfg.category_aliases["game"] == ["LogGame", "LogGameMode"]

    def test_multiple_aliases(self, tmp_path):
        (tmp_path / CONFIG_FILENAME).write_text(
            '[categories]\n[categories.aliases]\n'
            'net = ["LogNet", "LogNetTraffic"]\n'
            'render = ["LogRHI", "LogD3D11RHI"]\n'
        )
        cfg = load_config(tmp_path)
        assert "net" in cfg.category_aliases
        assert "render" in cfg.category_aliases


class TestLoadConfigParentWalk:
    def test_walks_parent_dirs(self, tmp_path):
        (tmp_path / CONFIG_FILENAME).write_text("[thresholds]\nhitch_ms = 99.0\n")
        subdir = tmp_path / "sub" / "dir"
        subdir.mkdir(parents=True)
        cfg = load_config(subdir)
        assert cfg.hitch_threshold_ms == 99.0

    def test_stops_at_nearest_config(self, tmp_path):
        (tmp_path / CONFIG_FILENAME).write_text("[thresholds]\nhitch_ms = 10.0\n")
        subdir = tmp_path / "sub"
        subdir.mkdir()
        (subdir / CONFIG_FILENAME).write_text("[thresholds]\nhitch_ms = 50.0\n")
        cfg = load_config(subdir)
        assert cfg.hitch_threshold_ms == 50.0  # nearest wins
