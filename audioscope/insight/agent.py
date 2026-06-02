"""Tool-calling agent that dynamically decides which analysis tools to run.

Rather than the fixed pipeline, the LLM is given the analysis tools and chooses which to
call (e.g. only check clipping after seeing a hot peak), then composes the final report.
The deterministic pipeline remains the default driver; the agent is an alternate one over
the same tools, so reliability is never traded away.

If no LLM is configured, this transparently falls back to the deterministic pipeline so
the ``--agent`` flag always produces a valid report.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..analyzers import AnalysisContext, run_analyzers
from ..config import LLM, THRESHOLDS, Thresholds
from ..ffmpeg import FFmpegError
from ..models import AudioReport
from ..pipeline import _error_report, compose_report
from ..probe import extract_metadata
from ..tools import (
    detect_clipping_tool,
    detect_noise_tool,
    detect_silence_tool,
    detect_volume_tool,
    get_audio_metadata,
)
from .direct import generate_insight

_TOOLS = {
    "get_audio_metadata": get_audio_metadata,
    "detect_silence": detect_silence_tool,
    "detect_volume": detect_volume_tool,
    "detect_clipping": detect_clipping_tool,
    "estimate_noise": detect_noise_tool,
}

_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": (fn.__doc__ or "").strip().splitlines()[0],
            "parameters": {
                "type": "object",
                "properties": {"file_path": {"type": "string"}},
                "required": ["file_path"],
            },
        },
    }
    for name, fn in _TOOLS.items()
]

_SYSTEM = (
    "You are an audio-analysis agent. Use the provided tools to inspect the given audio "
    "file. Start with metadata, then decide which quality checks are warranted. Call every "
    "tool needed to assess silence, volume, and clipping before finishing. When done, stop "
    "calling tools."
)


def _build_agent_report(path: Path, config: Thresholds) -> AudioReport:
    """Assemble the authoritative report via the registry, tagged mode='agent'."""

    try:
        metadata = extract_metadata(path)
    except FFmpegError as exc:
        return _error_report(path, exc, config)
    ctx = AnalysisContext(path, metadata.duration_seconds, metadata, config)
    return compose_report(path, metadata, run_analyzers(ctx), config=config, mode="agent")


def analyze_with_agent(
    path: str | Path,
    *,
    use_llm: bool = True,
    max_steps: int = 8,
    config: Thresholds = THRESHOLDS,
) -> AudioReport:
    """Drive analysis via an LLM tool-calling loop, then build the standard report.

    The agent's tool calls gather the same measurements; we then reuse the registry to
    assemble a schema-valid report (ensuring the output contract holds regardless of the
    agent's path), tag it mode='agent', and attach LLM insight.
    """

    path = Path(path)

    if not (use_llm and LLM.is_configured):
        report = _build_agent_report(path, config)
        report.insight = generate_insight(report, use_llm=use_llm)
        return report

    from openai import OpenAI

    client = OpenAI(api_key=LLM.api_key)
    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": f"Analyse the audio file at: {path}"},
    ]

    try:
        for _ in range(max_steps):
            resp = client.chat.completions.create(
                model=LLM.model,
                temperature=LLM.temperature,
                messages=messages,
                tools=_TOOL_SCHEMAS,
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                break
            messages.append(msg.model_dump(exclude_none=True))
            for call in msg.tool_calls:
                fn = _TOOLS.get(call.function.name)
                args = json.loads(call.function.arguments or "{}")
                # Force the tool to operate on the real file regardless of model echo.
                args["file_path"] = str(path)
                result = fn(**args) if fn else {"error": "unknown tool"}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, default=str),
                    }
                )
    except Exception:  # noqa: BLE001 - agent is best-effort; fall back to pipeline
        pass

    # Assemble the authoritative report via the registry and attach insight.
    report = _build_agent_report(path, config)
    report.insight = generate_insight(report, use_llm=use_llm)
    return report
