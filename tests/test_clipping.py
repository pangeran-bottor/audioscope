"""Unit tests for the clipping heuristic (pure logic)."""

from __future__ import annotations

from audioscope.analysis.clipping import detect_clipping
from audioscope.analysis.volume import VolumeResult


def test_clipping_detected_on_hot_peak_and_pinned_samples():
    v = VolumeResult(mean_db=-10.0, max_db=0.0, samples_at_0db=500)
    result = detect_clipping(v)
    assert result.detected is True
    assert result.confidence == "high"  # peak ~0 dBFS


def test_clipping_medium_confidence_near_threshold():
    # Peak between clipping threshold (-1) and high-confidence (-0.1), few pinned samples.
    v = VolumeResult(mean_db=-10.0, max_db=-0.5, samples_at_0db=0)
    result = detect_clipping(v)
    assert result.detected is True
    assert result.confidence == "medium"


def test_clipping_high_confidence_when_many_pinned():
    v = VolumeResult(mean_db=-10.0, max_db=-0.5, samples_at_0db=500)
    assert detect_clipping(v).confidence == "high"


def test_no_clipping_on_healthy_peak():
    v = VolumeResult(mean_db=-18.0, max_db=-6.0, samples_at_0db=0)
    result = detect_clipping(v)
    assert result.detected is False
    assert result.confidence == "low"


def test_no_peak_measurement_is_not_clipping():
    v = VolumeResult(mean_db=None, max_db=None, samples_at_0db=0)
    assert detect_clipping(v).detected is False
