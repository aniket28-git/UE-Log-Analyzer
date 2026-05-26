from __future__ import annotations
from datetime import datetime
from jinja2 import Environment, BaseLoader
from ..analyzers.results import AnalysisReport

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>UE Log Analysis{% if filename %} — {{ filename }}{% endif %}</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1117; color: #c9d1d9; font-size: 14px; line-height: 1.5; padding: 24px; }
  h1 { font-size: 1.4rem; color: #58a6ff; margin-bottom: 4px; }
  .meta { color: #8b949e; font-size: 12px; margin-bottom: 24px; }

  /* summary grid */
  .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }
  .stat-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; }
  .stat-card .label { font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: .05em; }
  .stat-card .value { font-size: 1.6rem; font-weight: 700; margin-top: 2px; }
  .v-ok    { color: #3fb950; }
  .v-warn  { color: #d29922; }
  .v-error { color: #f85149; }
  .v-fatal { color: #ff7b72; }
  .v-info  { color: #c9d1d9; }

  /* collapsible sections */
  details { background: #161b22; border: 1px solid #30363d; border-radius: 8px; margin-bottom: 16px; overflow: hidden; }
  details > summary { cursor: pointer; padding: 12px 16px; font-weight: 600; font-size: .95rem; list-style: none; display: flex; align-items: center; gap: 8px; user-select: none; }
  details > summary::before { content: '▶'; font-size: .7rem; color: #8b949e; transition: transform .15s; }
  details[open] > summary::before { transform: rotate(90deg); }
  details > summary:hover { background: #1c2128; }
  .section-body { padding: 0 16px 16px; }
  .badge { display: inline-block; border-radius: 12px; padding: 1px 8px; font-size: 11px; font-weight: 600; margin-left: 8px; }
  .badge-red    { background: #3d1a1a; color: #f85149; }
  .badge-yellow { background: #2d2108; color: #d29922; }
  .badge-blue   { background: #0c2034; color: #58a6ff; }
  .badge-green  { background: #0d2114; color: #3fb950; }

  /* tables */
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; padding: 8px 10px; border-bottom: 1px solid #30363d; color: #8b949e; font-weight: 600; font-size: 11px; text-transform: uppercase; }
  td { padding: 6px 10px; border-bottom: 1px solid #21262d; vertical-align: top; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #1c2128; }
  .num { font-variant-numeric: tabular-nums; text-align: right; color: #8b949e; font-size: 12px; }
  .mono { font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 12px; }
  .sev-fatal   { color: #ff7b72; font-weight: 600; }
  .sev-error   { color: #f85149; }
  .sev-warning { color: #d29922; }
  .sev-info    { color: #8b949e; }

  /* crash block */
  .crash-block { background: #1a0d0d; border: 1px solid #6e1b1b; border-radius: 6px; padding: 14px; margin-bottom: 12px; }
  .crash-trigger { color: #ff7b72; font-weight: 600; font-size: 13px; margin-bottom: 8px; }
  .crash-meta span { color: #8b949e; font-size: 12px; margin-right: 16px; }
  .crash-meta span b { color: #c9d1d9; }
  .callstack { margin-top: 10px; background: #0d1117; border-radius: 4px; padding: 10px; max-height: 260px; overflow-y: auto; }
  .callstack pre { font-family: 'Cascadia Code','Consolas',monospace; font-size: 11px; color: #8b949e; white-space: pre-wrap; word-break: break-all; }
  .context-lines { margin-top: 8px; }
  .ctx-line { font-family: 'Cascadia Code','Consolas',monospace; font-size: 11px; color: #8b949e; padding: 1px 0; }
  .ctx-line .lnum { display: inline-block; width: 52px; text-align: right; color: #3c444d; margin-right: 8px; }

  /* kind pills */
  .kind { display: inline-block; border-radius: 4px; padding: 1px 6px; font-size: 11px; background: #21262d; color: #8b949e; }
</style>
</head>
<body>

<h1>UE Log Analysis{% if filename %} — <span style="color:#c9d1d9">{{ filename }}</span>{% endif %}</h1>
<p class="meta">Generated {{ generated_at }}  |  {{ total_lines | format_num }} lines parsed</p>

<!-- ── SUMMARY ────────────────────────────────────────────── -->
<div class="summary-grid">
  <div class="stat-card">
    <div class="label">Crash</div>
    <div class="value {{ 'v-fatal' if has_crash else 'v-ok' }}">{{ 'YES' if has_crash else 'NO' }}</div>
  </div>
  <div class="stat-card">
    <div class="label">Errors</div>
    <div class="value {{ 'v-error' if total_errors else 'v-ok' }}">{{ total_errors }}</div>
  </div>
  <div class="stat-card">
    <div class="label">Warnings</div>
    <div class="value {{ 'v-warn' if total_warnings else 'v-ok' }}">{{ total_warnings }}</div>
  </div>
  <div class="stat-card">
    <div class="label">Asset Issues</div>
    <div class="value {{ 'v-warn' if asset_issues else 'v-ok' }}">{{ asset_issues }}</div>
  </div>
  <div class="stat-card">
    <div class="label">Shader Issues</div>
    <div class="value {{ 'v-warn' if shader_issues else 'v-ok' }}">{{ shader_issues }}</div>
  </div>
  <div class="stat-card">
    <div class="label">Hitches &gt;33ms</div>
    <div class="value {{ 'v-warn' if hitch_count else 'v-ok' }}">{{ hitch_count }}</div>
  </div>
  <div class="stat-card">
    <div class="label">GC Purges</div>
    <div class="value v-info">{{ gc_purges }}</div>
  </div>
  <div class="stat-card">
    <div class="label">Network Events</div>
    <div class="value v-info">{{ net_events }}</div>
  </div>
</div>

<!-- ── CRASH ──────────────────────────────────────────────── -->
{% if crashes %}
<details open>
  <summary class="sev-fatal">Crash <span class="badge badge-red">{{ crashes | length }}</span></summary>
  <div class="section-body">
  {% for c in crashes %}
    <div class="crash-block">
      <div class="crash-trigger">{{ c.summary | e }}</div>
      <div class="crash-meta">
        <span>Line <b>{{ c.line_number }}</b></span>
        <span>Frame <b>{{ c.frame }}</b></span>
        {% if c.exception_type %}<span>Exception <b>{{ c.exception_type | e }}</b></span>{% endif %}
        {% if c.source_file %}<span>Source <b>{{ c.source_file | e }}:{{ c.source_line }}</b></span>{% endif %}
      </div>
      {% if c.context_before %}
      <div class="context-lines" style="margin-top:8px">
        <div style="font-size:11px;color:#3c444d;margin-bottom:2px">context before</div>
        {% for ln in c.context_before %}<div class="ctx-line"><span class="lnum">{{ ln.line_number }}</span>{{ ln.message | e | truncate(120, True) }}</div>{% endfor %}
      </div>
      {% endif %}
      {% if c.callstack %}
      <div class="callstack"><pre>{{ c.callstack | join('\n') | e }}</pre></div>
      {% endif %}
    </div>
  {% endfor %}
  </div>
</details>
{% endif %}

<!-- ── ERRORS ─────────────────────────────────────────────── -->
{% if error_groups %}
<details {{ 'open' if has_crash else '' }}>
  <summary class="sev-error">Errors <span class="badge badge-red">{{ total_errors }}</span></summary>
  <div class="section-body">
  <table>
    <thead><tr><th>Count</th><th>Category</th><th>Message Template</th><th class="num">First Line</th></tr></thead>
    <tbody>
    {% for g in error_groups %}
    <tr>
      <td class="num" style="color:#f85149;font-weight:700">{{ g.count }}</td>
      <td class="mono">{{ g.category | e }}</td>
      <td class="mono">{{ g.template | e | truncate(100, True) }}</td>
      <td class="num">{{ g.first_line }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
</details>
{% endif %}

<!-- ── WARNINGS ───────────────────────────────────────────── -->
{% if warning_groups %}
<details>
  <summary class="sev-warning">Warnings <span class="badge badge-yellow">{{ total_warnings }}</span></summary>
  <div class="section-body">
  <table>
    <thead><tr><th>Count</th><th>Category</th><th>Message Template</th><th class="num">First Line</th></tr></thead>
    <tbody>
    {% for g in warning_groups %}
    <tr>
      <td class="num" style="color:#d29922;font-weight:700">{{ g.count }}</td>
      <td class="mono">{{ g.category | e }}</td>
      <td class="mono">{{ g.template | e | truncate(100, True) }}</td>
      <td class="num">{{ g.first_line }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
</details>
{% endif %}

<!-- ── ASSETS ─────────────────────────────────────────────── -->
{% if assets %}
<details>
  <summary class="sev-warning">Asset Issues <span class="badge badge-yellow">{{ assets | length }}</span></summary>
  <div class="section-body">
  <table>
    <thead><tr><th>Kind</th><th>Asset Path</th><th class="num">Line</th></tr></thead>
    <tbody>
    {% for a in assets %}
    <tr>
      <td><span class="kind {{ 'sev-error' if a.kind in ('load_failure','cook_error') else 'sev-warning' }}">{{ a.kind }}</span></td>
      <td class="mono">{{ a.asset_path | e }}</td>
      <td class="num">{{ a.line_number }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
</details>
{% endif %}

<!-- ── SHADERS ────────────────────────────────────────────── -->
{% if shaders %}
<details>
  <summary class="sev-warning">Shader Issues <span class="badge badge-yellow">{{ shaders | length }}</span></summary>
  <div class="section-body">
  <table>
    <thead><tr><th>Kind</th><th>Message</th><th class="num">ms</th><th class="num">Line</th></tr></thead>
    <tbody>
    {% for s in shaders %}
    <tr>
      <td><span class="kind {{ 'sev-error' if s.kind == 'compile_error' else 'sev-warning' }}">{{ s.kind }}</span></td>
      <td class="mono">{{ s.message | e | truncate(90, True) }}</td>
      <td class="num">{{ s.compile_time_ms if s.compile_time_ms else '—' }}</td>
      <td class="num">{{ s.line_number }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
</details>
{% endif %}

<!-- ── PERFORMANCE ────────────────────────────────────────── -->
{% if perf_events %}
<details>
  <summary class="sev-warning">Performance <span class="badge badge-yellow">{{ perf_events | length }}</span></summary>
  <div class="section-body">
  <table>
    <thead><tr><th>Kind</th><th>Description</th><th class="num">ms</th><th class="num">Line</th></tr></thead>
    <tbody>
    {% for p in perf_events %}
    <tr>
      <td><span class="kind {{ 'sev-error' if p.kind == 'oom_warning' else 'sev-warning' }}">{{ p.kind }}</span></td>
      <td>{{ p.description | e | truncate(90, True) }}</td>
      <td class="num">{{ '%.1f' | format(p.value_ms) if p.value_ms is not none else '—' }}</td>
      <td class="num">{{ p.line_number }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
</details>
{% endif %}

<!-- ── NETWORK ────────────────────────────────────────────── -->
{% if net_events_list %}
<details>
  <summary class="sev-warning">Network <span class="badge badge-yellow">{{ net_events_list | length }}</span></summary>
  <div class="section-body">
  <table>
    <thead><tr><th>Kind</th><th>Description</th><th class="num">Line</th></tr></thead>
    <tbody>
    {% for n in net_events_list %}
    <tr>
      <td><span class="kind {{ 'sev-error' if n.kind == 'error' else 'sev-warning' }}">{{ n.kind }}</span></td>
      <td>{{ n.description | e | truncate(100, True) }}</td>
      <td class="num">{{ n.line_number }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
</details>
{% endif %}

<!-- ── TIMELINE ───────────────────────────────────────────── -->
{% if timeline %}
<details>
  <summary style="color:#58a6ff">Timeline <span class="badge badge-blue">{{ timeline | length }}</span></summary>
  <div class="section-body">
  <table>
    <thead><tr><th class="num">Line</th><th>Severity</th><th>Kind</th><th>Description</th><th class="num">Frame</th></tr></thead>
    <tbody>
    {% for ev in timeline %}
    <tr>
      <td class="num">{{ ev.line_number }}</td>
      <td class="sev-{{ ev.severity }}">{{ ev.severity | upper }}</td>
      <td><span class="kind">{{ ev.kind }}</span></td>
      <td class="mono">{{ ev.description | e | truncate(100, True) }}</td>
      <td class="num">{{ ev.frame if ev.frame is not none else '—' }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
</details>
{% endif %}

</body>
</html>
"""


def _format_num(value: int) -> str:
    return f"{value:,}"


class HtmlReport:
    def __init__(self) -> None:
        self._env = Environment(loader=BaseLoader(), autoescape=False)
        self._env.filters["format_num"] = _format_num
        self._tmpl = self._env.from_string(_TEMPLATE)

    def render(self, report: AnalysisReport, filename: str = "") -> str:
        pr = report.parse_result

        crashes_ctx = []
        for d in report.crash.details:
            cb = d.block
            crashes_ctx.append({
                "summary": cb.summary,
                "line_number": cb.line_number,
                "frame": cb.trigger_entry.frame,
                "exception_type": d.exception_type,
                "source_file": d.source_file,
                "source_line": d.source_line,
                "context_before": cb.context_before[-5:],
                "callstack": cb.callstack_lines[:30],
            })

        shaders_ctx = [
            {
                "kind": i.kind,
                "message": i.message,
                "compile_time_ms": i.compile_time_ms,
                "line_number": i.entry.line_number,
            }
            for i in report.shaders.issues
        ]

        perf_ctx = [
            {
                "kind": ev.kind,
                "description": ev.description,
                "value_ms": ev.value_ms,
                "line_number": ev.entry.line_number,
            }
            for ev in report.performance.events
        ]

        net_ctx = [
            {
                "kind": ev.kind,
                "description": ev.description,
                "line_number": ev.entry.line_number,
            }
            for ev in report.network.events
        ]

        timeline_ctx = [
            {
                "line_number": ev.line_number,
                "severity": ev.severity,
                "kind": ev.kind,
                "description": ev.description,
                "frame": ev.frame,
                "timestamp": ev.timestamp.strftime("%H:%M:%S") if ev.timestamp else None,
            }
            for ev in report.timeline
        ]

        return self._tmpl.render(
            filename=filename,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_lines=pr.total_lines,
            has_crash=report.has_crash,
            total_errors=report.errors.total_errors,
            total_warnings=report.errors.total_warnings,
            asset_issues=report.assets.total,
            shader_issues=len(report.shaders.issues),
            hitch_count=report.performance.hitch_count,
            gc_purges=report.performance.gc_purge_count,
            net_events=len(report.network.events),
            crashes=crashes_ctx,
            error_groups=report.errors.error_groups[:10],
            warning_groups=report.errors.warning_groups[:10],
            assets=[
                {"kind": i.kind, "asset_path": i.asset_path, "line_number": i.entry.line_number}
                for i in report.assets.issues
            ],
            shaders=shaders_ctx,
            perf_events=perf_ctx,
            net_events_list=net_ctx,
            timeline=timeline_ctx,
        )
