"""Regression tests for the new, section-aware chiptune arrangement."""
import numpy as np
from audio8bit import converter as c


def test_auto_transcription_switches_stems_per_passage(monkeypatch):
    sr = 100
    voice = np.concatenate((np.zeros(300), np.full(300, 0.8)))
    backing = np.concatenate((np.full(300, 0.8), np.full(300, 0.2)))
    vocal_notes = [(0.25, 0.75, 74, .9), (3.25, 3.75, 76, .9)]
    other_notes = [(0.25, 0.75, 60, .8), (3.25, 3.75, 62, .8)]
    monkeypatch.setattr(c, "transcribe_notes", lambda signal, _: (
        vocal_notes if signal is voice else other_notes))
    chosen, accompaniment, label = c.transcribe_auto_stems(
        {"vocals":voice, "other":backing}, sr)
    assert [event[2] for event in chosen] == [60,76]
    assert accompaniment == other_notes
    assert "1/2" in label


def test_pulsed_chords_have_audible_gaps():
    chords=[(0.,1.,0,(0,4,7))]
    wav = c.render_chord_pad(chords, 8000, 0, 8000, pulse_step=.25)
    assert np.max(np.abs(wav[200:1000])) > 0.01
    assert np.max(np.abs(wav[1650:1950])) == 0


def test_renderer_preserves_full_source_length_with_short_notes():
    events = [(0., 1., 72, .9)]
    wav = c.render_band(events, 8000, lead_notes=[[0.,.8,72]],
                        bass_notes=[], drum_hits=[], chords=[],
                        echo_delay=0, duration=7)
    assert wav.size >= 7 * 8000
    assert np.max(np.abs(wav[0:8000])) > 0.01


def test_nes_arpeggio_uses_tempo_relative_step():
    chords=[(0.,1.,0,(0,4,7))]
    slow=c.render_chord_arp(chords,8000,0,8000,step=.25)
    fast=c.render_chord_arp(chords,8000,0,8000,step=.125)
    assert not np.array_equal(slow, fast)
