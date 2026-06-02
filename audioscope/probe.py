"""Metadata extraction via ffprobe (facts layer).

We ask ffprobe for JSON and parse that, never regex over human-readable output, so
the extraction is robust across ffmpeg versions.
"""

from __future__ import annotations

import json
from pathlib import Path

from .ffmpeg import FFmpegError, ffprobe
from .models import AudioMetadata


def _first_audio_stream(streams: list[dict]) -> dict | None:
    for stream in streams:
        if stream.get("codec_type") == "audio":
            return stream
    return None


def _to_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _to_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def extract_metadata(path: Path) -> AudioMetadata:
    """Return container/stream metadata for ``path``.

    Falls back to deriving bitrate from file size when the container omits it.
    """

    if not path.exists():
        raise FFmpegError(f"File not found: {path}")

    proc = ffprobe(
        [
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )
    if proc.returncode != 0:
        raise FFmpegError(f"ffprobe failed for {path.name}: {proc.stderr.strip()}")

    data = json.loads(proc.stdout or "{}")
    fmt = data.get("format", {})
    stream = _first_audio_stream(data.get("streams", [])) or {}

    duration = _to_float(fmt.get("duration")) or _to_float(stream.get("duration"))
    bitrate = _to_int(fmt.get("bit_rate")) or _to_int(stream.get("bit_rate"))

    # Derive an approximate bitrate when missing and we know size + duration.
    if bitrate is None and duration:
        size = _to_int(fmt.get("size"))
        if size:
            bitrate = int(size * 8 / duration)

    return AudioMetadata(
        duration_seconds=duration,
        bitrate_bps=bitrate,
        sample_rate_hz=_to_int(stream.get("sample_rate")),
        channels=_to_int(stream.get("channels")),
        codec=stream.get("codec_name"),
        container=(fmt.get("format_name") or "").split(",")[0] or None,
    )
