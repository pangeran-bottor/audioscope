"""Human-readable rendering of reports for the terminal."""

from __future__ import annotations

from .models import AudioReport, BatchReport

_SEVERITY_ICON = {"info": "ℹ", "warning": "⚠", "critical": "✖"}


def _fmt_duration(seconds: float | None) -> str:
    if not seconds:
        return "unknown"
    m, s = divmod(int(seconds), 60)
    return f"{m}m{s:02d}s"


def render_report(report: AudioReport) -> str:
    md = report.metadata
    q = report.audio_quality
    clip = f"{q.clipping_detected}"
    if q.clipping_detected:
        clip += f" ({q.clipping_confidence})"
    noise = f"{q.noise_floor_db}dB" if q.noise_floor_db is not None else "n/a"
    dr = q.extra_metrics.get("peak_to_mean_db")
    lines = [
        f"📄 {report.file_name}",
        f"   duration={_fmt_duration(report.duration_seconds)}  "
        f"bitrate={(md.bitrate_bps or 0) // 1000}kbps  "
        f"sample_rate={md.sample_rate_hz}Hz  channels={md.channels}  codec={md.codec}",
        f"   silence_ratio={q.silence_ratio:.0%}  clipping={clip}  "
        f"avg_volume={q.avg_volume_db}dB  peak={q.max_volume_db}dB",
        f"   noise_floor={noise}  rms={q.rms_level_db}dB"
        + (f"  dynamic_range={dr}dB" if dr is not None else ""),
    ]

    if report.issues:
        lines.append("   issues:")
        for issue in report.issues:
            icon = _SEVERITY_ICON.get(issue.severity.value, "-")
            lines.append(f"     {icon} [{issue.severity.value}] {issue.message}")
    else:
        lines.append("   issues: none ✓")

    if report.insight:
        lines.append(f"   insight ({report.insight.generated_by}):")
        lines.append(f"     {report.insight.summary}")
        for action in report.insight.recommended_actions:
            lines.append(f"     → {action}")
        if report.insight.usable_as_is is not None:
            verdict = "yes" if report.insight.usable_as_is else "no"
            lines.append(f"     usable as-is: {verdict}")

    return "\n".join(lines)


def render_batch(batch: BatchReport) -> str:
    per_file = "\n\n".join(render_report(r) for r in batch.reports)
    avg_dur = _fmt_duration(batch.average_duration_seconds)
    avg_sil = (
        f"{batch.average_silence_ratio:.0%}" if batch.average_silence_ratio is not None else "n/a"
    )
    agg = [
        "📊 Aggregate",
        f"   files={batch.file_count}  avg_duration={avg_dur}  avg_silence={avg_sil}",
        f"   top_issues={batch.top_issues or 'none'}",
        f"   clipping={batch.files_with_clipping or 'none'}",
        f"   low_volume={batch.files_with_low_volume or 'none'}",
        f"   {batch.aggregate_summary}",
    ]
    return per_file + "\n\n" + "\n".join(agg)
