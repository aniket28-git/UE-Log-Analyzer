from __future__ import annotations
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILENAME = ".ue-log-analyzer.toml"


@dataclass
class AnalyzerConfig:
    hitch_threshold_ms: float = 33.0
    shader_threshold_ms: int = 1000
    category_aliases: dict[str, list[str]] = field(default_factory=dict)
    default_output: str = "console"
    default_severity: str = "all"


def load_config(start_dir: Path | None = None) -> AnalyzerConfig:
    """Walk start_dir and its parents looking for .ue-log-analyzer.toml."""
    search = start_dir or Path.cwd()
    for directory in [search, *search.parents]:
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return _parse(candidate)
    return AnalyzerConfig()


def _parse(path: Path) -> AnalyzerConfig:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    cfg = AnalyzerConfig()
    if (t := data.get("thresholds")):
        if "hitch_ms" in t:
            cfg.hitch_threshold_ms = float(t["hitch_ms"])
        if "shader_ms" in t:
            cfg.shader_threshold_ms = int(t["shader_ms"])
    if (c := data.get("categories")):
        if "aliases" in c:
            cfg.category_aliases = {k: list(v) for k, v in c["aliases"].items()}
    if (d := data.get("defaults")):
        if "output" in d:
            cfg.default_output = str(d["output"])
        if "severity" in d:
            cfg.default_severity = str(d["severity"])
    return cfg
