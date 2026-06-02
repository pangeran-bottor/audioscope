"""Tests for batch aggregation logic (no ffmpeg/network needed)."""

from __future__ import annotations

from audioscope.batch import _aggregate_summary, _mean
from audioscope.models import (
    AudioMetadata,
    AudioQuality,
    AudioReport,
    BatchReport,
    Issue,
    IssueType,
    Severity,
)


def _report(name: str, *, clipping=False, silence=0.05, issues=None) -> AudioReport:
    return AudioReport(
        file_name=name,
        duration_seconds=100.0,
        metadata=AudioMetadata(),
        audio_quality=AudioQuality(silence_ratio=silence, clipping_detected=clipping),
        issues=issues or [],
        analysis_version="test",
    )


def test_mean():
    assert _mean([1.0, 2.0, 3.0]) == 2.0
    assert _mean([]) is None


def test_aggregate_summary_offline_counts_clean_files():
    batch = BatchReport(
        file_count=2,
        reports=[_report("a.wav"), _report("b.wav")],
        issue_counts={},
    )
    summary = _aggregate_summary(batch, use_llm=False)
    assert "2 file(s)" in summary
    assert "2 clean" in summary


def test_clipping_issue_flows_into_severity():
    issue = Issue(type=IssueType.clipping, severity=Severity.critical, message="x")
    report = _report("c.wav", clipping=True, issues=[issue])
    assert report.audio_quality.clipping_detected is True
    assert report.issues[0].severity is Severity.critical
