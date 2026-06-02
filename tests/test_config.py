"""Tests for external JSON config loading and threshold overrides."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from audioscope.config import THRESHOLDS, Thresholds, load_config


def test_load_config_none_returns_defaults():
    assert load_config(None) is THRESHOLDS


def test_from_dict_overrides_and_ignores_unknown():
    cfg = Thresholds.from_dict({"silence_noise_db": -40.0, "bogus_key": 123})
    assert cfg.silence_noise_db == -40.0
    # Untouched field keeps its default; unknown key is ignored (no crash).
    assert cfg.low_bitrate_bps == THRESHOLDS.low_bitrate_bps


def test_load_config_from_file(tmp_path: Path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"high_silence_ratio": 0.1, "long_silence_seconds": 2.0}))
    cfg = load_config(p)
    assert cfg.high_silence_ratio == 0.1
    assert cfg.long_silence_seconds == 2.0


def test_load_config_rejects_non_object(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("[1, 2, 3]")
    with pytest.raises(ValueError):
        load_config(p)


def test_to_dict_roundtrips():
    cfg = Thresholds(silence_noise_db=-33.0)
    assert Thresholds.from_dict(cfg.to_dict()).silence_noise_db == -33.0
