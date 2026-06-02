"""Reusable analysis tools shared by the CLI pipeline, the agent, and the MCP server.

Each tool is a thin, JSON-friendly wrapper over the probe/detector functions. Designing
the analysis as discrete tools is what lets the same logic power three entry points
without duplication.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .analysis import detect_clipping, detect_noise, detect_silence, detect_volume
from .analysis.silence import silence_ratio
from .probe import extract_metadata


def get_audio_metadata(file_path: str) -> dict[str, Any]:
    """Return container/stream metadata (duration, bitrate, sample_rate, channels)."""

    return extract_metadata(Path(file_path)).model_dump()


def detect_silence_tool(file_path: str) -> dict[str, Any]:
    """Detect silence segments and the overall silence ratio."""

    path = Path(file_path)
    duration = extract_metadata(path).duration_seconds
    segments = detect_silence(path, total_duration=duration)
    return {
        "silence_ratio": round(silence_ratio(segments, duration), 4),
        "segment_count": len(segments),
        "segments": [s.model_dump() for s in segments],
    }


def detect_volume_tool(file_path: str) -> dict[str, Any]:
    """Measure mean and peak volume (dBFS)."""

    v = detect_volume(Path(file_path))
    return {"mean_db": v.mean_db, "max_db": v.max_db, "samples_at_0db": v.samples_at_0db}


def detect_clipping_tool(file_path: str) -> dict[str, Any]:
    """Detect likely clipping/distortion from peak levels."""

    v = detect_volume(Path(file_path))
    c = detect_clipping(v)
    return {"clipping_detected": c.detected, "confidence": c.confidence, "reason": c.reason}


def detect_noise_tool(file_path: str) -> dict[str, Any]:
    """Estimate RMS level and noise floor (dBFS) via ffmpeg astats."""

    n = detect_noise(Path(file_path))
    return {"rms_level_db": n.rms_level_db, "noise_floor_db": n.noise_floor_db}
