"""Silence detection via ffmpeg's ``silencedetect`` filter.

Parsing is anchored on the stable ``silence_start`` / ``silence_end`` tokens and unit
tested against captured filter output, so it is resilient to surrounding log noise.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..config import THRESHOLDS
from ..ffmpeg import ffmpeg_filter
from ..models import SilenceSegment

_START_RE = re.compile(r"silence_start:\s*(-?[\d.]+)")
_END_RE = re.compile(r"silence_end:\s*(-?[\d.]+)")


def parse_silence(stderr: str, *, total_duration: float | None) -> list[SilenceSegment]:
    """Pair up silence_start / silence_end markers into segments.

    A trailing ``silence_start`` without an end (silence running to EOF) is closed at
    ``total_duration`` when known.
    """

    starts = [float(m) for m in _START_RE.findall(stderr)]
    ends = [float(m) for m in _END_RE.findall(stderr)]

    segments: list[SilenceSegment] = []
    for i, start in enumerate(starts):
        if i < len(ends):
            end = ends[i]
        elif total_duration is not None:
            end = total_duration
        else:
            continue
        if end > start:
            segments.append(SilenceSegment(start_seconds=start, end_seconds=end))
    return segments


def merge_segments(
    segments: list[SilenceSegment], *, gap: float = THRESHOLDS.silence_merge_gap
) -> list[SilenceSegment]:
    """Merge segments separated by less than ``gap`` seconds."""

    if not segments:
        return []
    ordered = sorted(segments, key=lambda s: s.start_seconds)
    merged = [ordered[0]]
    for seg in ordered[1:]:
        last = merged[-1]
        if seg.start_seconds - last.end_seconds <= gap:
            merged[-1] = SilenceSegment(
                start_seconds=last.start_seconds,
                end_seconds=max(last.end_seconds, seg.end_seconds),
            )
        else:
            merged.append(seg)
    return merged


def detect_silence(
    path: Path,
    *,
    total_duration: float | None,
    noise_db: float = THRESHOLDS.silence_noise_db,
    min_duration: float = THRESHOLDS.silence_min_duration,
) -> list[SilenceSegment]:
    """Detect and merge silence segments in ``path``."""

    stderr = ffmpeg_filter(path, f"silencedetect=noise={noise_db}dB:d={min_duration}")
    return merge_segments(parse_silence(stderr, total_duration=total_duration))


def silence_ratio(segments: list[SilenceSegment], total_duration: float | None) -> float:
    if not total_duration:
        return 0.0
    total_silence = sum(s.duration for s in segments)
    return min(1.0, total_silence / total_duration)
