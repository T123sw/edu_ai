"""Offline, same-resident-model comparison; never changes the serving process."""
import os
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
import json
import time
import signal
from contextlib import nullcontext
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel
from services.local_tts.batching import bound_waveform_decode
from services.local_tts.voice_profile import (
    VOICE_PROFILE, VOICE_INSTRUCTIONS, GENERATION_OPTIONS,
    bind_request_sampling, request_sampling,
)
from services.local_tts.pitch import median_pitch, stabilize_pitch

ROOT = Path(__file__).resolve().parent
source = Path('docs/acceptance/2026-10-19-tts-concurrency/podcast-script.json')
script = json.loads(source.read_text())
segments = [script['segments'][i] for i in (0, 6)]
texts = [s['text'] for s in segments]
ROOT.mkdir(exist_ok=True)
(ROOT / 'texts.json').write_text(json.dumps(segments, ensure_ascii=False, indent=2))
results = {'source': str(source), 'pid': os.getpid(), 'device': 'cuda:0',
           'samples': [], 'runs': [], 'limitations': [
               'Two complete chapters, one batch per condition; no perceptual or ASR verdict.',
               'Waveform decoder memory safeguard shared across all conditions.',
               'Fixed seed for comparability, not a claim of identical random draws across conditions.',
           ]}
def persist():
    (ROOT / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
def deadline(*_):
    raise TimeoutError('Offline condition exceeded 300 seconds; not used as a successful sample')
signal.signal(signal.SIGALRM, deadline)
started = time.perf_counter()
model = Qwen3TTSModel.from_pretrained('/home/zxqs_ep/data/models/qwen3-tts',
    device_map='cuda:0', dtype=torch.bfloat16, local_files_only=True)
bound_waveform_decode(model)
bind_request_sampling(model)
torch.cuda.synchronize()
results['load_seconds'] = time.perf_counter() - started
results['official_defaults'] = model._merge_generate_kwargs()
results['attention'] = {name: getattr(part.config, '_attn_implementation', None)
                        for name, part in [('model', model.model), ('talker', model.model.talker)]}
results['parameter_devices'] = sorted({str(p.device) for p in model.model.parameters()})
persist()
print('LOADED', results['load_seconds'], results['attention'], flush=True)

# Exclude the one-time first-generation warmup from comparisons.
signal.alarm(120)
model.generate_custom_voice(text='这是一次语音测试。', speaker='vivian', language='chinese')
signal.alarm(0)
print('WARMED', flush=True)

for group, instruction, custom in [
    ('A_official', '', False),
    ('B_official_with_instruction', VOICE_INSTRUCTIONS, False),
    ('C_current_raw', VOICE_INSTRUCTIONS, True),
]:
    torch.manual_seed(20261019)
    torch.cuda.manual_seed_all(20261019)
    torch.cuda.synchronize()
    started = time.perf_counter()
    signal.alarm(300)
    print('START', group, flush=True)
    try:
        context = request_sampling([f'{VOICE_PROFILE}|vivian|chinese|{t}' for t in texts]) if custom else nullcontext()
        with context:
            wavs, sr = model.generate_custom_voice(text=texts, speaker=['vivian'] * len(texts),
                language=['chinese'] * len(texts), instruct=[instruction] * len(texts),
                **(GENERATION_OPTIONS if custom else {}))
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - started
        signal.alarm(0)
        results['runs'].append({'group': group, 'generation_seconds': elapsed,
                               'audio_seconds': sum(len(w) / sr for w in wavs)})
        # Store originals before CPU measurements and post-processing.
        for i, wav in enumerate(wavs):
            sf.write(ROOT / f'{group}-{i}.wav', wav, sr, subtype='FLOAT')
        persist()
        print('GENERATED', group, round(elapsed, 2), [round(len(w) / sr, 2) for w in wavs], flush=True)
        for i, wav in enumerate(wavs):
            pitch = median_pitch(wav, sr)
            row = {'group': group, 'index': i, 'chars': len(texts[i]),
                   'duration': len(wav) / sr, 'pitch_median_hz': pitch,
                   'rms': float(np.sqrt(np.mean(wav ** 2)))}
            results['samples'].append(row)
            if custom:
                tick = time.perf_counter()
                aligned = stabilize_pitch(wav, sr, 'vivian')
                process_seconds = time.perf_counter() - tick
                sf.write(ROOT / f'D_current_aligned-{i}.wav', aligned, sr, subtype='FLOAT')
                results['samples'].append({**row, 'group': 'D_current_aligned',
                    'duration': len(aligned) / sr,
                    'rms': float(np.sqrt(np.mean(aligned ** 2))),
                    'pitch_median_hz': median_pitch(aligned, sr),
                    'processing_seconds': process_seconds,
                    'requested_shift_semitones': float(np.clip(12 * np.log2(240 / pitch), -3, 3)) if pitch else None})
            persist()
        print('MEASURED', group, flush=True)
    except Exception as exc:
        signal.alarm(0)
        results['runs'].append({'group': group, 'error': type(exc).__name__ + ': ' + str(exc),
                               'elapsed': time.perf_counter() - started})
        persist()
        raise
print('COMPLETE', flush=True)
