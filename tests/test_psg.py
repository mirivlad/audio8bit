"""Tests for three-channel AY/YM musical PSG approximation."""
import numpy as np
import pytest

from audio8bit import converter as c
from audio8bit import psg


def test_clock_divider_and_twelve_bit_period():
    ay_hz, ay_period = psg.tone_frequency(69, "ay")
    ym_hz, ym_period = psg.tone_frequency(69, "ym")
    assert 1 <= ay_period <= 4095
    assert 1 <= ym_period <= 4095
    assert abs(ay_hz - 440) < 2
    assert abs(ym_hz - 440) < 2
    assert ay_period != ym_period
    assert psg.tone_frequency(180, "ay")[1] == 1
    assert psg.tone_frequency(-80, "ym")[1] == 4095


def test_chip_envelope_steps_distinguish_ay_and_ym():
    ay = psg.stepped_envelope(4000, 22050, "ay")
    ym = psg.stepped_envelope(4000, 22050, "ym")
    assert len(np.unique(ay)) <= 16
    assert len(np.unique(ym)) <= 32
    assert len(np.unique(ym)) > len(np.unique(ay))
    assert not np.array_equal(ay, ym)


def test_only_three_hardware_tone_channels():
    assert psg.CHANNEL_COUNT == 3
    assert set(psg.CLOCKS) == {"ay", "ym"}


@pytest.mark.parametrize("chip", ["ay", "ym"])
def test_render_is_finite_deterministic_and_preserves_duration(chip):
    kw = dict(
        chip=chip, events=[(0.0, .4, 72, .9)],
        rate=8000, duration=3.0,
        lead_notes=[[0.0, .35, 72], [1.0, .4, 74]],
        bass_notes=[[0.0, .9, 42]], chords=[(0.0, 2.0, 0, (0,4,7))],
        drum_hits=[(.5, "snare", .9), (1.0, "kick", 1.0)],
        tempo=120,
    )
    first = psg.render_psg(**kw)
    second = psg.render_psg(**kw)
    assert first.size == 24000
    assert np.isfinite(first).all()
    assert np.max(np.abs(first)) > .01
    assert np.max(np.abs(first)) <= .91
    assert np.array_equal(first, second)


def test_ay_and_ym_do_not_sound_identical():
    kw = dict(events=[(0, .5, 72, .9)], rate=8000, duration=1,
              lead_notes=[[0,.5,72]], bass_notes=[], chords=[], drum_hits=[])
    assert not np.array_equal(psg.render_psg(chip="ay", **kw),
                              psg.render_psg(chip="ym", **kw))


def test_convert_choices_are_available():
    assert {"ay", "ym"} <= set(c.VOICES_CHOICES)
