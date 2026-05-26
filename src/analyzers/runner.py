from __future__ import annotations
from ..models import ParseResult
from .crash import CrashAnalyzer
from .errors import ErrorAnalyzer
from .assets import AssetAnalyzer
from .shaders import ShaderAnalyzer
from .performance import PerformanceAnalyzer
from .network import NetworkAnalyzer
from .timeline import TimelineBuilder
from .results import AnalysisReport


def run_all(result: ParseResult) -> AnalysisReport:
    crash = CrashAnalyzer().analyze(result)
    errors = ErrorAnalyzer().analyze(result)
    assets = AssetAnalyzer().analyze(result)
    shaders = ShaderAnalyzer().analyze(result)
    performance = PerformanceAnalyzer().analyze(result)
    network = NetworkAnalyzer().analyze(result)

    report = AnalysisReport(
        parse_result=result,
        crash=crash,
        errors=errors,
        assets=assets,
        shaders=shaders,
        performance=performance,
        network=network,
    )

    report.timeline = TimelineBuilder().build(result, report)
    return report
