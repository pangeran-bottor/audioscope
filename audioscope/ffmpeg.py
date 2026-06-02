"""Thin, safe wrappers around the ffmpeg/ffprobe binaries.

We shell out (rather than use a Python audio library) to leverage ffmpeg's battle-tested
analysis filters. All callers go through ``run`` so timeout/error handling lives in one
place.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class FFmpegError(RuntimeError):
    """Raised when ffmpeg/ffprobe is missing or a command fails."""


def _require(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise FFmpegError(
            f"`{binary}` not found on PATH. Install ffmpeg (e.g. `brew install ffmpeg`)."
        )
    return path


def run(args: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    """Run a command, returning the completed process.

    ffmpeg writes its analysis output to stderr, so we always capture both streams and
    let the caller decide which to parse. We do not raise on non-zero exit for analysis
    filters (some emit warnings); callers inspect output explicitly.
    """

    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - timing dependent
        raise FFmpegError(f"Command timed out after {timeout}s: {' '.join(args)}") from exc


def ffprobe(extra_args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return run([_require("ffprobe"), *extra_args], timeout=timeout)


def has_ffmpeg() -> bool:
    """Return True when both binaries are present (used to gate optional analysis)."""

    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def ffmpeg_filter(path: Path, audio_filter: str, *, timeout: int = 300) -> str:
    """Run an ffmpeg audio filter against ``path`` and return stderr (where filters log).

    Output is discarded (``-f null -``); we only want the filter's measurements.
    """

    proc = run(
        [
            _require("ffmpeg"),
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            audio_filter,
            "-f",
            "null",
            "-",
        ],
        timeout=timeout,
    )
    return proc.stderr
