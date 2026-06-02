"""Composable analyzer registry, the extensibility backbone.

Each analyzer receives shared file context plus the metrics emitted by earlier analyzers,
and returns new metrics, typed issues, and optional silence segments. Adding a new check is
a one-class change: implement ``Analyzer`` and add it to ``DEFAULT_ANALYZERS``. The pipeline
composes the accumulated outputs into the validated :class:`AudioReport`.

Analyzers emit typed ``Issue`` objects (with severity) rather than free-text strings, which
keeps the report machine-readable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .analysis import detect_clipping, detect_noise, detect_silence, detect_volume
from .analysis.silence import silence_ratio
from .config import THRESHOLDS, Thresholds
from .ffmpeg import FFmpegError
from .models import AudioMetadata, Issue, IssueType, Severity, SilenceSegment


@dataclass(frozen=True)
class AnalysisContext:
    file_path: Path
    duration_seconds: float | None
    metadata: AudioMetadata
    config: Thresholds = THRESHOLDS


@dataclass(frozen=True)
class AnalyzerOutput:
    name: str
    metrics: dict[str, Any] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)
    silence_segments: list[SilenceSegment] = field(default_factory=list)


class Analyzer(Protocol):
    name: str

    def run(self, ctx: AnalysisContext, metrics: dict[str, Any]) -> AnalyzerOutput: ...


def _fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:d}:{s:02d}"


class SilenceAnalyzer:
    name = "silence"

    def run(self, ctx: AnalysisContext, metrics: dict[str, Any]) -> AnalyzerOutput:
        segments = detect_silence(
            ctx.file_path,
            total_duration=ctx.duration_seconds,
            noise_db=ctx.config.silence_noise_db,
            min_duration=ctx.config.silence_min_duration,
        )
        ratio = silence_ratio(segments, ctx.duration_seconds)
        issues: list[Issue] = []
        for seg in segments:
            if seg.duration >= ctx.config.long_silence_seconds:
                issues.append(
                    Issue(
                        type=IssueType.long_silence,
                        severity=Severity.warning,
                        message=(
                            f"Long silence ({seg.duration:.0f}s) between "
                            f"{_fmt_ts(seg.start_seconds)} and {_fmt_ts(seg.end_seconds)}"
                        ),
                        start_seconds=seg.start_seconds,
                        end_seconds=seg.end_seconds,
                    )
                )
        if ratio >= ctx.config.high_silence_ratio:
            issues.append(
                Issue(
                    type=IssueType.high_silence_ratio,
                    severity=Severity.warning,
                    message=f"{ratio:.0%} of the recording is silent; consider trimming dead air",
                )
            )
        return AnalyzerOutput(
            name=self.name,
            metrics={"silence_ratio": round(ratio, 4)},
            issues=issues,
            silence_segments=segments,
        )


class VolumeAnalyzer:
    name = "volume"

    def run(self, ctx: AnalysisContext, metrics: dict[str, Any]) -> AnalyzerOutput:
        v = detect_volume(ctx.file_path)
        clip = detect_clipping(
            v,
            peak_db=ctx.config.clipping_peak_db,
            high_confidence_db=ctx.config.high_confidence_clipping_db,
            sample_count=ctx.config.clipping_sample_count,
        )
        issues: list[Issue] = []
        if v.mean_db is not None and v.mean_db < ctx.config.low_mean_volume_db:
            issues.append(
                Issue(
                    type=IssueType.low_volume,
                    severity=Severity.warning,
                    message=(
                        f"Low average level ({v.mean_db} dB); audio may be too quiet, "
                        "check input gain"
                    ),
                )
            )
        if clip.detected:
            sev = Severity.critical if clip.confidence == "high" else Severity.warning
            issues.append(
                Issue(
                    type=IssueType.clipping,
                    severity=sev,
                    message=(
                        f"Possible clipping/distortion "
                        f"({clip.confidence} confidence: {clip.reason})"
                    ),
                )
            )
        return AnalyzerOutput(
            name=self.name,
            metrics={
                "avg_volume_db": v.mean_db,
                "max_volume_db": v.max_db,
                "clipping_detected": clip.detected,
                "clipping_confidence": clip.confidence,
            },
            issues=issues,
        )


class NoiseAnalyzer:
    """Optional astats pass for RMS + noise floor. Skipped on very long files."""

    name = "noise"

    def run(self, ctx: AnalysisContext, metrics: dict[str, Any]) -> AnalyzerOutput:
        if (
            ctx.duration_seconds is not None
            and ctx.duration_seconds > ctx.config.max_astats_duration_seconds
        ):
            return AnalyzerOutput(name=self.name)  # bounded cost on huge files
        n = detect_noise(ctx.file_path)
        issues: list[Issue] = []
        if n.noise_floor_db is not None and n.noise_floor_db > ctx.config.elevated_noise_floor_db:
            issues.append(
                Issue(
                    type=IssueType.elevated_noise,
                    severity=Severity.warning,
                    message=(
                        f"Elevated noise floor ({n.noise_floor_db:.1f} dB); audible "
                        "background hiss/hum"
                    ),
                )
            )
        return AnalyzerOutput(
            name=self.name,
            metrics={"rms_level_db": n.rms_level_db, "noise_floor_db": n.noise_floor_db},
        )


class DynamicRangeAnalyzer:
    """Derived metric (peak − mean) from earlier volume metrics; no extra ffmpeg pass."""

    name = "dynamic_range"

    def run(self, ctx: AnalysisContext, metrics: dict[str, Any]) -> AnalyzerOutput:
        avg, peak = metrics.get("avg_volume_db"), metrics.get("max_volume_db")
        if avg is None or peak is None:
            return AnalyzerOutput(name=self.name)
        return AnalyzerOutput(
            name=self.name, metrics={"peak_to_mean_db": round(peak - avg, 2)}
        )


class BitrateAnalyzer:
    name = "bitrate"

    def run(self, ctx: AnalysisContext, metrics: dict[str, Any]) -> AnalyzerOutput:
        br = ctx.metadata.bitrate_bps
        if br is not None and br < ctx.config.low_bitrate_bps:
            return AnalyzerOutput(
                name=self.name,
                issues=[
                    Issue(
                        type=IssueType.low_bitrate,
                        severity=Severity.info,
                        message=(
                            f"Low bitrate ({br // 1000} kbps) may reduce audio fidelity"
                        ),
                    )
                ],
            )
        return AnalyzerOutput(name=self.name)


DEFAULT_ANALYZERS: tuple[Analyzer, ...] = (
    SilenceAnalyzer(),
    VolumeAnalyzer(),
    NoiseAnalyzer(),
    DynamicRangeAnalyzer(),
    BitrateAnalyzer(),
)


def run_analyzers(
    ctx: AnalysisContext, analyzers: tuple[Analyzer, ...] | list[Analyzer] | None = None
) -> list[AnalyzerOutput]:
    """Run analyzers in order, threading accumulated metrics between them."""

    outputs: list[AnalyzerOutput] = []
    metrics: dict[str, Any] = {}
    for analyzer in analyzers or DEFAULT_ANALYZERS:
        try:
            output = analyzer.run(ctx, dict(metrics))
        except FFmpegError:
            # A failing optional analyzer shouldn't abort the whole report.
            output = AnalyzerOutput(name=analyzer.name)
        metrics.update(output.metrics)
        outputs.append(output)
    return outputs
