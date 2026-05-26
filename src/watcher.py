from __future__ import annotations
import time
from pathlib import Path


def poll_until_changed(path: Path, interval: float = 1.0) -> None:
    """Block until path's mtime changes (or it is created), then return."""
    try:
        last = path.stat().st_mtime
    except OSError:
        last = 0.0
    while True:
        time.sleep(interval)
        try:
            current = path.stat().st_mtime
        except OSError:
            continue
        if current != last:
            return
