"""Central configuration: env loading, model names, and analysis thresholds.

All tunable numbers live here so detectors stay free of magic constants and the
behaviour of the pipeline is auditable in one place.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

# Load credentials from a .env file (project root or current working directory). We set
# these into the environment so a stale OPENAI_API_KEY exported in the shell can't shadow
# the project's key; the first file to define a key wins.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_seen: set[str] = set()
for _candidate in (_PROJECT_ROOT / ".env", Path.cwd() / ".env"):
    if not _candidate.exists():
        continue
    for _key, _val in dotenv_values(_candidate).items():
        if _val is not None and _key not in _seen:
            os.environ[_key] = _val
            _seen.add(_key)


@dataclass(frozen=True)
class Thresholds:
    """Tunable detection thresholds with documented rationale.

    Defaults are tuned for spoken-word and general audio, where intelligibility
    matters more than music-grade fidelity. Every field can be
    overridden from a JSON file via :func:`load_config`, and the effective values are
    recorded in each report's ``analysis_metadata`` for reproducibility.
    """

    # silencedetect: noise floor and minimum silence duration (seconds).
    silence_noise_db: float = -30.0
    silence_min_duration: float = 1.0
    # Merge silence segments separated by less than this gap (seconds).
    silence_merge_gap: float = 0.5
    # Flag the file as "mostly silent" above this ratio.
    high_silence_ratio: float = 0.30
    # A single silence at/above this length is called out individually (seconds).
    long_silence_seconds: float = 5.0

    # volumedetect: mean volume below this is considered unusually low (dBFS).
    low_mean_volume_db: float = -30.0
    # Peak at or above this is treated as likely clipping (near 0 dBFS).
    clipping_peak_db: float = -1.0
    # Peak at/above this gives "high" clipping confidence.
    high_confidence_clipping_db: float = -0.1
    # Number of max-level samples above which clipping is more strongly indicated.
    clipping_sample_count: int = 100

    # astats: noise floor above this (dBFS) is flagged as elevated background noise.
    elevated_noise_floor_db: float = -45.0
    # Skip the (slower) astats pass on files longer than this, to bound cost.
    max_astats_duration_seconds: float = 4 * 60 * 60

    # Bitrate below this (bits/s) is flagged as low quality for the sample rate.
    low_bitrate_bps: int = 64_000

    def to_dict(self) -> dict[str, float | int]:
        from dataclasses import asdict

        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, object]) -> Thresholds:
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in values.items() if k in allowed})  # type: ignore[arg-type]


def load_config(path: str | Path | None) -> Thresholds:
    """Load thresholds from a JSON file, falling back to defaults.

    Unknown keys are ignored so config files can carry comments/extra fields without
    breaking. This makes behaviour tunable as *data*, with no code change.
    """

    if path is None:
        return THRESHOLDS
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Config file must contain a JSON object.")
    return Thresholds.from_dict(data)


@dataclass(frozen=True)
class LLMConfig:
    """LLM provider configuration. OpenAI by default (key present in workspace)."""

    provider: str = os.getenv("AUDIOSCOPE_LLM_PROVIDER", "openai")
    api_key: str | None = os.getenv("OPENAI_API_KEY")
    # Cheap model for per-file insight; a stronger one can be set for aggregation.
    model: str = os.getenv("AUDIOSCOPE_LLM_MODEL", "gpt-4o-mini")
    temperature: float = 0.2

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


THRESHOLDS = Thresholds()
LLM = LLMConfig()
ANALYSIS_VERSION = "1.0.0"
