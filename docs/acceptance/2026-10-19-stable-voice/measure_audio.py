"""Pitch diagnostics, not a substitute for timbre listening or word-level ASR."""
from pathlib import Path
import json,subprocess
import numpy as np
import soundfile as sf
import librosa
root=Path('docs/acceptance/2026-10-19-stable-voice');records=json.loads((root/'real-model.json').read_text());results=[]
for item in records:
 path=root/'audio'/item['name'];signal,sr=sf.read(path)
 decoded=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],capture_output=True,text=True)
 assert decoded.returncode==0 and not decoded.stderr
 y=librosa.resample(signal,orig_sr=sr,target_sr=8000)
 f0,voiced,prob=librosa.pyin(y,sr=8000,fmin=75,fmax=500,frame_length=1024,hop_length=160)
 valid=f0[voiced & (prob>.7) & np.isfinite(f0)]
 if len(valid)<20:valid=f0[voiced & np.isfinite(f0)]
 assert len(valid)>10,item['name']
 row={'name':item['name'],'duration':item['duration'],'median_hz':round(float(np.median(valid)),2),'p10_hz':round(float(np.percentile(valid,10)),2),'p90_hz':round(float(np.percentile(valid,90)),2),'voiced_frames':len(valid)}
 results.append(row);print(json.dumps(row),flush=True)
groups={}
for name in ['baseline','stable','repeat','long']:
 values=[r['median_hz'] for r in results if r['name'].startswith(name+'-')]
 if not values:continue
 groups[name]={'median_hz':values,'range_hz':round(max(values)-min(values),2),'cv':round(float(np.std(values)/np.mean(values)),4)}
comparisons=[]
for a,b in [('repeat-0.wav','repeat-1.wav'),('stable-0.wav','repeat-0.wav'),('stable-1.wav','repeat-2.wav')]:
 if not (root/'audio'/a).exists() or not (root/'audio'/b).exists():continue
 aa,_=sf.read(root/'audio'/a);bb,_=sf.read(root/'audio'/b)
 comparisons.append({'a':a,'b':b,'same_pcm':bool(np.array_equal(aa,bb)),'samples_a':len(aa),'samples_b':len(bb)})
result={'measurements':results,'groups':groups,'repeatability':comparisons,'limitations':'F0 measures pitch, not speaker identity or intelligibility; no ASR or human listening result is claimed.'}
(root/'acoustic-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({'groups':groups,'repeatability':comparisons}),flush=True)
