"""Pydantic schemas: the deterministic contract between measurement and insight.

These models define exactly what the probe/analysis layers produce. The LLM layer
consumes (never mutates) this structure, which keeps the report reproducible and the
LLM's reasoning auditable against concrete numbers.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    info = "info"
    warning = "warning"
    critical = "critical"


class IssueType(StrEnum):
    long_silence = "long_silence"
    high_silence_ratio = "high_silence_ratio"
    low_volume = "low_volume"
    clipping = "clipping"
    elevated_noise = "elevated_noise"
    low_bitrate = "low_bitrate"
    probe_error = "probe_error"


class ClippingConfidence(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class Issue(BaseModel):
    """A single, machine-detected problem with the audio."""

    type: IssueType
    severity: Severity
    message: str
    start_seconds: float | None = None
    end_seconds: float | None = None


class AudioMetadata(BaseModel):
    """Container/stream facts straight from ffprobe."""

    duration_seconds: float | None = None
    bitrate_bps: int | None = None
    sample_rate_hz: int | None = None
    channels: int | None = None
    codec: str | None = None
    container: str | None = None


class SilenceSegment(BaseModel):
    start_seconds: float
    end_seconds: float

    @property
    def duration(self) -> float:
        return self.end_seconds - self.start_seconds


class AudioQuality(BaseModel):
    """Quantitative quality metrics.

    Alongside the core fields it carries signal-depth metrics (RMS, noise floor, clipping
    confidence) and an open ``extra_metrics`` map so new analyzers can contribute derived
    metrics (e.g. dynamic range) without schema churn.
    """

    silence_ratio: float = Field(ge=0.0, le=1.0)
    clipping_detected: bool
    clipping_confidence: ClippingConfidence = ClippingConfidence.low
    avg_volume_db: float | None = None
    max_volume_db: float | None = None
    rms_level_db: float | None = None
    noise_floor_db: float | None = None
    silence_segments: list[SilenceSegment] = Field(default_factory=list)
    extra_metrics: dict[str, float] = Field(default_factory=dict)


class AnalysisMetadata(BaseModel):
    """Audit trail: how this report was produced (mode, analyzers, effective config)."""

    mode: str = "deterministic"  # "deterministic" or "agent"
    analyzers: list[str] = Field(default_factory=list)
    config: dict[str, float | int] = Field(default_factory=dict)


class Insight(BaseModel):
    """Human-readable interpretation produced by the LLM (or rule fallback)."""

    summary: str
    recommended_actions: list[str] = Field(default_factory=list)
    usable_as_is: bool | None = None
    generated_by: str = "rules"  # "llm:<model>" or "rules"


class AudioReport(BaseModel):
    """Top-level per-file report. Serialised as the deterministic JSON artifact."""

    file_name: str
    duration_seconds: float | None = None
    metadata: AudioMetadata
    audio_quality: AudioQuality
    issues: list[Issue] = Field(default_factory=list)
    insight: Insight | None = None
    analysis_metadata: AnalysisMetadata = Field(default_factory=AnalysisMetadata)
    analysis_version: str
    error: str | None = None


class BatchReport(BaseModel):
    """Aggregate view across many files."""

    file_count: int
    reports: list[AudioReport]
    issue_counts: dict[str, int] = Field(default_factory=dict)
    average_duration_seconds: float | None = None
    average_silence_ratio: float | None = None
    files_with_clipping: list[str] = Field(default_factory=list)
    files_with_low_volume: list[str] = Field(default_factory=list)
    top_issues: list[str] = Field(default_factory=list)
    aggregate_summary: str | None = None
