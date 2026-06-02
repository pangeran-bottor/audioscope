"""Direct-mode insight generation.

The LLM reasons over the already-computed metrics; it never measures audio itself.
The prompt supplies the meaning of each metric so the model produces grounded, actionable
judgement rather than a generic description. A deterministic rule-based fallback keeps the
system usable with no API key configured.
"""

from __future__ import annotations

from ..models import AudioReport, Insight
from .llm import LLMUnavailable, complete_json, model_label

_SYSTEM = """\
You are an audio-quality analyst. You are given a JSON report of objective measurements \
extracted from an audio file using ffmpeg. The numbers are already computed and \
authoritative, so do not invent or recompute values; reason only from what is provided.

What the metrics mean:
- silence_ratio is the fraction of the file that is silent; long stretches of silence often \
indicate dead air that can be trimmed.
- avg_volume_db / max_volume_db are in dBFS (0 is maximum; more negative is quieter). \
A very low average level means the audio is too quiet; peaks at/near 0 dB suggest \
clipping/distortion.
- noise_floor_db indicates background noise; a high floor means audible hiss or hum.
- Low bitrate or low sample rate can reduce fidelity.

Be specific and concise. Cite the actual numbers. Recommendations must be concrete and \
actionable for whoever manages the audio.\
"""

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {
            "type": "string",
            "description": "2-3 sentence plain-language summary citing the metrics.",
        },
        "recommended_actions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Prioritised, concrete actions. Empty if none needed.",
        },
        "usable_as_is": {
            "type": "boolean",
            "description": "Whether the audio is usable as-is or needs remediation first.",
        },
    },
    "required": ["summary", "recommended_actions", "usable_as_is"],
}


def _rule_based(report: AudioReport) -> Insight:
    """Deterministic fallback used when no LLM is available."""

    q = report.audio_quality
    parts: list[str] = []
    actions: list[str] = []
    usable = True

    if q.clipping_detected:
        parts.append("peaks reach near 0 dBFS, indicating possible clipping/distortion")
        actions.append("Reduce input gain or re-record to avoid clipping.")
        usable = False
    if q.avg_volume_db is not None and q.avg_volume_db < -30:
        parts.append(f"the average level is low ({q.avg_volume_db} dB)")
        actions.append("Apply normalization/gain and check microphone levels.")
    if q.silence_ratio >= 0.30:
        parts.append(f"{q.silence_ratio:.0%} of the recording is silence")
        actions.append("Trim extended silence to remove dead air.")
    if report.metadata.bitrate_bps and report.metadata.bitrate_bps < 64_000:
        parts.append(f"bitrate is low ({report.metadata.bitrate_bps // 1000} kbps)")
        actions.append("Capture at a higher bitrate/sample rate for future recordings.")

    if not parts:
        summary = (
            "Audio quality looks good: levels are reasonable, no clipping detected, and "
            "silence is within normal limits."
        )
    else:
        summary = "This audio is usable but " + "; ".join(parts) + "."

    return Insight(
        summary=summary,
        recommended_actions=actions,
        usable_as_is=usable,
        generated_by="rules",
    )


def generate_insight(report: AudioReport, *, use_llm: bool = True) -> Insight:
    """Produce an :class:`Insight`, preferring the LLM and falling back to rules."""

    if not use_llm:
        return _rule_based(report)

    payload = report.model_dump_json(
        include={"file_name", "duration_seconds", "metadata", "audio_quality", "issues"},
        indent=2,
    )
    try:
        data = complete_json(
            system=_SYSTEM,
            user=f"Analyse this audio report and respond per the schema:\n\n{payload}",
            schema=_SCHEMA,
            schema_name="audio_insight",
        )
    except LLMUnavailable:
        return _rule_based(report)

    return Insight(
        summary=data["summary"],
        recommended_actions=data.get("recommended_actions", []),
        usable_as_is=data.get("usable_as_is"),
        generated_by=model_label(),
    )
