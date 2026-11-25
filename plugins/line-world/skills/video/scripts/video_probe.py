"""Interpret FFprobe duration metadata consistently across delivery checks."""

from __future__ import annotations

from math import isfinite
import re
from typing import Any


def duration_seconds(value: Any) -> float | None:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return seconds if isfinite(seconds) and seconds > 0 else None


def video_duration(stream: dict[str, Any]) -> float | None:
    duration = duration_seconds(stream.get("duration"))
    if duration is not None:
        return duration

    # Matroska's DURATION tag records the end timestamp on the stream timeline.
    tag = stream.get("tags", {}).get("DURATION")
    if not isinstance(tag, str):
        return None
    timestamp = re.fullmatch(r"(\d+):([0-5]\d):([0-5]\d(?:\.\d+)?)", tag)
    if timestamp is None:
        return None
    try:
        start = float(stream.get("start_time"))
    except (TypeError, ValueError):
        return None
    hours, minutes, seconds = timestamp.groups()
    end = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return duration_seconds(end - start)
