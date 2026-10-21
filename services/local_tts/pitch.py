"""Conservative whole-utterance pitch alignment with preserved formants."""
import logging
import os
import subprocess
from functools import lru_cache

import librosa
import numpy as np

log = logging.getLogger('local_tts')
# Calibrated for the system's current Vivian narrator. Other selected speakers
# keep their own pitch until a reference profile has been measured for them.
PITCH_TARGETS = {'vivian': 240.0}


@lru_cache(maxsize=1)
def validate_pitch_runtime():
    # The conda FFmpeg on this host lacks librubberband; use the explicitly
    # configured system build instead of depending on the service's PATH.
    binary = os.getenv('QWEN_TTS_PITCH_FFMPEG', '/usr/bin/ffmpeg')
    checked = subprocess.run([binary, '-hide_banner', '-h', 'filter=rubberband'],
                             capture_output=True, text=True, check=True, timeout=10)
    if 'formant' not in checked.stdout + checked.stderr:
        raise RuntimeError('Pitch stabilization requires FFmpeg with the rubberband filter')
    return binary


def median_pitch(audio, sample_rate):
    signal = librosa.resample(audio, orig_sr=sample_rate, target_sr=8000)
    f0, voiced, probability = librosa.pyin(
        signal, sr=8000, fmin=75, fmax=500, frame_length=1024, hop_length=160,
    )
    valid = f0[voiced & (probability > .7) & np.isfinite(f0)]
    if len(valid) < 20:
        valid = f0[voiced & np.isfinite(f0)]
    return float(np.median(valid)) if len(valid) >= 10 else None


def stabilize_pitch(audio, sample_rate, voice):
    target = PITCH_TARGETS.get(voice.strip().lower())
    if target is None:
        return audio
    measured = median_pitch(audio, sample_rate)
    if measured is None:
        log.warning('tts_pitch_unvoiced voice=%s', voice)
        return audio
    semitones = float(np.clip(12 * np.log2(target / measured), -3, 3))
    if abs(semitones) < .1:
        return audio
    ratio = 2 ** (semitones / 12)
    # A single factor keeps the sentence's intonation contour. Rubber Band's
    # formant preservation avoids the chipmunk/deepened-vowel effect of simple
    # resampling; tempo stays 1 and the authored text is never cut.
    process = subprocess.run([
        validate_pitch_runtime(), '-v', 'error', '-f', 'f32le', '-ar', str(sample_rate), '-ac', '1',
        '-i', 'pipe:0', '-af',
        f'rubberband=tempo=1:pitch={ratio:.9f}:formant=preserved:pitchq=quality',
        '-f', 'f32le', 'pipe:1',
    ], input=np.asarray(audio, dtype='<f4').tobytes(), capture_output=True,
        check=True, timeout=90)
    result = np.frombuffer(process.stdout, dtype='<f4').copy()
    if not result.size or not np.isfinite(result).all() or abs(len(result)-len(audio)) > sample_rate * .1:
        raise RuntimeError('invalid pitch-aligned audio')
    peak = np.max(np.abs(result))
    if peak > .99:
        result *= .99 / peak
    log.info('tts_pitch_aligned voice=%s source_hz=%.2f target_hz=%.2f shift_semitones=%.3f',
             voice, measured, target, semitones)
    return result
