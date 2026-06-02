"""Orchestrator: turn an audio file into a deterministic ``AudioReport``.

The "facts" half of the system. It probes metadata, runs the analyzer registry, and
composes the accumulated outputs into a validated report, recording the effective config
and analyzer list in ``analysis_metadata`` for reproducibility. The LLM insight layer is
attached separately so measurement stays independent of interpretation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .analyzers import AnalysisContext, AnalyzerOutput, run_analyzers
from .config import ANALYSIS_VERSION, THRESHOLDS, Thresholds
from .ffmpeg import FFmpegError
from .models import (
    AnalysisMetadata,
    AudioMetadata,
    AudioQuality,
    AudioReport,
    ClippingConfidence,
    Issue,
    IssueType,
    Severity,
    SilenceSegment,
)
from .probe import extract_metadata

# Metric keys that map onto typed AudioQuality fields; anything else flows to extra_metrics.
_KNOWN_METRICS = {
    "silence_ratio",
    "clipping_detected",
    "clipping_confidence",
    "avg_volume_db",
    "max_volume_db",
    "rms_level_db",
    "noise_floor_db",
}


def _compose_quality(
    metrics: dict[str, Any], segments: list[SilenceSegment]
) -> AudioQuality:
    extra = {
        k: float(v)
        for k, v in metrics.items()
        if k not in _KNOWN_METRICS and isinstance(v, (int, float))
    }
    return AudioQuality(
        silence_ratio=metrics.get("silence_ratio", 0.0),
        clipping_detected=bool(metrics.get("clipping_detected", False)),
        clipping_confidence=ClippingConfidence(metrics.get("clipping_confidence", "low")),
        avg_volume_db=metrics.get("avg_volume_db"),
        max_volume_db=metrics.get("max_volume_db"),
        rms_level_db=metrics.get("rms_level_db"),
        noise_floor_db=metrics.get("noise_floor_db"),
        silence_segments=segments,
        extra_metrics=extra,
    )


def compose_report(
    path: Path,
    metadata: AudioMetadata,
    outputs: list[AnalyzerOutput],
    *,
    config: Thresholds,
    mode: str = "deterministic",
) -> AudioReport:
    """Assemble a validated report from analyzer outputs (shared by pipeline and agent)."""

    metrics: dict[str, Any] = {}
    issues: list[Issue] = []
    segments: list[SilenceSegment] = []
    for out in outputs:
        metrics.update(out.metrics)
        issues.extend(out.issues)
        segments.extend(out.silence_segments)

    return AudioReport(
        file_name=path.name,
        duration_seconds=metadata.duration_seconds,
        metadata=metadata,
        audio_quality=_compose_quality(metrics, segments),
        issues=issues,
        analysis_metadata=AnalysisMetadata(
            mode=mode,
            analyzers=[out.name for out in outputs],
            config=config.to_dict(),
        ),
        analysis_version=ANALYSIS_VERSION,
    )


def _error_report(path: Path, exc: Exception, config: Thresholds) -> AudioReport:
    return AudioReport(
        file_name=path.name,
        metadata=AudioMetadata(),
        audio_quality=AudioQuality(silence_ratio=0.0, clipping_detected=False),
        issues=[
            Issue(type=IssueType.probe_error, severity=Severity.critical, message=str(exc))
        ],
        analysis_metadata=AnalysisMetadata(config=config.to_dict()),
        analysis_version=ANALYSIS_VERSION,
        error=str(exc),
    )


def analyze_file(path: str | Path, *, config: Thresholds = THRESHOLDS) -> AudioReport:
    """Run the full deterministic analysis on a single file.

    Probe failures are captured into the report rather than raised, so batch runs over
    messy real-world data don't abort on one bad file.
    """

    path = Path(path)
    try:
        metadata = extract_metadata(path)
    except FFmpegError as exc:
        return _error_report(path, exc, config)

    ctx = AnalysisContext(path, metadata.duration_seconds, metadata, config)
    outputs = run_analyzers(ctx)
    return compose_report(path, metadata, outputs, config=config)
