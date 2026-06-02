"""FastMCP server exposing audioscope's analysis tools.

Run with:  python -m audioscope.mcp_server
or:        fastmcp run audioscope/mcp_server.py

This lets any MCP client (e.g. Claude Desktop) drive ffmpeg-based audio analysis. The
tools are the same reusable functions used by the CLI and the agent; the MCP layer is a
thin adapter, demonstrating that the analysis was designed as composable units.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from .pipeline import analyze_file
from .tools import (
    detect_clipping_tool,
    detect_noise_tool,
    detect_silence_tool,
    detect_volume_tool,
    get_audio_metadata,
)

mcp = FastMCP("audioscope")


@mcp.tool
def get_metadata(file_path: str) -> dict[str, Any]:
    """Extract audio metadata (duration, bitrate, sample rate, channels) via ffprobe."""

    return get_audio_metadata(file_path)


@mcp.tool
def detect_silence(file_path: str) -> dict[str, Any]:
    """Detect silence segments and the overall silence ratio via ffmpeg silencedetect."""

    return detect_silence_tool(file_path)


@mcp.tool
def detect_clipping(file_path: str) -> dict[str, Any]:
    """Detect likely clipping/distortion from peak levels via ffmpeg volumedetect."""

    return detect_clipping_tool(file_path)


@mcp.tool
def measure_volume(file_path: str) -> dict[str, Any]:
    """Measure mean and peak volume in dBFS via ffmpeg volumedetect."""

    return detect_volume_tool(file_path)


@mcp.tool
def estimate_noise(file_path: str) -> dict[str, Any]:
    """Estimate RMS level and noise floor (dBFS) via ffmpeg astats."""

    return detect_noise_tool(file_path)


@mcp.tool
def analyze_audio(file_path: str) -> dict[str, Any]:
    """Run the full analysis pipeline and return the complete structured report."""

    return analyze_file(file_path).model_dump()


if __name__ == "__main__":  # pragma: no cover
    mcp.run()
