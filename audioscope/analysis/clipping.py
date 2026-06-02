"""Clipping detection (heuristic).

True sample-peak clipping requires decoded-PCM inspection; as a pragmatic and cheap
proxy we combine ``volumedetect``'s peak level with its count of samples pinned at
0 dBFS. This is documented as a heuristic in the README, with ``astats`` noted as a
stronger follow-up.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import THRESHOLDS
from .volume import VolumeResult


@dataclass(frozen=True)
class ClippingResult:
    detected: bool
    confidence: str  # "low" | "medium" | "high"
    reason: str


def detect_clipping(
    volume: VolumeResult,
    *,
    peak_db: float = THRESHOLDS.clipping_peak_db,
    high_confidence_db: float = THRESHOLDS.high_confidence_clipping_db,
    sample_count: int = THRESHOLDS.clipping_sample_count,
) -> ClippingResult:
    """Infer clipping from peak level and 0 dBFS sample count, with graded confidence.

    - ``high``:   peak extremely close to 0 dBFS, or near-peak with many pinned samples.
    - ``medium``: peak at/above the clipping threshold.
    - ``low``:    headroom remains (not clipping).
    """

    if volume.max_db is None:
        return ClippingResult(False, "low", "no peak measurement available")

    if volume.max_db >= high_confidence_db:
        return ClippingResult(
            True, "high", f"peak {volume.max_db} dB is extremely close to 0 dBFS"
        )
    if volume.max_db >= peak_db:
        many_pinned = volume.samples_at_0db >= sample_count
        confidence = "high" if many_pinned else "medium"
        detail = (
            f"peak {volume.max_db} dB with {volume.samples_at_0db} samples at 0 dBFS"
            if many_pinned
            else f"peak {volume.max_db} dB is close to 0 dBFS"
        )
        return ClippingResult(True, confidence, detail)

    return ClippingResult(False, "low", f"peak {volume.max_db} dB leaves headroom")
