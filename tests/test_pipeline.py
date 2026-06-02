"""Integration tests against generated fixtures (require ffmpeg)."""

from __future__ import annotations

from pathlib import Path

from audioscope.models import IssueType
from audioscope.pipeline import analyze_file

from .conftest import requires_ffmpeg


@requires_ffmpeg
def test_metadata_extracted(tone_wav: Path):
    report = analyze_file(tone_wav)
    assert report.metadata.sample_rate_hz is not None
    assert report.metadata.channels == 1
    assert report.duration_seconds and 2.5 < report.duration_seconds < 3.5
    assert report.error is None


@requires_ffmpeg
def test_silent_file_flags_high_silence(silent_wav: Path):
    report = analyze_file(silent_wav)
    assert report.audio_quality.silence_ratio > 0.9
    types = {i.type for i in report.issues}
    assert IssueType.high_silence_ratio in types


@requires_ffmpeg
def test_clipped_file_flags_clipping(clipped_wav: Path):
    report = analyze_file(clipped_wav)
    assert report.audio_quality.clipping_detected is True
    assert any(i.type is IssueType.clipping for i in report.issues)


@requires_ffmpeg
def test_clean_tone_has_no_clipping(tone_wav: Path):
    report = analyze_file(tone_wav)
    assert report.audio_quality.clipping_detected is False


def test_missing_file_returns_error_report():
    report = analyze_file("does_not_exist.wav")
    assert report.error is not None
    assert any(i.type is IssueType.probe_error for i in report.issues)


@requires_ffmpeg
def test_report_serialises_to_json(tone_wav: Path):
    report = analyze_file(tone_wav)
    blob = report.model_dump_json()
    assert '"audio_quality"' in blob


@requires_ffmpeg
def test_report_records_analysis_metadata(tone_wav: Path):
    report = analyze_file(tone_wav)
    meta = report.analysis_metadata
    assert meta.mode == "deterministic"
    assert "silence" in meta.analyzers and "noise" in meta.analyzers
    # Effective config is captured for reproducibility.
    assert "silence_noise_db" in meta.config


@requires_ffmpeg
def test_dynamic_range_metric_present(tone_wav: Path):
    report = analyze_file(tone_wav)
    assert "peak_to_mean_db" in report.audio_quality.extra_metrics


@requires_ffmpeg
def test_clipping_confidence_set(clipped_wav: Path):
    report = analyze_file(clipped_wav)
    assert report.audio_quality.clipping_confidence in {"medium", "high"}
