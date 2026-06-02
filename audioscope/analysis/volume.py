"""Volume measurement via ffmpeg's ``volumedetect`` filter.

Provides mean and peak levels in dBFS, which feed both the low-volume check and the
clipping heuristic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..ffmpeg import ffmpeg_filter

_MEAN_RE = re.compile(r"mean_volume:\s*(-?[\d.]+)\s*dB")
_MAX_RE = re.compile(r"max_volume:\s*(-?[\d.]+)\s*dB")
_HIST_0DB_RE = re.compile(r"histogram_0db:\s*(\d+)")


@dataclass(frozen=True)
class VolumeResult:
    mean_db: float | None
    max_db: float | None
    # Count of samples at exactly 0 dBFS (a strong clipping indicator).
    samples_at_0db: int


def _search_float(pattern: re.Pattern[str], text: str) -> float | None:
    m = pattern.search(text)
    return float(m.group(1)) if m else None


def parse_volume(stderr: str) -> VolumeResult:
    hist = _HIST_0DB_RE.search(stderr)
    return VolumeResult(
        mean_db=_search_float(_MEAN_RE, stderr),
        max_db=_search_float(_MAX_RE, stderr),
        samples_at_0db=int(hist.group(1)) if hist else 0,
    )


def detect_volume(path: Path) -> VolumeResult:
    return parse_volume(ffmpeg_filter(path, "volumedetect"))
