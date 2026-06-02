"""Tests for the rule-based insight fallback (no network)."""

from __future__ import annotations

from audioscope.insight import generate_insight
from audioscope.models import AudioMetadata, AudioQuality, AudioReport


def _report(**quality) -> AudioReport:
    base = dict(silence_ratio=0.05, clipping_detected=False, avg_volume_db=-18.0)
    base.update(quality)
    return AudioReport(
        file_name="x.wav",
        duration_seconds=10.0,
        metadata=AudioMetadata(bitrate_bps=256_000),
        audio_quality=AudioQuality(**base),
        analysis_version="test",
    )


def test_clean_audio_is_usable():
    insight = generate_insight(_report(), use_llm=False)
    assert insight.usable_as_is is True
    assert insight.generated_by == "rules"
    assert "good" in insight.summary.lower()


def test_clipping_makes_unusable_with_action():
    insight = generate_insight(_report(clipping_detected=True), use_llm=False)
    assert insight.usable_as_is is False
    assert any("gain" in a.lower() or "clip" in a.lower() for a in insight.recommended_actions)


def test_high_silence_recommends_trim():
    insight = generate_insight(_report(silence_ratio=0.5), use_llm=False)
    assert any("silence" in a.lower() for a in insight.recommended_actions)
