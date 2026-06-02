"""Audio analysis detectors (silence, volume, clipping).

Each detector is a pure function over a file path (and parsed ffmpeg output), making
them independently testable and reusable by the CLI, the agent, and the MCP server.
"""

from .clipping import ClippingResult, detect_clipping
from .noise import NoiseResult, detect_noise
from .silence import detect_silence
from .volume import VolumeResult, detect_volume

__all__ = [
    "detect_silence",
    "detect_volume",
    "VolumeResult",
    "detect_clipping",
    "ClippingResult",
    "detect_noise",
    "NoiseResult",
]
