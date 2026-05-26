# UE Log Analyzer — Project Plan

## Overview

A desktop/CLI tool that ingests Unreal Engine log files (`.log`) and produces a structured, human-readable analysis report covering errors, warnings, performance issues, crashes, asset problems, and more.

---

## Goals

- Parse the full UE log from top to bottom without losing context
- Categorize and surface every meaningful event (not just errors)
- Provide a severity-ranked summary at the top, then a detailed section-by-section breakdown
- Support both a CLI output and an optional HTML/JSON report export
- Be fast enough to handle large logs (100k+ lines)

---

## UE Log Format Primer

A standard UE log line looks like:

```
[2024.03.15-12.34.56:789][  0]LogInit: Display: Loading project...
[2024.03.15-12.34.56:789][  0]LogEngine: Error: Asset '/Game/Foo' failed to load
```

Fields:
- `[timestamp]` — wall-clock time
- `[frame]` — engine frame number (0 before game loop starts)
- `LogCategory` — subsystem that emitted the line (e.g. `LogEngine`, `LogShaders`)
- `Verbosity` — `Display`, `Warning`, `Error`, `Fatal`, `Verbose`, `VeryVerbose` (may be omitted for Display)
- `Message` — free-form text

Special patterns:
- **Crash callstacks** — multi-line blocks starting with `Unhandled Exception` or `Fatal error`
- **Assertion failures** — lines containing `Assertion failed:`
- **Shader compilation** — `LogShaderCompilers` lines with compile times
- **Package/asset loads** — `LogUObjectGlobals`, `LogPackageLocalizationCache`
- **Memory** — `LogMemory`, heap stats dumps
- **RHI/GPU** — `LogRHI`, `LogD3D11RHI`, driver messages
- **PIE events** — `Play in editor started / ended`
- **Network** — `LogNet`, `LogNetTraffic`

---

## Architecture

```
ue-log-analyzer/
├── src/
│   ├── main.py               # CLI entry point
│   ├── parser.py             # Line-by-line log parser / tokenizer
│   ├── models.py             # Data classes: LogEntry, Event, CrashBlock, etc.
│   ├── analyzers/
│   │   ├── __init__.py
│   │   ├── crash.py          # Crash / Fatal / callstack detection
│   │   ├── errors.py         # Error & Warning aggregation
│   │   ├── assets.py         # Asset load failures, missing references
│   │   ├── shaders.py        # Shader compile errors & slow compiles
│   │   ├── performance.py    # Frame hitches, long GC pauses, memory spikes
│   │   ├── network.py        # Net errors, connection drops
│   │   └── timeline.py       # Chronological event timeline builder
│   ├── report/
│   │   ├── console.py        # Rich terminal output (colored, sectioned)
│   │   ├── html.py           # Self-contained HTML report
│   │   └── json_export.py    # Machine-readable JSON
│   └── utils.py              # Regex helpers, timestamp parsing
├── tests/
│   ├── sample_logs/          # Anonymized UE log snippets for testing
│   └── test_parser.py
├── requirements.txt
└── README.md
```

---

## Implementation Phases

### Phase 1 — Parser & Core Models
- [ ] Define `LogEntry` dataclass (timestamp, frame, category, verbosity, message, line_number)
- [ ] Write regex-based line parser; handle multi-line crash blocks as a single event
- [ ] Handle edge cases: lines without timestamps (continued messages), UTF-8 BOM, Windows line endings
- [ ] Unit tests against real sample log snippets

### Phase 2 — Analyzers
- [ ] **Crash analyzer**: detect `Fatal error`, `Assertion failed`, `Unhandled Exception`; capture full callstack
- [ ] **Error/Warning analyzer**: aggregate by category + message template (deduplicate repeated spew)
- [ ] **Asset analyzer**: detect load failures, cook errors, missing package refs
- [ ] **Shader analyzer**: compile errors, shaders that took > threshold ms
- [ ] **Performance analyzer**: detect hitches (frame time > threshold), GC full purge events, OOM warnings
- [ ] **Network analyzer**: net errors, packet loss warnings, connection timeouts
- [ ] **Timeline builder**: ordered list of significant events with timestamps

### Phase 3 — Report Generation
- [ ] **Console report**: colored sections using `rich` library
  - Executive summary (crash? Y/N, error count, warning count, top issues)
  - Crash section (callstack + surrounding context)
  - Errors (grouped by category, top 10 most frequent)
  - Warnings (grouped, top 10)
  - Asset issues
  - Shader issues
  - Performance notes
  - Network notes
  - Full timeline
- [ ] **HTML report**: same structure, self-contained single file, collapsible sections
- [ ] **JSON export**: raw structured data for downstream tooling

### Phase 4 — CLI & UX Polish
- [ ] `analyze <log_file> [--output html|json|console] [--out-file path]`
- [ ] `--severity` filter (show only errors, or errors+warnings)
- [ ] `--category` filter (only show specific log categories)
- [ ] `--since` / `--until` timestamp range filtering
- [ ] Progress bar for large files
- [ ] Drag-and-drop friendly (accept path as first positional arg)

### Phase 5 — Stretch Goals
- [ ] Watch mode (`--watch`): tail a live log and update analysis in real time
- [ ] Diff mode: compare two logs (e.g. before/after a fix) and highlight new issues
- [ ] VS Code extension wrapper
- [ ] Config file (`.ue-log-analyzer.toml`) for custom thresholds and category aliases

---

## Key Dependencies

| Package | Purpose |
|---|---|
| `rich` | Colored, formatted terminal output |
| `click` | CLI argument parsing |
| `jinja2` | HTML report templating |
| `dataclasses` / `pydantic` | Typed data models |
| `pytest` | Testing |

Python 3.10+ (uses `match` for verbosity dispatch).

---

## Analysis Output Structure

```
═══════════════════════════════════════════
  UE LOG ANALYSIS — MyProject.log
  Lines parsed: 142,837 | Duration: 00:04:32
═══════════════════════════════════════════

SUMMARY
  Crash detected:        YES (Fatal error @ frame 1842)
  Errors:                47  (12 unique)
  Warnings:              312 (38 unique)
  Asset failures:        5
  Shader compile errors: 2
  Frame hitches (>33ms): 8

CRASH
  Frame 1842 | 12:34:56.789
  Fatal error: [Assertion failed: IsValid(Component)]
  File: D:/Build/.../ActorComponent.cpp:412
  Callstack:
    0x00007ff... UActorComponent::RegisterComponent()
    ...
  Context (±10 lines): [shown]

ERRORS (top 10 by frequency)
  [LogUObjectGlobals] x23  Failed to find object '/Game/BP_Enemy.BP_Enemy_C'
  [LogEngine]         x11  Couldn't load package ...
  ...

... (etc.)
```

---

## Development Order

1. Set up repo + `requirements.txt` + basic CLI skeleton
2. Parser + models with unit tests
3. Crash + Error analyzers (highest value)
4. Console report
5. Asset + Shader + Performance analyzers
6. HTML + JSON reports
7. Polish CLI flags
8. Stretch goals as time permits
