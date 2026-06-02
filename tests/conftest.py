"""Test fixtures: tiny synthetic audio generated with ffmpeg's lavfi sources.

Generating fixtures on the fly keeps the test suite self-contained (no binary blobs in
git) and lets us construct precise edge cases: pure silence, a clipped tone, and a normal
tone.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_FFMPEG = shutil.which("ffmpeg")
requires_ffmpeg = pytest.mark.skipif(_FFMPEG is None, reason="ffmpeg not installed")


def _gen(args: list[str], out: Path) -> Path:
    subprocess.run(
        [_FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *args, str(out)],
        check=True,
    )
    return out


@pytest.fixture(scope="session")
def tone_wav(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """3s sine tone at a moderate level (clean-ish audio)."""

    out = tmp_path_factory.mktemp("audio") / "tone.wav"
    return _gen(
        ["-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-af", "volume=-12dB"], out
    )


@pytest.fixture(scope="session")
def silent_wav(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """3s of pure silence."""

    out = tmp_path_factory.mktemp("audio") / "silent.wav"
    return _gen(["-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono", "-t", "3"], out)


@pytest.fixture(scope="session")
def clipped_wav(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """3s sine pushed well past 0 dBFS to force clipping."""

    out = tmp_path_factory.mktemp("audio") / "clipped.wav"
    return _gen(
        ["-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-af", "volume=20dB"], out
    )
