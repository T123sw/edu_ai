import numpy as np
import pytest

from services.local_tts.pitch import median_pitch, stabilize_pitch


def test_pitch_alignment_keeps_duration_and_natural_pitch_contour():
    sr = 24000
    t = np.arange(sr * 3) / sr
    frequency = 210 + 12 * np.sin(2 * np.pi * 2 * t)
    phase = np.cumsum(2 * np.pi * frequency / sr)
    audio = (.2 * np.sin(phase) + .1 * np.sin(phase*2)).astype(np.float32)
    output = stabilize_pitch(audio, sr, 'vivian')
    assert abs(len(output)-len(audio)) < sr * .1
    assert median_pitch(output, sr) == pytest.approx(240, abs=8)
    assert np.isfinite(output).all() and np.max(np.abs(output)) <= 1


def test_uncalibrated_speaker_is_not_forced_to_vivian_pitch():
    audio = np.zeros(24000, dtype=np.float32)
    assert stabilize_pitch(audio, 24000, 'ryan') is audio
