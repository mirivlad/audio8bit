"""AY-3-8910/8912 and Yamaha YM2149F-inspired 3-channel chip renderer.

These are *musical approximations*, not a cycle-accurate bus/register emulator
and not a .AY/.YM tracker exporter. Both PSGs have three 50%-duty tone
generators and a single noise source which can be mixed into the tone channels.
We time-share channel C between harmony and percussion, rather than cheating
with an independent drum audio track or a fourth synth voice.

ZX Spectrum AY-3-8912: 1,773,400 Hz. Atari ST Yamaha YM2149F: 2,000,000 Hz.
Both use 12-bit tone periods and 16 manually addressed amplitude levels. The
Yamaha's hardware envelope provides 32 steps versus the AY's 16. Our envelopes
approximate those stepped hardware shapes, and AC-coupled outputs omit DC.
"""
from __future__ import annotations

import numpy as np

CLOCKS = {"ay": 1_773_400.0, "ym": 2_000_000.0}
LEVELS = {"ay": 16, "ym": 32}
CHANNEL_COUNT = 3
NOISE_SEED = 0x8910


def tone_frequency(midi: float, chip: str) -> tuple[float, int]:
    """Nearest representable 12-bit PSG tone period and resulting frequency."""
    if chip not in CLOCKS:
        raise ValueError(f"Unknown chip: {chip}")
    hz = 440.0 * (2.0 ** ((float(midi) - 69.0) / 12.0))
    period = int(np.clip(np.rint(CLOCKS[chip] / (16.0 * hz)), 1, 4095))
    return CLOCKS[chip] / (16.0 * period), period


def stepped_envelope(count: int, rate: int, chip: str, *,
                     attack=0.004, release=0.020, sustain=0.65) -> np.ndarray:
    """Single envelope approximating AY16 / YM32 hardware dynamics."""
    if chip not in LEVELS:
        raise ValueError(f"Unknown chip: {chip}")
    if count <= 0:
        return np.zeros(0, dtype=np.float32)
    length = count / rate
    t = np.arange(count, dtype=np.float32) / rate
    rising = np.minimum(1.0, t / max(attack, 1 / rate))
    falling = sustain + (1 - sustain) * np.exp(-t / max(0.045, length * 0.35))
    fade = np.minimum(1.0, np.maximum(0.0, (length - t) / max(release, 1 / rate)))
    envelope = np.clip(rising * falling * fade, 0.0, 1.0)
    steps = LEVELS[chip] - 1
    # Approximation of a logarithmic hardware DAC, not empirical resistor values.
    return (np.rint(envelope * steps) / steps) ** 1.6


def _put_note(channel: np.ndarray, *, start: float, duration: float,
              midi: float, rate: int, chip: str, transpose: int,
              gain: float, sustain=0.65):
    """Render one AC-coupled 50% pulse; no pulse-width knob on AY or YM."""
    first = max(0, int(start * rate))
    last = min(channel.size, int((start + duration) * rate))
    count = last - first
    if count < 2:
        return
    frequency, _period = tone_frequency(midi + transpose, chip)
    # Pulse waveform is synthesized with harmonic band limiting; the hardware
    # signal is a binary gate but direct aliasing on a PC DAC is undesirable.
    from audio8bit.converter import band_limited_pulse
    times = np.arange(count, dtype=np.float64) / rate
    wave = band_limited_pulse(2.0 * np.pi * frequency * times,
                              frequency, rate, 0.5)
    channel[first:last] += (wave * stepped_envelope(
        count, rate, chip, sustain=sustain) * gain).astype(np.float32)


def _percussion_noise(count: int, rate: int, clock: float, kind: str,
                      rng: np.random.Generator) -> np.ndarray:
    """Shared PSG-style stepped noise approximating noise register periods.

    A single pseudo-random noise clock is retuned for each hit. Exact LFSR
    bit patterns and analog DC coupling are intentionally not modeled yet.
    """
    periods = {"kick": 30, "snare": 11, "hat": 3}
    period = periods.get(kind, 11)
    frequency = clock / (16 * period)
    # One binary noise value for each *noise clock*, reused for the samples
    # until the next tick. A short attack-less envelope makes a percussion hit.
    ticks = np.floor(np.arange(count) * (frequency / rate)).astype(np.int64)
    states = rng.integers(0, 2, size=int(ticks[-1]) + 1, dtype=np.int8)
    noise = (2 * states[ticks].astype(np.float32) - 1.0)
    time = np.arange(count, dtype=np.float32) / rate
    decay = {"kick": 0.040, "snare": 0.029, "hat": 0.008}.get(kind, 0.029)
    return noise * np.exp(-time / decay)


def render_psg(*, events, rate: int, chip: str, lead_notes=None,
               bass_notes=None, chords=None, drum_hits=None,
               transpose=0, tempo=120.0, duration=None) -> np.ndarray:
    """Render lead A, bass B, harmony/percussion C using three PSG channels.

    Input notes use [start, duration, midi] and chords are
    [(start, end, root_pc, pitch_classes)]. Melody is never sacrificed to
    drums. Noise *replaces* channel C briefly, rather than adding a fourth
    channel. Output is an approximate AY/YM mono mix for WAV/MP3 export.
    """
    if chip not in CLOCKS:
        raise ValueError(f"Unknown chip: {chip}")
    events = events or []
    span = float(duration or 0)
    if events:
        span = max(span, max(end for start, end, pitch, amplitude in events))
    for notes in (lead_notes or [], bass_notes or []):
        # Notes are [start, duration, pitch] triples; consider every note,
        # not the first nested list as if it were a single note.
        for note in notes:
            span = max(span, float(note[0]) + float(note[1]))
    for start, end, root, pcs in (chords or []):
        span = max(span, float(end))
    for onset, kind, velocity in (drum_hits or []):
        span = max(span, float(onset) + 0.12)
    total = max(1, int(np.ceil(span * rate)))
    channels = [np.zeros(total, dtype=np.float32) for _ in range(CHANNEL_COUNT)]

    if lead_notes is None:
        from audio8bit.converter import melody_line
        lead_notes = melody_line(events)
    if bass_notes is None:
        from audio8bit.converter import bass_line
        bass_notes = bass_line(events)
    for note in lead_notes:
        _put_note(channels[0], start=note[0], duration=note[1], midi=note[2],
                  rate=rate, chip=chip, transpose=transpose, gain=0.55,
                  sustain=0.75)
    for note in bass_notes:
        _put_note(channels[1], start=note[0], duration=note[1], midi=note[2],
                  rate=rate, chip=chip, transpose=transpose, gain=0.37,
                  sustain=0.55)

    beat = 60 / max(float(tempo), 30)
    arpeggio_step = max(0.055, beat / 4)
    if chords:
        # One tone at a time on C. The periods are quantized to the original
        # chip clock. NES-style chords must not be rendered simultaneously.
        for left, right, root_pc, pcs in chords:
            from audio8bit.converter import voice_pitch
            notes = sorted(voice_pitch(pc) for pc in pcs)
            ladder = notes + [min(notes) + 12]
            n = 0
            moment = max(0.0, float(left))
            while moment < right - 1e-6:
                duration_note = min(arpeggio_step * 0.76, right - moment)
                _put_note(channels[2], start=moment, duration=duration_note,
                          midi=ladder[n % len(ladder)], rate=rate,
                          chip=chip, transpose=transpose, gain=0.25,
                          sustain=0.6)
                moment += arpeggio_step
                n += 1
    else:
        # Render a sparse broken chord from the actual transcription if the
        # harmony detector had no confident progression.
        from audio8bit.converter import render_arp
        channels[2][:] = render_arp(events, rate, transpose, total,
                                   step=arpeggio_step).astype(np.float32) * 0.45

    rng = np.random.default_rng(NOISE_SEED)
    for onset, kind, velocity in sorted(drum_hits or [], key=lambda hit: hit[0]):
        duration_hit = {"kick": .10, "snare": .07, "hat": .035}.get(kind, .07)
        first = max(0, int(onset * rate))
        last = min(total, first + max(1, int(duration_hit * rate)))
        count = last - first
        if count < 1:
            continue
        # Noise is mixed into C while its tone is disabled (time sharing).
        # Even multiple simultaneous hits cannot create extra PSG channels.
        if kind == "kick":
            noise_gain = 0.28
        elif kind == "hat":
            noise_gain = 0.15
        else:
            noise_gain = 0.23
        channels[2][first:last] = _percussion_noise(
            count, rate, CLOCKS[chip], kind, rng) * (
                noise_gain * max(0, min(float(velocity), 1.0)))

    # Each channel retains a separate hardware-style amplitude curve. Mix to
    # a mono recording then remove DC and limit for ordinary media playback.
    mix = (channels[0] + channels[1] + channels[2]).astype(np.float32)
    peak = float(np.max(np.abs(mix)))
    if peak > 0.90:
        mix *= 0.90 / peak
    return mix
