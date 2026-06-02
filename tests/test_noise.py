"""Tests for astats noise/RMS parsing (pure string parsing)."""

from __future__ import annotations

from audioscope.analysis.noise import parse_astats

ASTATS_FINITE = """\
[Parsed_astats_0 @ 0x1] RMS level dB: -16.605719
[Parsed_astats_0 @ 0x1] Noise floor dB: -52.3
[Parsed_astats_0 @ 0x1] RMS level dB: -16.605719
[Parsed_astats_0 @ 0x1] Noise floor dB: -52.3
"""

ASTATS_INF_NOISE = """\
[Parsed_astats_0 @ 0x1] RMS level dB: -16.605719
[Parsed_astats_0 @ 0x1] Noise floor dB: -inf
"""


def test_parse_astats_finite():
    r = parse_astats(ASTATS_FINITE)
    assert r.rms_level_db == -16.605719
    assert r.noise_floor_db == -52.3


def test_parse_astats_inf_noise_floor_is_none():
    # A -inf noise floor is surfaced as None rather than a misleading number.
    r = parse_astats(ASTATS_INF_NOISE)
    assert r.rms_level_db == -16.605719
    assert r.noise_floor_db is None


def test_parse_astats_empty():
    r = parse_astats("")
    assert r.rms_level_db is None
    assert r.noise_floor_db is None
