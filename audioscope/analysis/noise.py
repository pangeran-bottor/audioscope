"""Noise-floor / RMS measurement via ffmpeg's ``astats`` filter.

``astats`` reports per-channel stats followed by an overall block; we take the last
occurrence of each field (the overall summary). Non-finite values (e.g. a ``-inf`` noise
floor on near-silent or already-clean tracks) are intentionally surfaced as ``None`` and
recommended for manual spot-checking rather than reported as a misleading number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..ffmpeg import ffmpeg_filter

# Match only finite decimals, so "-inf"/"nan" won't match and map to None.
_FINITE = r"(-?\d+(?:\.\d+)?)"
_RMS_RE = re.compile(rf"RMS level dB:\s*{_FINITE}")
_NOISE_RE = re.compile(rf"Noise floor dB:\s*{_FINITE}")


@dataclass(frozen=True)
class NoiseResult:
    rms_level_db: float | None
    noise_floor_db: float | None


def parse_astats(stderr: str) -> NoiseResult:
    rms = _RMS_RE.findall(stderr)
    noise = _NOISE_RE.findall(stderr)
    return NoiseResult(
        rms_level_db=float(rms[-1]) if rms else None,
        noise_floor_db=float(noise[-1]) if noise else None,
    )


def detect_noise(path: Path) -> NoiseResult:
    return parse_astats(ffmpeg_filter(path, "astats=metadata=1:reset=0"))
