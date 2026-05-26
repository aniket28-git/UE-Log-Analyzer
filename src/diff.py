from __future__ import annotations
from dataclasses import dataclass, field
from .analyzers.results import (
    AnalysisReport, CrashDetail, ErrorGroup, AssetIssue,
    ShaderIssue, PerformanceEvent, NetworkEvent,
)


@dataclass
class SectionDiff:
    added: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    count_before: int = 0
    count_after: int = 0

    @property
    def delta(self) -> int:
        return self.count_after - self.count_before


@dataclass
class DiffReport:
    log_before: str
    log_after: str
    crashes: SectionDiff = field(default_factory=SectionDiff)
    errors: SectionDiff = field(default_factory=SectionDiff)
    warnings: SectionDiff = field(default_factory=SectionDiff)
    assets: SectionDiff = field(default_factory=SectionDiff)
    shaders: SectionDiff = field(default_factory=SectionDiff)
    performance: SectionDiff = field(default_factory=SectionDiff)
    network: SectionDiff = field(default_factory=SectionDiff)

    @property
    def has_regressions(self) -> bool:
        return any(
            s.added for s in (
                self.crashes, self.errors, self.warnings,
                self.assets, self.shaders, self.performance, self.network,
            )
        )


def compute_diff(
    before: AnalysisReport,
    after: AnalysisReport,
    log_before: str,
    log_after: str,
) -> DiffReport:
    dr = DiffReport(log_before=log_before, log_after=log_after)

    def _crash_key(c: CrashDetail) -> str:
        return c.exception_type or c.block.trigger_entry.message

    def _err_key(g: ErrorGroup) -> str:
        return f"{g.category}|{g.template}"

    def _asset_key(a: AssetIssue) -> str:
        return f"{a.kind}|{a.asset_path}"

    def _shader_key(s: ShaderIssue) -> str:
        return f"{s.kind}|{s.message}"

    def _perf_key(e: PerformanceEvent) -> str:
        return f"{e.kind}|{e.description}"

    def _net_key(e: NetworkEvent) -> str:
        return f"{e.kind}|{e.description}"

    _diff_lists(dr.crashes, before.crash.details, after.crash.details, _crash_key)
    _diff_lists(dr.errors, before.errors.error_groups, after.errors.error_groups, _err_key)
    _diff_lists(dr.warnings, before.errors.warning_groups, after.errors.warning_groups, _err_key)
    _diff_lists(dr.assets, before.assets.issues, after.assets.issues, _asset_key)
    _diff_lists(dr.shaders, before.shaders.issues, after.shaders.issues, _shader_key)
    _diff_lists(dr.performance, before.performance.events, after.performance.events, _perf_key)
    _diff_lists(dr.network, before.network.events, after.network.events, _net_key)

    return dr


def _diff_lists(section: SectionDiff, before: list, after: list, key_fn) -> None:
    before_keys = {key_fn(x) for x in before}
    after_keys = {key_fn(x) for x in after}
    section.count_before = len(before)
    section.count_after = len(after)
    section.added = [x for x in after if key_fn(x) not in before_keys]
    section.removed = [x for x in before if key_fn(x) not in after_keys]
