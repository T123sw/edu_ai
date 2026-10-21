from pathlib import Path
import json,time,subprocess
import numpy as np
import soundfile as sf
from services.local_tts.pitch import stabilize_pitch,median_pitch
root=Path('docs/acceptance/2026-10-19-stable-voice');records=json.loads((root/'real-model.json').read_text());result=[]
for row in records:
 if row['name'].startswith('baseline-'):continue
 audio,sr=sf.read(root/'audio'/row['name']);start=time.monotonic()
 before=median_pitch(audio,sr);fixed=stabilize_pitch(audio,sr,'vivian');after=median_pitch(fixed,sr)
 path=root/'audio'/('aligned-'+row['name']);sf.write(path,fixed,sr)
 assert abs(len(fixed)-len(audio))<sr*.1 and np.isfinite(fixed).all()
 assert after is not None and abs(after-240)<15,(row['name'],before,after)
 p=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],capture_output=True,text=True);assert p.returncode==0 and not p.stderr
 item={'source':row['name'],'output':path.name,'before_hz':round(before,2),'after_hz':round(after,2),'source_duration':len(audio)/sr,'output_duration':len(fixed)/sr,'seconds':round(time.monotonic()-start,2)}
 result.append(item);print(json.dumps(item),flush=True)
 (root/'pitch-alignment.json').write_text(json.dumps(result,indent=2))
print('PITCH_ALIGNMENT_PASSED',flush=True)
