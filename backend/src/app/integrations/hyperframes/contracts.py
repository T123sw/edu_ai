"""Published native project and semantic timeline contract (seconds, [start,end))."""
from copy import deepcopy
import math
import re
from pathlib import PurePosixPath


def safe_path(value):
    if not isinstance(value, str) or not value or '\\' in value or '%' in value or '\x00' in value:
        raise ValueError('Invalid project path')
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ('', '.', '..') for p in value.split('/')) or ':' in value:
        raise ValueError('Invalid project path')
    return value


def time_value(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Time must be finite and nonnegative')
    return value


def validate_content(content):
    result = deepcopy(content)
    if result.get('format') != 'hyperframes/v1':
        raise ValueError('Expected hyperframes/v1')
    if not isinstance(result.get('title'), str) or not result['title'].strip():
        raise ValueError('Title required')
    project = result['project']
    if not re.fullmatch(r'[A-Za-z0-9_-]+', project['id']) or not re.fullmatch(r'[0-9a-f]{64}', project['digest']):
        raise ValueError('Invalid project identity')
    safe_path(project['entry'])
    timeline = result['timeline']
    duration = time_value(timeline['duration'])
    if duration <= 0 or not isinstance(timeline.get('segments'), list) or not timeline['segments']:
        raise ValueError('A classroom requires nonempty timed segments')
    ids = set()
    previous = 0
    for segment in timeline['segments']:
        sid = segment['id']
        if not isinstance(sid, str) or not sid or sid in ids:
            raise ValueError('Segment IDs must be unique')
        ids.add(sid)
        start, end = time_value(segment['start']), time_value(segment['end'])
        if start < previous or end <= start or end > duration:
            raise ValueError('Invalid or overlapping segment interval')
        previous = end
        for key in ('title', 'narration', 'visual_description'):
            if not isinstance(segment.get(key), str): raise ValueError(f'Missing {key}')
        if segment.get('audio_path') is not None:
            safe_path(segment['audio_path'])
        for key in ('objective_ids', 'source_ids'):
            if not isinstance(segment.get(key), list) or any(not isinstance(v, str) for v in segment[key]):
                raise ValueError(f'Invalid {key}')
        for event in segment.get('events', []):
            if not start <= time_value(event['start']) < time_value(event['end']) <= end:
                raise ValueError(f"Event outside segment {sid}: [{event.get('start')}, {event.get('end')}) must be inside GLOBAL [{start}, {end}); add segment start {start} to scene-local event times")
            if not isinstance(event.get('description'), str) or not isinstance(event.get('target'), str):
                raise ValueError('Invalid visual event')
    for value in result.get('exports', {}).values(): safe_path(value)
    return result


def resolve_position(content, seconds):
    value = validate_content(content)
    time_value(seconds)
    timeline = value['timeline']
    if seconds > timeline['duration']: raise ValueError('Position exceeds duration')
    segments = timeline['segments']
    for i, segment in enumerate(segments):
        if segment['start'] <= seconds < segment['end'] or (i == len(segments)-1 and seconds == timeline['duration'] == segment['end']):
            return {'segment': segment, 'events': [e for e in segment.get('events', []) if e['start'] <= seconds < e['end']]}
    return {'segment': None, 'events': []}
