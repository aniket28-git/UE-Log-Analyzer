from __future__ import annotations
import re
from ..models import ParseResult, Verbosity
from .results import ErrorGroup, ErrorAnalysisResult

_MAX_EXAMPLES = 3

# Normalise the variable parts of a message to produce a stable template key
_NORM_RULES = [
    (re.compile(r"'[^']{3,}'"), "'<PATH>'"),          # quoted paths / names (3+ chars)
    (re.compile(r'"[^"]{3,}"'), '"<STR>"'),             # double-quoted strings
    (re.compile(r"0x[0-9a-fA-F]{4,}"), "0x<ADDR>"),    # hex addresses
    (re.compile(r"\b\d{4,}\b"), "<N>"),                 # long bare numbers (line nums, IDs)
]


def _template(msg: str) -> str:
    for pattern, replacement in _NORM_RULES:
        msg = pattern.sub(replacement, msg)
    return msg.strip()


class ErrorAnalyzer:
    def analyze(self, result: ParseResult) -> ErrorAnalysisResult:
        error_map: dict[tuple[str, str], ErrorGroup] = {}
        warning_map: dict[tuple[str, str], ErrorGroup] = {}

        for entry in result.entries:
            if entry.verbosity not in (Verbosity.ERROR, Verbosity.FATAL, Verbosity.WARNING):
                continue

            tmpl = _template(entry.message)
            key = (entry.category, tmpl)
            target = error_map if entry.is_error else warning_map

            if key not in target:
                target[key] = ErrorGroup(
                    category=entry.category,
                    verbosity=entry.verbosity,
                    template=tmpl,
                    count=0,
                    first_line=entry.line_number,
                )

            g = target[key]
            g.count += 1
            if len(g.examples) < _MAX_EXAMPLES:
                g.examples.append(entry)

        return ErrorAnalysisResult(
            error_groups=sorted(error_map.values(), key=lambda g: -g.count),
            warning_groups=sorted(warning_map.values(), key=lambda g: -g.count),
        )
