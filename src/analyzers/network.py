from __future__ import annotations
import re
from ..models import ParseResult
from .results import NetworkEvent, NetworkAnalysisResult

_NET_CATEGORIES = {
    "LogNet", "LogNetTraffic", "LogNetDormancy",
    "LogSockets", "LogOnline", "LogNetPackageMap",
}

# Ordered: first match wins
_KEYWORD_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(packet\s*loss|packetloss)", re.I), "packet_loss"),
    (re.compile(r"(timed?\s*out|timeout)", re.I), "timeout"),
    (re.compile(r"(disconnect|connection\s*(closed|lost|dropped))", re.I), "disconnect"),
    (re.compile(r"(connection\s*(failed|refused|reset))", re.I), "connect_failed"),
    (re.compile(r"(net\s*error|socket\s*error)", re.I), "error"),
]


class NetworkAnalyzer:
    def analyze(self, result: ParseResult) -> NetworkAnalysisResult:
        events: list[NetworkEvent] = []

        for entry in result.entries:
            if entry.category not in _NET_CATEGORIES:
                continue

            if entry.is_error:
                events.append(NetworkEvent(
                    kind="error",
                    description=entry.message[:200],
                    entry=entry,
                ))
                continue

            for pattern, kind in _KEYWORD_PATTERNS:
                if pattern.search(entry.message):
                    events.append(NetworkEvent(
                        kind=kind,
                        description=entry.message[:200],
                        entry=entry,
                    ))
                    break

        return NetworkAnalysisResult(events=events)
