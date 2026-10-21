"""Read finished native artifacts into the existing player contract; no authoring."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import zipfile

from .contracts import safe_path, validate_content
from .runtime import NativeRuntime, RUNTIME, UPSTREAM, run_process


def native_storyboard(project):
    file = Path(project)/'STORYBOARD.md'
    if not file.exists(): return {'frames': []}
    parser = UPSTREAM/'skills/faceless-explainer/scripts/lib/storyboard.mjs'
    code = 'import {readFileSync} from "node:fs";import {parseStoryboard} from '+json.dumps(parser.as_uri())+';console.log(JSON.stringify(parseStoryboard(readFileSync(process.argv[1],"utf8"))));'
    return json.loads(run_process([shutil.which('node'), '--input-type=module','-e',code,str(file)], timeout=30))


def script_lines(project):
    file = Path(project)/'SCRIPT.md'
    result, current = {}, None
    if not file.exists(): return result
    for line in file.read_text().splitlines():
        heading = re.match(r'^#{2,3}\s+.*?\(frame\s+(\d+)\)',line,re.I) or re.match(r'^#{2,3}\s+(?:Frame|Scene)\s+(\d+)\b',line,re.I)
        if heading:
            current = int(heading[1]);result[current] = ''
        elif current is not None and not re.match(r'^\s*\*\*',line):
            spoken = re.match(r'^(?: {4,}|\t)(.+)$',line)
            if spoken: result[current] += (' ' if result[current] else '')+spoken[1].strip()
    return result


def native_captions(project):
    """Read only project-level subtitle tracks; per-scene cues may use local time."""
    for name in ('subtitles.srt', 'captions.srt', 'narration.srt', 'subtitles.vtt', 'captions.vtt'):
        file = Path(project)/name
        if not file.exists(): continue
        text = file.read_text(encoding='utf-8-sig')
        def seconds(value):
            parts = [float(p) for p in value.replace(',', '.').split(':')]
            return sum(v*60**i for i, v in enumerate(reversed(parts)))
        cues = []
        for block in re.split(r'\n\s*\n', text.strip()):
            match = re.search(r'([\d:]+[.,]\d+)\s+-->\s+([\d:]+[.,]\d+)[^\n]*\n(.*)', block, re.S)
            if match:
                cues.append({'start': seconds(match[1]), 'end': seconds(match[2]), 'text': re.sub('<[^>]+>', '', match[3]).strip()})
        if cues: return file, cues
    return None, []


def timeline_from_project(project, *, title, duration):
    project = Path(project)
    storyboard = native_storyboard(project)
    spoken = script_lines(project)
    audio_file = project/'audio_meta.json'
    voices = json.loads(audio_file.read_text()).get('voices', []) if audio_file.exists() else []
    request_file = project/'audio_request.json'
    lines = json.loads(request_file.read_text()).get('lines', []) if request_file.exists() else []
    narration_by_id = {str(line['id']): str(line.get('text', '')) for line in lines}
    _, cues = native_captions(project)
    mounts, audio = [], []
    class Reader(HTMLParser):
        def handle_starttag(self, tag, values):
            row = dict(values)
            if row.get('data-composition-src'): mounts.append(row)
            if tag == 'audio' and row.get('src'): audio.append(row)
    Reader().feed((project/'index.html').read_text())
    frames = storyboard['frames']
    segments = []
    for mount in mounts:
        src = mount['data-composition-src']
        frame = next((f for f in frames if f.get('src') == src), None)
        # Captions/transitions are native compositions, but not teaching segments.
        if frame is None:
            # Generic native compositions need not use the explainer's script format.
            if frames or re.search(r'caption|transition|subtitle', src, re.I): continue
            frame = {'index': len(segments)+1, 'title': mount.get('data-composition-id') or Path(src).stem}
        start = float(mount.get('data-start',0)); end = start+float(mount['data-duration'])
        number = frame.get('number', frame['index'])
        scene_id = mount.get('data-composition-id') or Path(src).stem
        identities = {str(number), scene_id, Path(src).stem, str(frame.get('id', ''))} - {''}
        native_voice = next((v for v in voices if str(v.get('frame', v.get('id'))) in identities), None)
        voice = next((a for a in audio if native_voice and a['src'] == native_voice.get('path')), None)
        if voice is None and not voices:
            voice = next((a for a in audio if abs(float(a.get('data-start',0))-start)<.01
                          and float(a.get('data-duration',0)) <= end-start+.1), None)
        segment = {'id': mount.get('data-composition-id') or 'frame-'+str(number),
            'title': frame.get('title') or f'Frame {number}', 'start':start, 'end':min(end,duration),
            'narration': next((narration_by_id[key] for key in (str(native_voice.get('id')) if native_voice else '', scene_id, str(number), Path(src).stem) if narration_by_id.get(key)), '') or spoken.get(number) or frame.get('voiceover',''),
            'visual_description': frame.get('scene') or frame.get('narrative',''),
            'objective_ids':[], 'source_ids':[], 'events':[]}
        if voice: segment['audio_path'] = safe_path(voice['src'])
        if not segment['narration'] and cues:
            segment['narration'] = '\n'.join(c['text'] for c in cues if c['start'] < segment['end'] and c['end'] > start)
        segments.append(segment)
    if not segments:
        # A native general-video single composition need not create a storyboard.
        segments = [{'id':'main','title':title,'start':0,'end':duration,
            'narration':'\n'.join(narration_by_id.values() or spoken.values()),'visual_description':title,
            'objective_ids':[],'source_ids':[],'events':[]}]
        if cues:
            segments = [{'id':f'caption-{i+1}', 'title':title, 'start':c['start'], 'end':min(c['end'],duration),
                'narration':c['text'], 'visual_description':title, 'objective_ids':[], 'source_ids':[], 'events':[]}
                for i,c in enumerate(cues) if 0 <= c['start'] < min(c['end'],duration)] or segments
    segments.sort(key=lambda s:s['start'])
    for current, following in zip(segments, segments[1:]):
        current['end'] = min(current['end'],following['start'])
    return {'duration':duration,'segments':segments}


def stamp(seconds):
    ms=round(seconds*1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'


def import_project(project, video, *, title, project_id, store, runtime=None):
    project, video = Path(project).resolve(), Path(video).resolve()
    video.relative_to(project)
    info = (runtime or NativeRuntime()).probe(video)
    if not any(s.get('codec_type')=='video' for s in info['streams']): raise ValueError('Native result has no video stream')
    duration = float(info['format']['duration'])
    timeline = timeline_from_project(project, title=title, duration=duration)
    files = {}
    for path in project.rglob('*'):
        name = path.relative_to(project).as_posix()
        if any(part in ('.git','node_modules','.host','.media') for part in path.relative_to(project).parts): continue
        if path.is_symlink(): raise ValueError('Native delivery contains a symlink: '+name)
        if path.is_file() and name not in ('exports/project.zip',): files[name] = path.read_bytes()
    # The hosting boundary supplies the same native runtime as CLI preview.
    html = files['index.html'].decode()
    if 'assets/hyperframe.runtime.iife.js' not in html:
        script='<script src="assets/hyperframe.runtime.iife.js"></script>'
        html=html.replace('<head>','<head>'+script,1) if '<head>' in html else script+html
    files['index.html'] = html.encode()
    files['assets/hyperframe.runtime.iife.js'] = (RUNTIME/'node_modules/hyperframes/dist/hyperframe.runtime.iife.js').read_bytes()
    verification = {'passed': True, 'method': 'ffprobe_native_export_and_timeline_contract',
        'video_stream': True, 'audio_stream': any(s.get('codec_type')=='audio' for s in info['streams']),
        'duration_seconds': duration, 'content_review': 'not_performed_by_host'}
    files['exports/import-receipt.json'] = json.dumps(verification,ensure_ascii=False,indent=2).encode()
    files['timeline.json'] = json.dumps(timeline,ensure_ascii=False,indent=2).encode()
    files['exports/lesson.mp4'] = video.read_bytes()
    spoken = [s for s in timeline['segments'] if s['narration']]
    files['exports/lesson.srt'] = ('\n\n'.join(f"{i}\n{stamp(s['start'])} --> {stamp(s['end'])}\n{s['narration']}" for i,s in enumerate(spoken,1))+'\n').encode()
    _, cues = native_captions(project)
    if cues:
        files['exports/lesson.srt'] = ('\n\n'.join(f"{i}\n{stamp(c['start'])} --> {stamp(min(c['end'],duration))}\n{c['text']}"
            for i,c in enumerate(cues,1) if 0 <= c['start'] < min(c['end'],duration))+'\n').encode()
    import io
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as package:
        for name, body in files.items(): package.writestr(name,body)
    files['exports/project.zip'] = archive.getvalue()
    ref = store.publish(project_id,files)
    return validate_content({'format':'hyperframes/v1','title':title,'project':ref,'timeline':timeline,
        'verification':verification, 'exports':{'video':'exports/lesson.mp4','subtitles':'exports/lesson.srt','project':'exports/project.zip'}})
