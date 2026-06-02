"""Unit tests for the stderr parsers (pure string parsing, no ffmpeg needed)."""

from __future__ import annotations

from audioscope.analysis.silence import merge_segments, parse_silence, silence_ratio
from audioscope.analysis.volume import parse_volume
from audioscope.models import SilenceSegment

SILENCE_STDERR = """\
[silencedetect @ 0x1] silence_start: 3.36
[silencedetect @ 0x1] silence_end: 5.33 | silence_duration: 1.97
[silencedetect @ 0x1] silence_start: 10.0
[silencedetect @ 0x1] silence_end: 12.0 | silence_duration: 2.0
"""

VOLUME_STDERR = """\
[Parsed_volumedetect_0 @ 0x1] n_samples: 1937722
[Parsed_volumedetect_0 @ 0x1] mean_volume: -16.6 dB
[Parsed_volumedetect_0 @ 0x1] max_volume: -0.4 dB
[Parsed_volumedetect_0 @ 0x1] histogram_0db: 779
"""


def test_parse_silence_pairs_segments():
    segs = parse_silence(SILENCE_STDERR, total_duration=20.0)
    assert len(segs) == 2
    assert segs[0].start_seconds == 3.36
    assert segs[0].end_seconds == 5.33


def test_parse_silence_closes_trailing_segment_at_duration():
    stderr = "silence_start: 8.0\n"
    segs = parse_silence(stderr, total_duration=10.0)
    assert len(segs) == 1
    assert segs[0].end_seconds == 10.0


def test_parse_silence_drops_trailing_when_duration_unknown():
    segs = parse_silence("silence_start: 8.0\n", total_duration=None)
    assert segs == []


def test_merge_segments_combines_close_neighbours():
    segs = [
        SilenceSegment(start_seconds=0.0, end_seconds=1.0),
        SilenceSegment(start_seconds=1.2, end_seconds=2.0),  # gap 0.2 <= 0.5
        SilenceSegment(start_seconds=5.0, end_seconds=6.0),  # far away
    ]
    merged = merge_segments(segs, gap=0.5)
    assert len(merged) == 2
    assert merged[0].end_seconds == 2.0


def test_silence_ratio():
    segs = [SilenceSegment(start_seconds=0.0, end_seconds=5.0)]
    assert silence_ratio(segs, 20.0) == 0.25
    assert silence_ratio(segs, None) == 0.0


def test_parse_volume():
    v = parse_volume(VOLUME_STDERR)
    assert v.mean_db == -16.6
    assert v.max_db == -0.4
    assert v.samples_at_0db == 779
